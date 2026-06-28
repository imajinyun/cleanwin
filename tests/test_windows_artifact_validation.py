from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any

from cleanwincli.windows_artifact_validation import (
    WINDOWS_NATIVE_ARTIFACT_LAYOUT_SCHEMA,
    WINDOWS_NATIVE_ARTIFACT_VALIDATION_ISSUE_SCHEMA,
    WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA,
    WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA,
    artifact_layout_report,
    validate_collector_manifest,
)

JSONPayload = dict[str, Any]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[Sequence[str]], dict[str, JSONPayload]]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]
WriteJSONFile = Callable[[Path, JSONPayload], Path]
WriteTextFile = Callable[[Path, str], Path]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _manifest(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA,
        "collector_version": "cleanwin-windows-native-collector-wrapper.v1",
        "generated_at_utc": "2026-06-28T00:00:00.0000000Z",
        "computer_name": "CLEANWIN-WIN11",
        "user_name": "tester",
        "is_windows": True,
        "is_admin": True,
        "windows_version": "Windows 11 24H2",
        "managed_context": "unmanaged-device",
        "artifact_root": r"C:\CleanWinArtifacts",
        "mode": "all",
        "destructive": False,
        "executes_cleanup": False,
        "records": [record],
        "summary": {"record_count": 1, "available_count": 1 if record["available"] else 0, "unavailable_count": 0 if record["available"] else 1},
    }


def _record(*, command: str = "Get-AppxPackage -AllUsers", sha256: str | None = None) -> dict[str, Any]:
    return {
        "id": "powershell-appx-packages",
        "relative_path": "appx-packages.json",
        "schema": "cleanwin.appx-package-snapshot.v1",
        "collector": "powershell-appx-packages",
        "available": True,
        "reason": "captured",
        "sha256": sha256 or _digest("[]"),
        "command": command,
    }


def test_artifact_layout_report_is_readonly_contract(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = artifact_layout_report()

    assert_readonly_report(report, WINDOWS_NATIVE_ARTIFACT_LAYOUT_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "artifact_validation_execution_enabled", "executes_native_collector", "executes_cleanup")
    assert_summary_counts(report, {"top_level_file_count": 3, "directory_count": 5})
    assert_contains_all(report["allowed_extensions"], [".json", ".jsonl", ".xml", ".reg", ".txt"])
    assert_contains_all(report["required_manifest_fields"], ["schema", "records", "summary", "destructive", "executes_cleanup"])
    assert_contains_all(report["forbidden_command_fragments"], ["Remove-AppxPackage", "RestoreHealth", "winget.exe uninstall"])


def test_artifact_validator_accepts_manifest_and_matching_hash(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_readonly_report: AssertReadonlyReport,
    assert_payload_status_true: AssertPayloadStatus,
    assert_payload_status_false: AssertPayloadStatus,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    write_text_file(tmp_path / "appx-packages.json", "[]")

    report = validate_collector_manifest(_manifest(_record()), artifact_root=tmp_path)

    assert_readonly_report(report, WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA)
    assert_payload_status_true(report, "valid")
    assert_payload_status_true(report, "ready_for_ci_artifact_upload")
    assert_payload_status_false(report, "ready_for_execution_promotion")
    assert report["issues"] == []
    assert_summary_counts(report, {"record_count": 1, "available_count": 1, "hash_checked_count": 1, "error_count": 0, "warning_count": 0})


def test_artifact_validator_reports_hash_mismatch_and_forbidden_commands(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_false: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    write_text_file(tmp_path / "appx-packages.json", "changed")

    report = validate_collector_manifest(
        _manifest(_record(command="Remove-AppxPackage Microsoft.XboxGamingOverlay")),
        artifact_root=tmp_path,
    )
    codes = [issue["code"] for issue in report["issues"]]

    assert_payload_status_false(report, "valid")
    assert_contains_all(codes, ["HASH_MISMATCH", "FORBIDDEN_COMMAND_FRAGMENT"])
    assert_payload_schema(report["issues"][0], WINDOWS_NATIVE_ARTIFACT_VALIDATION_ISSUE_SCHEMA)


def test_artifact_validator_reports_missing_fields_unsafe_paths_and_summary_mismatch(
    assert_contains_all: AssertContainsAll,
    assert_payload_status_false: AssertPayloadStatus,
) -> None:
    manifest = _manifest({**_record(), "relative_path": r"..\outside.exe"})
    del manifest["collector_version"]
    manifest["summary"]["record_count"] = 99

    report = validate_collector_manifest(manifest, artifact_root=None)
    codes = [issue["code"] for issue in report["issues"]]

    assert_payload_status_false(report, "valid")
    assert_contains_all(codes, ["MISSING_MANIFEST_FIELD", "UNSAFE_RELATIVE_PATH", "UNSUPPORTED_EXTENSION", "SUMMARY_MISMATCH"])


def test_cli_can_validate_manifest_file(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    write_json_file: WriteJSONFile,
    cleanwin_json: Callable[..., JSONPayload],
    assert_field_values: AssertFieldValues,
) -> None:
    write_text_file(tmp_path / "appx-packages.json", "[]")
    manifest_path = write_json_file(tmp_path / "manifest.json", _manifest(_record()))

    payload = cleanwin_json("windows-artifact-validate", "--manifest", str(manifest_path))

    assert_field_values(payload, {"schema": WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA, "valid": True})
    assert_field_values(payload["summary"], {"hash_checked_count": 1, "error_count": 0})


def test_cli_provider_and_schema_registry_expose_artifact_validation(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    assert_cli_provider_schema_sample("windows-artifact-layout", WINDOWS_NATIVE_ARTIFACT_LAYOUT_SCHEMA)
    assert_cli_provider_schema_sample("windows-artifact-validate", WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA)
    samples = assert_schema_samples(
        [
            WINDOWS_NATIVE_ARTIFACT_LAYOUT_SCHEMA,
            WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA,
            WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA,
            WINDOWS_NATIVE_ARTIFACT_VALIDATION_ISSUE_SCHEMA,
        ]
    )
    assert_payload_schema(samples[WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA], WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA)
