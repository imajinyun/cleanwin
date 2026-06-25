from __future__ import annotations

import os
from collections.abc import Callable, Sequence
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
MakeTempPlan = Callable[[Path, bool], tuple[Path, Path, dict[str, str]]]
WriteTextFile = Callable[[Path, str], Path]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
AssertAnyMatch = Callable[[list[str], Callable[[str], bool]], str]
AssertTextContainsAll = Callable[[str, Sequence[str]], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertFieldsPresent = Callable[[JSONPayload, Sequence[str]], JSONPayload]
AssertPathExists = Callable[[Path], Path]


def test_capture_identity_contains_replay_fields(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_payload_schema: AssertPayloadSchema,
    assert_field_values: AssertFieldValues,
    assert_fields_present: AssertFieldsPresent,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    identity = capture_filesystem_identity(target)

    assert_payload_schema(identity, "cleanwin.filesystem-identity.v1")
    assert_field_values(identity, {"exists": True, "file_type": "file", "size_bytes": 1})
    assert_fields_present(identity, ["canonical_path", "file_id", "volume_serial_number", "windows_file_index"])


def test_windows_native_identity_falls_back_off_windows(
    tmp_path: Path,
    assert_field_values: AssertFieldValues,
) -> None:
    if os.name == "nt":
        pytest.skip("fallback assertion is for non-Windows hosts")

    identity = capture_windows_native_identity(tmp_path / "candidate.tmp")

    assert_field_values(
        identity,
        {
            "windows_native_available": False,
            "windows_native_error": "not-windows",
            "volume_serial_number": None,
        },
    )


def test_compare_identity_detects_content_replacement(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_any_match: AssertAnyMatch,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    planned = capture_filesystem_identity(target)
    write_text_file(target, "changed")
    current = capture_filesystem_identity(target)

    mismatches = compare_identity(planned, current)

    assert_any_match(mismatches, lambda mismatch: "size_bytes" in mismatch)


def test_generated_plan_contains_identity_and_validate_rejects_drift(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    make_temp_plan_fixture: MakeTempPlan,
    write_text_file: WriteTextFile,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
    assert_payload_status_false: AssertPayloadStatus,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    _, target, env = make_temp_plan_fixture(tmp_path, False)
    plan_file = tmp_path / "plan.json"

    raw = cleanwin_plan_file(
        plan_file,
        "--categories",
        "temp",
        "--older-than-days",
        "0",
        env=env,
    )

    assert_payload_schema(raw["candidates"][0]["identity"], "cleanwin.filesystem-identity.v1")
    plan = plan_from_dict(raw)
    assert_payload_status_true(validate_plan_payload(plan, raw, require_context=False), "valid")

    write_text_file(target, "changed")
    validation = validate_plan_payload(plan, raw, require_context=False)
    assert_payload_status_false(validation, "valid")
    assert_text_contains_all("\n".join(validation["errors"]), ["Filesystem identity mismatch"])


def test_safe_delete_fails_closed_on_identity_mismatch(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_path_exists: AssertPathExists,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    planned = capture_filesystem_identity(target)
    write_text_file(target, "changed")

    with pytest.raises(RuntimeError, match="Filesystem identity mismatch"):
        safe_delete(
            str(target),
            dry_run=False,
            mode="recycle",
            trash_root=tmp_path / "trash",
            expected_identity=planned,
        )

    assert_path_exists(target)
