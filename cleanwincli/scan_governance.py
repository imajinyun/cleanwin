"""Scan performance and external rule review governance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SCAN_GOVERNANCE_SCHEMA = "cleanwin.scan-governance.v1"
SCRIPT_BOUNDARY_VALIDATION_SCHEMA = "cleanwin.script-boundary-validation.v1"
_ALLOWED_ROOT_FULLNAME_LINES = (
    "$RootFullPath = [System.IO.Path]::GetFullPath($Root.FullName)",
    "artifact_root = $Root.FullName",
)
_NATIVE_COMMAND_TOKENS = (
    "Get-AppxPackage",
    "Get-AppxProvisionedPackage",
    "reg.exe",
    "schtasks.exe",
    "Export-ScheduledTask",
    "Get-CimInstance",
    "sc.exe",
    "winget.exe",
    "scoop.cmd",
    "choco.exe",
    "dism.exe",
)
_WRITE_API_TOKENS = (
    "New-Item",
    "Set-Content",
    "Out-File",
    "Export-Csv",
    "Copy-Item",
    "Move-Item",
    "Start-Process",
    "Invoke-Expression",
)
_ALLOWED_WRITE_API_LINES = (
    "return New-Item -ItemType Directory -Force -Path $FullPath",
    "return New-Item -ItemType Directory -Force -Path (Resolve-ArtifactPath -RelativePath $RelativePath)",
    "New-Item -ItemType Directory -Force -Path $Parent | Out-Null",
    "$Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $FullPath -Encoding UTF8",
    "$Lines | Set-Content -LiteralPath $FullPath -Encoding UTF8",
    "$Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8",
)


def _violation(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def validate_script_boundaries(
    *,
    makefile_text: str,
    native_collector_text: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    makefile_contract = contract.get("makefile", {})
    collector_contract = contract.get("native_collector", {})
    allowed_command_fragments = collector_contract.get("allowed_command_fragments", [])
    allowed_write_api_lines = collector_contract.get("allowed_write_api_lines", _ALLOWED_WRITE_API_LINES)

    for command in makefile_contract.get("required_test_entrypoints", []):
        target = command.replace("make ", "")
        if f"{target}:" not in makefile_text:
            violations.append(_violation("makefile.required_test_entrypoints", "MISSING_MAKE_TARGET", f"missing Makefile target for {command}"))
    if "$(DEV_PYTHON) -m pytest" not in makefile_text:
        violations.append(_violation("makefile.pytest", "PYTEST_NOT_RUN_THROUGH_DEV_PYTHON", "pytest must run through $(DEV_PYTHON)"))
    for protected in makefile_contract.get("protected_targets", []):
        if f"'{protected}'" in makefile_text or f'"{protected}"' in makefile_text:
            violations.append(_violation("makefile.protected_targets", "PROTECTED_TARGET_IN_CLEANUP", f"cleanup must not remove {protected}"))

    for required_text in (
        "function Resolve-ArtifactRoot",
        "function Resolve-ArtifactPath",
        "ArtifactRoot must not be empty",
        "ArtifactRoot must include a parent directory",
        "ArtifactRoot parent directory must exist",
        "ArtifactRoot must not be a filesystem root",
        "Artifact relative path must not be rooted",
        "Artifact relative path must stay under ArtifactRoot",
    ):
        if required_text not in native_collector_text:
            violations.append(_violation("native_collector.required_root_checks", "MISSING_ARTIFACT_ROOT_GUARD", required_text))
    for fragment in collector_contract.get("forbidden_command_fragments", []):
        if fragment in native_collector_text:
            violations.append(_violation("native_collector.forbidden_command_fragments", "FORBIDDEN_COMMAND_FRAGMENT", fragment))
    for line in native_collector_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "Command-Exists" in stripped:
            continue
        if any(token in stripped for token in _NATIVE_COMMAND_TOKENS) and not any(fragment in stripped for fragment in allowed_command_fragments):
            violations.append(_violation("native_collector.allowed_command_fragments", "UNREVIEWED_NATIVE_COLLECTOR_COMMAND", stripped))
        if any(token in stripped for token in _WRITE_API_TOKENS) and stripped not in allowed_write_api_lines:
            violations.append(_violation("native_collector.allowed_write_apis", "DIRECT_ARTIFACT_WRITE_API", stripped))
    if "Resolve-ArtifactPath -RelativePath $RelativePath" not in native_collector_text:
        violations.append(_violation("native_collector.allowed_write_root", "MISSING_ARTIFACT_PATH_RESOLUTION", "collector artifact paths must use Resolve-ArtifactPath"))
    direct_root_references = [
        line.strip()
        for line in native_collector_text.splitlines()
        if "$Root.FullName" in line and line.strip() not in _ALLOWED_ROOT_FULLNAME_LINES
    ]
    for line in direct_root_references:
        violations.append(_violation("native_collector.allowed_write_root", "DIRECT_ARTIFACT_ROOT_PATH_JOIN", line))
    if "Set-Content -LiteralPath $FullPath" not in native_collector_text:
        violations.append(_violation("native_collector.allowed_write_root", "MISSING_LITERAL_ARTIFACT_WRITE", "collector writes must use resolved ArtifactRoot paths"))

    return {
        "schema": SCRIPT_BOUNDARY_VALIDATION_SCHEMA,
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def scan_governance_report() -> dict[str, Any]:
    scan_budgets = [
        {
            "id": "default-inspect",
            "surface": "safe cleanup candidate collection",
            "max_items": 100,
            "max_depth": None,
            "timeout_seconds": None,
            "permission_error_policy": "aggregate-and-continue",
            "locked_file_policy": "report-and-skip",
            "progress_events": "not-emitted",
        },
        {
            "id": "file-report",
            "surface": "large-file and duplicate-file reporting",
            "max_files_scanned": 2000,
            "max_hash_bytes_per_file": 1048576,
            "protected_directory_policy": "skip-system-app-dependency-roots",
            "timeout_seconds": None,
            "permission_error_policy": "aggregate-and-continue",
            "locked_file_policy": "report-and-skip",
            "progress_events": "not-emitted",
        },
    ]
    blocked_patterns = [
        "raw shell command strings",
        "wildcard deletion outside governed roots",
        "registry mutation without export and rollback metadata",
        "browser profile root deletion",
        "user document directory deletion",
    ]
    external_rule_contract: dict[str, Any] = {
        "schema": "cleanwin.external-rule-review.v1",
        "default_state": "report-only",
        "execution_enabled": False,
        "required_source_evidence": [
            "upstream_project",
            "upstream_rule_id_or_commit",
            "license",
            "original_pattern",
            "translated_cleanwin_rule",
        ],
        "required_safety_evidence": [
            "owner",
            "category",
            "default_path",
            "sensitive_exclusions",
            "official_cleanup_command",
            "rationale",
            "test_fixture",
        ],
        "blocked_patterns": blocked_patterns,
        "promotion_requirements": [
            "schema validation",
            "fixture coverage",
            "review-plan evidence",
            "dry-run evidence",
            "promotion-gate approval",
        ],
    }
    release_gate = {
        "requires_budget_tests": True,
        "requires_external_rule_review_tests": True,
        "requires_script_boundary_tests": True,
        "requires_quality": True,
        "required_commands": ["make quality"],
        "blocks_execution_expansion": True,
    }
    script_boundary_contract = {
        "schema": "cleanwin.script-boundary-contract.v1",
        "default_state": "read-only-or-local-artifact-only",
        "execution_enabled": False,
        "makefile": {
            "managed_venv": ".venv",
            "required_test_entrypoints": ["make pytest", "make pytest-governance-smoke"],
            "cleanup_targets": [
                ".pytest_cache",
                ".coverage",
                "coverage.xml",
                "htmlcov",
                "__pycache__",
                "build",
                "dist",
                "cleanwin.egg-info",
                ".mypy_cache",
                ".ruff_cache",
            ],
            "protected_targets": [".venv", ".aiflow", ".harness", ".git"],
        },
        "native_collector": {
            "script_path": "scripts/collect-cleanwin-artifacts.ps1",
            "allowed_write_root": "operator-provided ArtifactRoot",
            "required_root_checks": [
                "ArtifactRoot must not be empty",
                "ArtifactRoot must not be a filesystem root",
                "ArtifactRoot parent must exist",
                "Artifact relative path must not be rooted",
                "Artifact relative path must stay under ArtifactRoot",
                "all artifacts are written below ArtifactRoot",
                "external command output paths must be resolved through Resolve-ArtifactPath",
            ],
            "allowed_write_apis": ["New-ArtifactDirectory", "Write-JsonArtifact", "Write-TextArtifact", "Write-Manifest"],
            "allowed_write_api_lines": list(_ALLOWED_WRITE_API_LINES),
            "allowed_command_fragments": [
                "Get-AppxPackage -AllUsers",
                "Get-AppxProvisionedPackage -Online",
                "reg.exe export",
                "schtasks.exe /Query",
                "Export-ScheduledTask",
                "Get-CimInstance Win32_Service",
                "sc.exe qc",
                "winget.exe list",
                "winget.exe export",
                "scoop.cmd list",
                "choco.exe list --local-only",
                "dism.exe /Online /Get-Features",
                "dism.exe /Online /Cleanup-Image /AnalyzeComponentStore",
                "dism.exe /Online /Cleanup-Image /ScanHealth",
                "dism.exe /Online /Cleanup-Image /CheckHealth",
            ],
            "forbidden_command_fragments": [
                "Remove-Item",
                "Remove-AppxPackage",
                "Remove-AppxProvisionedPackage",
                "Set-ItemProperty",
                "reg.exe import",
                "schtasks.exe /Change",
                "sc.exe config",
                "StartComponentCleanup",
                "RestoreHealth",
                "winget.exe uninstall",
                "choco.exe uninstall",
            ],
        },
    }
    repo_root = Path(__file__).resolve().parents[1]
    script_boundary_validation = validate_script_boundaries(
        makefile_text=(repo_root / "Makefile").read_text(encoding="utf-8"),
        native_collector_text=(repo_root / "scripts" / "collect-cleanwin-artifacts.ps1").read_text(encoding="utf-8"),
        contract=script_boundary_contract,
    )
    return {
        "schema": SCAN_GOVERNANCE_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "scan_budgets": scan_budgets,
        "external_rule_contract": external_rule_contract,
        "script_boundary_contract": script_boundary_contract,
        "script_boundary_validation": script_boundary_validation,
        "summary": {
            "budget_count": len(scan_budgets),
            "external_rule_execution_enabled": external_rule_contract["execution_enabled"],
            "blocked_pattern_count": len(blocked_patterns),
            "script_boundary_valid": script_boundary_validation["valid"],
        },
        "release_gate": release_gate,
        "non_goals": [
            "This report does not import external cleaner rules automatically.",
            "This report does not download upstream rule catalogs.",
            "This report does not enable execution for external rules.",
        ],
    }
