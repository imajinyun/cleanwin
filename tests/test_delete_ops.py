from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity


def test_recycle_fails_closed_outside_windows_without_test_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        pytest.skip("non-Windows fail-closed path only applies off Windows")
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "0")

    with pytest.raises(RuntimeError):
        safe_delete(str(target), dry_run=False, mode="recycle")

    assert target.exists()


def test_recycle_routes_to_test_trash_and_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    trash = tmp_path / "trash"
    log = tmp_path / "ops.jsonl"
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "1")

    result = safe_delete(str(target), dry_run=False, mode="recycle", trash_root=trash, operation_log=log)

    assert result["status"] == "recycled"
    assert not target.exists()
    assert Path(result["destination"]).exists()
    record = json.loads(log.read_text(encoding="utf-8").strip())
    assert record["status"] == "recycled"


def test_symlinked_trash_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    real_trash = tmp_path / "real-trash"
    real_trash.mkdir()
    trash_link = tmp_path / "trash-link"
    try:
        trash_link.symlink_to(real_trash, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "1")

    with pytest.raises(RuntimeError):
        safe_delete(str(target), dry_run=False, mode="recycle", trash_root=trash_link)

    assert target.exists()


def test_permanent_delete_requires_explicit_allow(tmp_path: Path) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")

    with pytest.raises(RuntimeError):
        safe_delete(str(target), dry_run=False, mode="permanent", allow_permanent=False)

    assert target.exists()


def test_safe_delete_rechecks_expected_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    identity = capture_filesystem_identity(target)
    target.write_text("changed", encoding="utf-8")
    monkeypatch.setenv("CLEANWIN_TEST_MODE", "1")

    with pytest.raises(RuntimeError):
        safe_delete(
            str(target),
            dry_run=False,
            mode="recycle",
            trash_root=tmp_path / "trash",
            expected_identity=identity,
        )

    assert target.exists()
