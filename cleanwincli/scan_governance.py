"""Scan performance and external rule review governance."""

from __future__ import annotations

from typing import Any

SCAN_GOVERNANCE_SCHEMA = "cleanwin.scan-governance.v1"


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
        "requires_quality": True,
        "required_commands": ["make quality"],
        "blocks_execution_expansion": True,
    }
    return {
        "schema": SCAN_GOVERNANCE_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "scan_budgets": scan_budgets,
        "external_rule_contract": external_rule_contract,
        "summary": {
            "budget_count": len(scan_budgets),
            "external_rule_execution_enabled": external_rule_contract["execution_enabled"],
            "blocked_pattern_count": len(blocked_patterns),
        },
        "release_gate": release_gate,
        "non_goals": [
            "This report does not import external cleaner rules automatically.",
            "This report does not download upstream rule catalogs.",
            "This report does not enable execution for external rules.",
        ],
    }
