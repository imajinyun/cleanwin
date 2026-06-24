from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cleanwincli.core import validate_plan_payload
from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity, compare_identity
from cleanwincli.models import plan_from_dict
from cleanwincli.windows_identity import capture_windows_native_identity

JSONPayload = dict[str, Any]
CleanWinPlanFile = Callable[..., JSONPayload]


def test_capture_identity_contains_replay_fields(tmp_path: Path) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    identity = capture_filesystem_identity(target)

    assert identity["schema"] == "cleanwin.filesystem-identity.v1"
    assert identity["exists"] is True
    assert identity["file_type"] == "file"
    assert identity["size_bytes"] == 1
    assert "canonical_path" in identity
    assert "file_id" in identity
    assert "volume_serial_number" in identity
    assert "windows_file_index" in identity


def test_windows_native_identity_falls_back_off_windows(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("fallback assertion is for non-Windows hosts")

    identity = capture_windows_native_identity(tmp_path / "candidate.tmp")

    assert identity["windows_native_available"] is False
    assert identity["windows_native_error"] == "not-windows"
    assert identity["volume_serial_number"] is None


def test_compare_identity_detects_content_replacement(tmp_path: Path) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    planned = capture_filesystem_identity(target)
    target.write_text("changed", encoding="utf-8")
    current = capture_filesystem_identity(target)

    mismatches = compare_identity(planned, current)

    assert any("size_bytes" in mismatch for mismatch in mismatches), mismatches


def test_generated_plan_contains_identity_and_validate_rejects_drift(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
) -> None:
    temp_root = tmp_path / "Temp"
    temp_root.mkdir()
    target = temp_root / "stale.tmp"
    target.write_text("x", encoding="utf-8")
    plan_file = tmp_path / "plan.json"
    env = {"TEMP": str(temp_root), "TMP": str(temp_root)}

    raw = cleanwin_plan_file(
        plan_file,
        "--categories",
        "temp",
        "--older-than-days",
        "0",
        env=env,
    )

    assert raw["candidates"][0]["identity"]["schema"] == "cleanwin.filesystem-identity.v1"
    plan = plan_from_dict(raw)
    assert validate_plan_payload(plan, raw, require_context=False)["valid"] is True

    target.write_text("changed", encoding="utf-8")
    validation = validate_plan_payload(plan, raw, require_context=False)
    assert validation["valid"] is False
    assert "Filesystem identity mismatch" in "\n".join(validation["errors"])


def test_safe_delete_fails_closed_on_identity_mismatch(tmp_path: Path) -> None:
    target = tmp_path / "candidate.tmp"
    target.write_text("x", encoding="utf-8")
    planned = capture_filesystem_identity(target)
    target.write_text("changed", encoding="utf-8")

    with pytest.raises(RuntimeError):
        safe_delete(
            str(target),
            dry_run=False,
            mode="recycle",
            trash_root=tmp_path / "trash",
            expected_identity=planned,
        )

    assert target.exists()
