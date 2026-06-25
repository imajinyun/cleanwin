from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity

JSONPayload = dict[str, Any]
WriteTextFile = Callable[[Path, str], Path]
MakeDirectory = Callable[[Path], Path]
ReadJSONLRecord = Callable[[Path], JSONPayload]
AssertFieldValues = Callable[[JSONPayload, dict[str, object]], JSONPayload]
AssertPathExists = Callable[[Path], Path]
AssertPathMissing = Callable[[Path], Path]


def test_recycle_fails_closed_outside_windows_without_test_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_text_file: WriteTextFile,
    assert_path_exists: AssertPathExists,
) -> None:
    if os.name == "nt":
        pytest.skip("non-Windows fail-closed path only applies off Windows")
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "0")

    with pytest.raises(RuntimeError, match="Recycle Bin routing is only available on Windows"):
        safe_delete(str(target), dry_run=False, mode="recycle")

    assert_path_exists(target)


def test_recycle_routes_to_test_trash_and_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_text_file: WriteTextFile,
    read_jsonl_record: ReadJSONLRecord,
    assert_field_values: AssertFieldValues,
    assert_path_exists: AssertPathExists,
    assert_path_missing: AssertPathMissing,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    trash = tmp_path / "trash"
    log = tmp_path / "ops.jsonl"
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "1")

    result = safe_delete(str(target), dry_run=False, mode="recycle", trash_root=trash, operation_log=log)

    assert_field_values(result, {"status": "recycled"})
    assert_path_missing(target)
    assert_path_exists(Path(result["destination"]))
    record = read_jsonl_record(log)
    assert_field_values(record, {"status": "recycled"})


def test_symlinked_trash_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_text_file: WriteTextFile,
    make_directory: MakeDirectory,
    assert_path_exists: AssertPathExists,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    real_trash = make_directory(tmp_path / "real-trash")
    trash_link = tmp_path / "trash-link"
    try:
        trash_link.symlink_to(real_trash, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "1")

    with pytest.raises(RuntimeError, match="Refusing to use symlinked recycle sandbox"):
        safe_delete(str(target), dry_run=False, mode="recycle", trash_root=trash_link)

    assert_path_exists(target)


def test_permanent_delete_requires_explicit_allow(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_path_exists: AssertPathExists,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")

    with pytest.raises(RuntimeError, match="Permanent delete requires explicit allow_permanent=True"):
        safe_delete(str(target), dry_run=False, mode="permanent", allow_permanent=False)

    assert_path_exists(target)


def test_safe_delete_rechecks_expected_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_text_file: WriteTextFile,
    assert_path_exists: AssertPathExists,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    identity = capture_filesystem_identity(target)
    write_text_file(target, "changed")
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "1")

    with pytest.raises(RuntimeError, match="Filesystem identity mismatch"):
        safe_delete(
            str(target),
            dry_run=False,
            mode="recycle",
            trash_root=tmp_path / "trash",
            expected_identity=identity,
        )

    assert_path_exists(target)
