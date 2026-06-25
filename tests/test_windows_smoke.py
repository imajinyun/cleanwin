from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.windows_smoke import WINDOWS_SMOKE_MATRIX_SCHEMA, windows_smoke_matrix_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]


def test_windows_smoke_matrix_is_non_destructive_release_gate(
    assert_readonly_report: AssertReadonlyReport,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    report = windows_smoke_matrix_report()

    assert_readonly_report(report, WINDOWS_SMOKE_MATRIX_SCHEMA)
    assert_summary_counts(report, {"destructive_scenario_count": 0})
    assert report["release_gate"]["required_before_execution_expansion"] is True
    assert report["release_gate"]["requires_windows_10_evidence"] is True
    assert report["release_gate"]["requires_windows_11_evidence"] is True
    assert report["release_gate"]["allows_synthetic_fixture_only"] is False


def test_windows_smoke_matrix_covers_expected_edge_scenarios() -> None:
    report = windows_smoke_matrix_report()
    by_id = {scenario["id"]: scenario for scenario in report["scenarios"]}

    assert "win10-win11-standard-user-safe-preview" in by_id
    assert "admin-official-command-and-recovery-readiness" in by_id
    assert "onedrive-known-folders-and-user-data-protection" in by_id
    assert "browser-profile-lock-and-sensitive-exclusion" in by_id
    assert "wsl-docker-visual-studio-report-only" in by_id
    assert "filesystem-edge-cases" in by_id

    filesystem = by_id["filesystem-edge-cases"]
    assert "symlink_rejected" in filesystem["required_evidence"]
    assert "junction_rejected" in filesystem["required_evidence"]
    assert "non_english_path_handled" in filesystem["required_evidence"]

    browser = by_id["browser-profile-lock-and-sensitive-exclusion"]
    assert ["python", "cleanwin.py", "--json", "browser-profile-inventory"] in browser["commands"]
    assert "sensitive_exclusions" in browser["required_evidence"]


def test_cli_ai_provider_and_schema_registry_expose_windows_smoke_matrix(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("windows-smoke-matrix", WINDOWS_SMOKE_MATRIX_SCHEMA)
