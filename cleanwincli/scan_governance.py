"""Scan performance and external rule review governance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

SCAN_GOVERNANCE_SCHEMA = "cleanwin.scan-governance.v1"
SCRIPT_BOUNDARY_VALIDATION_SCHEMA = "cleanwin.script-boundary-validation.v1"


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
        "ArtifactRoot must not be empty",
        "ArtifactRoot must include a parent directory",
        "ArtifactRoot parent directory must exist",
        "ArtifactRoot must not be a filesystem root",
    ):
        if required_text not in native_collector_text:
            violations.append(_violation("native_collector.required_root_checks", "MISSING_ARTIFACT_ROOT_GUARD", required_text))
    for fragment in collector_contract.get("forbidden_command_fragments", []):
        if fragment in native_collector_text:
            violations.append(_violation("native_collector.forbidden_command_fragments", "FORBIDDEN_COMMAND_FRAGMENT", fragment))
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
                "all artifacts are written below ArtifactRoot",
            ],
            "allowed_write_apis": ["New-ArtifactDirectory", "Write-JsonArtifact", "Write-TextArtifact", "Write-Manifest"],
            "forbidden_command_fragments": [
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
