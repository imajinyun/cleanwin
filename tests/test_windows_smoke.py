from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.windows_smoke import WINDOWS_SMOKE_MATRIX_SCHEMA, windows_smoke_matrix_report

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


def test_cli_ai_provider_and_schema_registry_expose_windows_smoke_matrix(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("windows-smoke-matrix", WINDOWS_SMOKE_MATRIX_SCHEMA)
