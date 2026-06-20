"""Filesystem identity capture and replay checks for CleanWin."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from cleanwincli.windows_identity import capture_windows_native_identity

IDENTITY_SCHEMA = "cleanwin.filesystem-identity.v1"

STRICT_IDENTITY_FIELDS = (
    "exists",
    "canonical_path",
    "file_type",
    "is_symlink",
    "is_junction",
    "size_bytes",
    "modified_ns",
    "device",
    "file_id",
    "mode",
    "windows_file_attributes",
    "windows_reparse_tag",
)


def _file_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"


def _is_junction(path: Path) -> bool:
    if hasattr(path, "is_junction"):
        try:
            return bool(path.is_junction())
        except OSError:
            return True
    return False


def capture_filesystem_identity(path: Path) -> dict[str, Any]:
    """Capture stable identity fields for plan replay validation.

    Uses only stdlib data so it works in tests on non-Windows hosts. On Windows,
    Python stat exposes file attributes and reparse tags when available; on
    POSIX, inode/device act as the file-id stand-in.
    """

    resolved = path.resolve(strict=False)
    identity: dict[str, Any] = {
        "schema": IDENTITY_SCHEMA,
        "path": str(path),
        "canonical_path": str(resolved),
        "platform_os_name": os.name,
        "source": "python-stdlib-stat",
        "exists": path.exists() or path.is_symlink(),
        "is_symlink": path.is_symlink(),
        "is_junction": _is_junction(path),
        "owner_sid": None,
        "volume_serial_number": None,
        "windows_file_index": None,
        "windows_native_available": False,
        "windows_native_error": None,
    }
    try:
        st = path.stat(follow_symlinks=False)
    except OSError as exc:
        identity.update(
            {
                "readable": False,
                "error": str(exc),
                "file_type": "missing",
                "size_bytes": None,
                "modified_ns": None,
                "device": None,
                "file_id": None,
                "mode": None,
                "owner_uid": None,
                "owner_gid": None,
                "windows_file_attributes": None,
                "windows_reparse_tag": None,
            }
        )
        identity.update(capture_windows_native_identity(path))
        return identity
    identity.update(
        {
            "readable": True,
            "file_type": _file_type(st.st_mode),
            "size_bytes": int(st.st_size),
            "modified_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
            "device": int(st.st_dev),
            "file_id": int(st.st_ino),
            "mode": int(st.st_mode),
            "owner_uid": int(st.st_uid) if hasattr(st, "st_uid") else None,
            "owner_gid": int(st.st_gid) if hasattr(st, "st_gid") else None,
            "windows_file_attributes": getattr(st, "st_file_attributes", None),
            "windows_reparse_tag": getattr(st, "st_reparse_tag", None),
        }
    )
    identity.update(capture_windows_native_identity(path))
    return identity


def compare_identity(planned: dict[str, Any] | None, current: dict[str, Any]) -> list[str]:
    if not planned:
        return ["Missing planned filesystem identity"]
    mismatches: list[str] = []
    for field in STRICT_IDENTITY_FIELDS:
        if planned.get(field) != current.get(field):
            mismatches.append(f"{field}: planned={planned.get(field)!r} current={current.get(field)!r}")
    return mismatches


def assert_identity_matches(path: Path, planned: dict[str, Any] | None) -> None:
    current = capture_filesystem_identity(path)
    mismatches = compare_identity(planned, current)
    if mismatches:
        joined = "; ".join(mismatches)
        raise RuntimeError(f"Filesystem identity mismatch for {path}: {joined}")
