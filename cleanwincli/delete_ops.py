"""Single safety exit for CleanWin destructive cleanup operations."""

from __future__ import annotations

import ctypes
import os
import shutil
from pathlib import Path

from cleanwincli.identity import assert_identity_matches
from cleanwincli.operation_log import write_operation_log
from cleanwincli.protection import validate_filesystem_candidate


def is_test_mode() -> bool:
    return os.environ.get("CLEANWIN_TEST_MODE") == "1"


def remove_path_permanently(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing to permanently delete symlink/reparse-point candidate: {path}")
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def unique_trash_path(path: Path, *, trash_root: Path) -> Path:
    base = f"cleanwin-{path.name}"
    candidate = trash_root / base
    suffix = 1
    while candidate.exists():
        candidate = trash_root / f"{base}-{suffix}"
        suffix += 1
    return candidate


def route_to_test_trash(path: Path, *, trash_root: Path, dry_run: bool) -> Path:
    if trash_root.exists() and trash_root.is_symlink():
        raise RuntimeError(f"Refusing to use symlinked recycle sandbox: {trash_root}")
    trash_root.mkdir(parents=True, exist_ok=True)
    if trash_root.is_symlink():
        raise RuntimeError(f"Refusing to use symlinked recycle sandbox: {trash_root}")
    target = unique_trash_path(path, trash_root=trash_root)
    if not dry_run:
        shutil.move(str(path), str(target))
    return target


def route_to_windows_recycle_bin(path: Path, *, dry_run: bool) -> Path | None:
    if os.name != "nt":
        raise RuntimeError("Recycle Bin routing is only available on Windows outside CLEANWIN_TEST_MODE")
    if dry_run:
        return None
    shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):  # type: ignore[misc]
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.USHORT),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    fo_delete = 0x0003
    fof_allowundo = 0x0040
    fof_noconfirmation = 0x0010
    fof_silent = 0x0004
    fof_noerrorui = 0x0400
    operation = SHFILEOPSTRUCTW()
    operation.wFunc = fo_delete
    operation.pFrom = str(path) + "\0\0"
    operation.fFlags = fof_allowundo | fof_noconfirmation | fof_silent | fof_noerrorui
    result = shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted:
        raise RuntimeError(f"Recycle Bin routing failed for {path}: result={result}")
    return None


def safe_delete(
    path_text: str,
    *,
    dry_run: bool,
    mode: str = "recycle",
    allow_permanent: bool = False,
    trash_root: Path | None = None,
    operation_log: Path | None = None,
    expected_identity: dict[str, object] | None = None,
) -> dict[str, str]:
    path = Path(path_text)
    validate_filesystem_candidate(path)
    if expected_identity is not None:
        assert_identity_matches(path, expected_identity)
    if not path.exists():
        result = {"status": "missing", "path": str(path), "mode": mode}
    elif dry_run:
        result = {"status": "dry-run", "path": str(path), "mode": mode}
    elif mode == "recycle":
        if is_test_mode():
            destination = route_to_test_trash(path, trash_root=trash_root or Path.cwd() / ".cleanwin-trash", dry_run=False)
            result = {"status": "recycled", "path": str(path), "destination": str(destination), "mode": mode}
        else:
            route_to_windows_recycle_bin(path, dry_run=False)
            result = {"status": "recycled", "path": str(path), "mode": mode}
    elif mode == "permanent":
        if not allow_permanent:
            raise RuntimeError("Permanent delete requires explicit allow_permanent=True")
        remove_path_permanently(path)
        result = {"status": "deleted", "path": str(path), "mode": mode}
    else:
        raise RuntimeError(f"Unsupported delete mode: {mode}")
    if operation_log is not None:
        write_operation_log(operation_log, result)
    return result
