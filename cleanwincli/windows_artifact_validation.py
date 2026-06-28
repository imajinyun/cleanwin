"""Read-only validation for Windows native collector artifact layouts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

WINDOWS_NATIVE_ARTIFACT_LAYOUT_SCHEMA = "cleanwin.windows-native-artifact-layout.v1"
WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA = "cleanwin.windows-native-collector-manifest.v1"
WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA = "cleanwin.windows-native-artifact-validation.v1"
WINDOWS_NATIVE_ARTIFACT_VALIDATION_ISSUE_SCHEMA = "cleanwin.windows-native-artifact-validation-issue.v1"

ALLOWED_ARTIFACT_EXTENSIONS = (".csv", ".json", ".jsonl", ".log", ".reg", ".txt", ".xml")
FORBIDDEN_COMMAND_FRAGMENTS = (
    "Remove-AppxPackage",
    "Remove-AppxProvisionedPackage",
    "Set-ItemProperty",
    "reg.exe import",
    "reg import",
    "schtasks.exe /Change",
    "schtasks /Change",
    "sc.exe config",
    "sc config",
    "StartComponentCleanup",
    "RestoreHealth",
    "winget.exe uninstall",
    "winget uninstall",
    "choco.exe uninstall",
    "choco uninstall",
)
REQUIRED_MANIFEST_FIELDS = (
    "schema",
    "collector_version",
    "generated_at_utc",
    "computer_name",
    "user_name",
    "is_windows",
    "is_admin",
    "artifact_root",
    "mode",
    "destructive",
    "executes_cleanup",
    "records",
    "summary",
)
REQUIRED_RECORD_FIELDS = ("id", "relative_path", "schema", "collector", "available", "reason", "sha256", "command")
EXPECTED_TOP_LEVEL_LAYOUT = {
    "appx-packages.json": "cleanwin.appx-package-snapshot.v1",
    "provisioned-appx.json": "cleanwin.provisioned-appx-package-snapshot.v1",
    "manifest.json": WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA,
}
EXPECTED_DIRECTORY_LAYOUT = {
    "registry": [".reg"],
    "scheduled-tasks": [".csv", ".json", ".xml"],
    "services": [".json", ".txt"],
    "package-managers": [".json", ".log", ".txt"],
    "dism": [".txt"],
}


def _issue(path: str, code: str, message: str, *, severity: str = "error", record_id: str = "") -> dict[str, Any]:
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_VALIDATION_ISSUE_SCHEMA,
        "severity": severity,
        "code": code,
        "path": path,
        "record_id": record_id,
        "message": message,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _artifact_path(root: Path, relative_path: str) -> Path:
    parts = [part for part in relative_path.replace("\\", "/").split("/") if part and part != "."]
    return root.joinpath(*parts)


def _record_id(record: Mapping[str, Any], index: int) -> str:
    return str(record.get("id") or f"record-{index}")


def artifact_layout_report() -> dict[str, Any]:
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_LAYOUT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "manifest_schema": WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA,
        "validator_schema": WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA,
        "artifact_root": "<operator-provided-artifact-root>",
        "allowed_extensions": list(ALLOWED_ARTIFACT_EXTENSIONS),
        "required_manifest_fields": list(REQUIRED_MANIFEST_FIELDS),
        "required_record_fields": list(REQUIRED_RECORD_FIELDS),
        "expected_top_level_files": [
            {"relative_path": path, "schema": schema}
            for path, schema in sorted(EXPECTED_TOP_LEVEL_LAYOUT.items())
        ],
        "expected_directories": [
            {"relative_path": path, "allowed_extensions": extensions}
            for path, extensions in sorted(EXPECTED_DIRECTORY_LAYOUT.items())
        ],
        "hash_contract": {
            "algorithm": "sha256",
            "encoding": "hex-uppercase",
            "required_for_available_records": True,
            "validator_reads_files": True,
            "validator_executes_system_commands": False,
        },
        "context_contract": {
            "requires_windows_version": True,
            "requires_user_context": True,
            "requires_admin_context": True,
            "requires_managed_context": True,
            "managed_context_source": "collector manifest, CI environment, or operator-supplied run metadata",
        },
        "forbidden_command_fragments": list(FORBIDDEN_COMMAND_FRAGMENTS),
        "execution_gate": {
            "artifact_validation_execution_enabled": False,
            "executes_native_collector": False,
            "executes_cleanup": False,
            "ai_auto_call_allowed": False,
        },
        "summary": {
            "top_level_file_count": len(EXPECTED_TOP_LEVEL_LAYOUT),
            "directory_count": len(EXPECTED_DIRECTORY_LAYOUT),
            "allowed_extension_count": len(ALLOWED_ARTIFACT_EXTENSIONS),
            "forbidden_command_fragment_count": len(FORBIDDEN_COMMAND_FRAGMENTS),
        },
        "non_goals": [
            "This report does not run the Windows native collector.",
            "This report does not execute PowerShell, DISM, registry, package manager, service, or scheduled task commands.",
            "This report does not mutate registry, services, scheduled tasks, packages, or Windows features.",
        ],
    }


def sample_collector_manifest() -> dict[str, Any]:
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
        "records": [
            {
                "id": "powershell-appx-packages",
                "relative_path": "appx-packages.json",
                "schema": "cleanwin.appx-package-snapshot.v1",
                "collector": "powershell-appx-packages",
                "available": True,
                "reason": "captured",
                "sha256": "0" * 64,
                "command": "Get-AppxPackage -AllUsers",
            }
        ],
        "summary": {"record_count": 1, "available_count": 1, "unavailable_count": 0},
    }


def artifact_validation_sample() -> dict[str, Any]:
    return validate_collector_manifest(sample_collector_manifest(), artifact_root=None)


def load_collector_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("collector manifest must be a JSON object")
    return payload


def validate_collector_manifest(manifest: Mapping[str, Any], *, artifact_root: Path | None) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if manifest.get("schema") != WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA:
        issues.append(
            _issue(
                "schema",
                "INVALID_MANIFEST_SCHEMA",
                f"schema must be {WINDOWS_NATIVE_COLLECTOR_MANIFEST_SCHEMA}",
            )
        )
    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest:
            issues.append(_issue(field, "MISSING_MANIFEST_FIELD", f"manifest field is required: {field}"))
    if manifest.get("destructive") is not False:
        issues.append(_issue("destructive", "DESTRUCTIVE_MANIFEST", "collector manifest must declare destructive=false"))
    if manifest.get("executes_cleanup") is not False:
        issues.append(_issue("executes_cleanup", "CLEANUP_EXECUTION_DECLARED", "collector manifest must declare executes_cleanup=false"))

    records_raw = manifest.get("records", [])
    records = records_raw if isinstance(records_raw, list) else []
    if not isinstance(records_raw, list):
        issues.append(_issue("records", "INVALID_RECORDS_TYPE", "records must be a list"))

    record_ids: set[str] = set()
    available_count = 0
    unavailable_count = 0
    hash_checked_count = 0
    schema_counts: dict[str, int] = {}
    extension_counts: dict[str, int] = {}
    for index, raw_record in enumerate(records):
        if not isinstance(raw_record, Mapping):
            issues.append(_issue(f"records[{index}]", "INVALID_RECORD_TYPE", "record must be an object"))
            continue
        record = raw_record
        record_id = _record_id(record, index)
        if record_id in record_ids:
            issues.append(_issue(f"records[{index}].id", "DUPLICATE_RECORD_ID", f"duplicate record id: {record_id}", record_id=record_id))
        record_ids.add(record_id)
        for field in REQUIRED_RECORD_FIELDS:
            if field not in record:
                issues.append(_issue(f"records[{index}].{field}", "MISSING_RECORD_FIELD", f"record field is required: {field}", record_id=record_id))
        relative_path = str(record.get("relative_path") or "")
        if not relative_path:
            issues.append(_issue(f"records[{index}].relative_path", "EMPTY_RELATIVE_PATH", "relative_path is required", record_id=record_id))
        elif Path(relative_path.replace("\\", "/")).is_absolute() or ".." in relative_path.replace("\\", "/").split("/"):
            issues.append(_issue(f"records[{index}].relative_path", "UNSAFE_RELATIVE_PATH", "relative_path must stay inside artifact root", record_id=record_id))
        suffix = Path(relative_path.replace("\\", "/")).suffix.lower()
        if relative_path and suffix not in ALLOWED_ARTIFACT_EXTENSIONS:
            issues.append(_issue(f"records[{index}].relative_path", "UNSUPPORTED_EXTENSION", f"unsupported artifact extension: {suffix}", record_id=record_id))
        if suffix:
            extension_counts[suffix] = extension_counts.get(suffix, 0) + 1
        schema = str(record.get("schema") or "")
        if schema:
            schema_counts[schema] = schema_counts.get(schema, 0) + 1
        command = str(record.get("command") or "")
        for fragment in FORBIDDEN_COMMAND_FRAGMENTS:
            if fragment.lower() in command.lower():
                issues.append(_issue(f"records[{index}].command", "FORBIDDEN_COMMAND_FRAGMENT", f"command contains forbidden fragment: {fragment}", record_id=record_id))
        available = record.get("available")
        if available is True:
            available_count += 1
            if not record.get("sha256"):
                issues.append(_issue(f"records[{index}].sha256", "MISSING_SHA256", "available artifacts must include sha256", record_id=record_id))
            if artifact_root is not None and relative_path:
                artifact_path = _artifact_path(artifact_root, relative_path)
                if not artifact_path.exists():
                    issues.append(_issue(f"records[{index}].relative_path", "MISSING_ARTIFACT_FILE", f"available artifact file is missing: {relative_path}", record_id=record_id))
                elif artifact_path.is_file() and record.get("sha256"):
                    hash_checked_count += 1
                    actual = _sha256_file(artifact_path)
                    expected = str(record["sha256"]).upper()
                    if actual != expected:
                        issues.append(_issue(f"records[{index}].sha256", "HASH_MISMATCH", f"sha256 mismatch for {relative_path}", record_id=record_id))
        elif available is False:
            unavailable_count += 1
        else:
            issues.append(_issue(f"records[{index}].available", "INVALID_AVAILABLE_VALUE", "available must be true or false", record_id=record_id))

    summary = manifest.get("summary", {})
    if isinstance(summary, Mapping):
        expected_summary: dict[str, int] = {
            "record_count": len(records),
            "available_count": available_count,
            "unavailable_count": unavailable_count,
        }
        for summary_key, expected_value in expected_summary.items():
            if summary.get(summary_key) != expected_value:
                issues.append(_issue(f"summary.{summary_key}", "SUMMARY_MISMATCH", f"summary {summary_key} must be {expected_value}"))
    else:
        issues.append(_issue("summary", "INVALID_SUMMARY_TYPE", "summary must be an object"))

    required_context_warnings = {
        "windows_version": "Windows version should be captured for real artifact matrices.",
        "managed_context": "Managed/unmanaged context should be captured for promotion review.",
    }
    for field, message in required_context_warnings.items():
        if not manifest.get(field):
            issues.append(_issue(field, "MISSING_CONTEXT_FIELD", message, severity="warning"))

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_VALIDATION_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "manifest_schema": str(manifest.get("schema") or ""),
        "artifact_root": str(artifact_root) if artifact_root is not None else str(manifest.get("artifact_root") or ""),
        "valid": error_count == 0,
        "ready_for_ci_artifact_upload": error_count == 0,
        "ready_for_execution_promotion": False,
        "issues": issues,
        "layout": artifact_layout_report(),
        "summary": {
            "record_count": len(records),
            "available_count": available_count,
            "unavailable_count": unavailable_count,
            "schema_count": len(schema_counts),
            "extension_count": len(extension_counts),
            "hash_checked_count": hash_checked_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "forbidden_command_issue_count": sum(1 for issue in issues if issue["code"] == "FORBIDDEN_COMMAND_FRAGMENT"),
            "hash_mismatch_count": sum(1 for issue in issues if issue["code"] == "HASH_MISMATCH"),
        },
        "schema_counts": dict(sorted(schema_counts.items())),
        "extension_counts": dict(sorted(extension_counts.items())),
        "execution_gate": {
            "artifact_validation_execution_enabled": False,
            "executes_native_collector": False,
            "executes_cleanup": False,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This validator does not run the Windows native collector.",
            "This validator does not execute PowerShell, DISM, registry, package manager, service, or scheduled task commands.",
            "This validator does not mutate registry, services, scheduled tasks, packages, or Windows features.",
        ],
    }


def artifact_validation_report(manifest_path: Path | None = None) -> dict[str, Any]:
    if manifest_path is None:
        return artifact_validation_sample()
    manifest = load_collector_manifest(manifest_path)
    return validate_collector_manifest(manifest, artifact_root=manifest_path.parent)
