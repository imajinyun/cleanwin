from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.windows_smoke import (
    WINDOWS_SMOKE_MATRIX_SCHEMA,
    WINDOWS_SNAPSHOT_ARTIFACT_MATRIX_SCHEMA,
    windows_smoke_matrix_report,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_windows_smoke_matrix_is_non_destructive_release_gate(
    assert_readonly_report: AssertReadonlyReport,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    report = windows_smoke_matrix_report()

    assert_readonly_report(report, WINDOWS_SMOKE_MATRIX_SCHEMA)
    assert_summary_counts(report, {"destructive_scenario_count": 0})
    assert_field_values(
        report["release_gate"],
        {
            "required_before_execution_expansion": True,
            "requires_windows_10_evidence": True,
            "requires_windows_11_evidence": True,
            "allows_synthetic_fixture_only": False,
        },
    )


def test_windows_smoke_matrix_covers_expected_edge_scenarios(assert_contains_all: AssertContainsAll) -> None:
    report = windows_smoke_matrix_report()
    by_id = {scenario["id"]: scenario for scenario in report["scenarios"]}

    assert_contains_all(
        by_id,
        [
            "win10-win11-standard-user-safe-preview",
            "admin-official-command-and-recovery-readiness",
            "debloat-privacy-readonly-baseline",
            "startup-service-task-readonly-inventory",
            "system-health-readonly-diagnostics",
            "onedrive-known-folders-and-user-data-protection",
            "browser-profile-lock-and-sensitive-exclusion",
            "wsl-docker-visual-studio-report-only",
            "filesystem-edge-cases",
        ],
    )

    filesystem = by_id["filesystem-edge-cases"]
    assert_contains_all(
        filesystem["required_evidence"],
        ["symlink_rejected", "junction_rejected", "non_english_path_handled"],
    )

    browser = by_id["browser-profile-lock-and-sensitive-exclusion"]
    assert_contains_all(browser["commands"], [["python", "cleanwin.py", "--json", "browser-profile-inventory"]])
    assert_contains_all(browser["required_evidence"], ["sensitive_exclusions"])


def test_windows_smoke_matrix_includes_real_snapshot_artifact_matrix(
    assert_payload_schema: Callable[[JSONPayload, str], JSONPayload],
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    matrix = windows_smoke_matrix_report()["snapshot_artifact_matrix"]
    by_id = {artifact["id"]: artifact for artifact in matrix["artifacts"]}

    assert_payload_schema(matrix, WINDOWS_SNAPSHOT_ARTIFACT_MATRIX_SCHEMA)
    assert_summary_counts(matrix, {"artifact_count": 7, "execution_enabled_count": 0})
    assert_field_values(
        matrix["release_gate"],
        {
            "requires_admin_and_standard_user_evidence": True,
            "requires_managed_and_unmanaged_evidence": True,
            "requires_package_manager_presence_matrix": True,
            "allows_synthetic_fixture_only": False,
        },
    )
    assert_contains_all(
        by_id,
        [
            "appx-package-snapshot",
            "provisioned-appx-package-snapshot",
            "registry-export-artifact",
            "scheduled-task-xml-artifact",
            "service-config-artifact",
            "dism-component-store-analysis",
            "package-manager-inventory-artifacts",
        ],
    )
    assert_contains_all(by_id["appx-package-snapshot"]["windows_versions"], ["Windows 10 22H2", "Windows 11 24H2"])
    assert_contains_all(by_id["appx-package-snapshot"]["host_contexts"], ["managed-device", "unmanaged-device"])
    assert_contains_all(
        by_id["package-manager-inventory-artifacts"]["package_manager_contexts"],
        ["winget-present", "scoop-present", "chocolatey-present", "package-manager-absent"],
    )


def test_windows_smoke_matrix_covers_readonly_debloat_startup_and_health(assert_contains_all: AssertContainsAll) -> None:
    report = windows_smoke_matrix_report()
    by_id = {scenario["id"]: scenario for scenario in report["scenarios"]}

    privacy = by_id["debloat-privacy-readonly-baseline"]
    assert_contains_all(privacy["commands"], [["python", "cleanwin.py", "--json", "debloat-privacy-report"]])
    assert_contains_all(privacy["required_evidence"], ["registry_privacy_evidence_schema", "registry_export_required"])

    startup = by_id["startup-service-task-readonly-inventory"]
    assert_contains_all(startup["commands"], [["python", "cleanwin.py", "--json", "startup-service-inventory"]])
    assert_contains_all(startup["required_evidence"], ["service_registry_export_required", "scheduled_task_xml_export_required"])

    health = by_id["system-health-readonly-diagnostics"]
    assert_contains_all(health["commands"], [["python", "cleanwin.py", "--json", "system-health-report"]])
    assert_contains_all(health["required_evidence"], ["dism_scanhealth_only", "repair_flags_absent"])


def test_cli_ai_provider_and_schema_registry_expose_windows_smoke_matrix(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("windows-smoke-matrix", WINDOWS_SMOKE_MATRIX_SCHEMA)
