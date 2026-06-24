from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.windows_smoke import WINDOWS_SMOKE_MATRIX_SCHEMA, windows_smoke_matrix_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchema = Callable[[str, str], None]
AssertSchemaSample = Callable[[str], JSONPayload]


def test_windows_smoke_matrix_is_non_destructive_release_gate() -> None:
    report = windows_smoke_matrix_report()

    assert report["schema"] == WINDOWS_SMOKE_MATRIX_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["summary"]["destructive_scenario_count"] == 0
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
    assert_cli_provider_schema: AssertCliProviderSchema, assert_schema_sample: AssertSchemaSample
) -> None:
    assert_cli_provider_schema("windows-smoke-matrix", WINDOWS_SMOKE_MATRIX_SCHEMA)
    assert_schema_sample(WINDOWS_SMOKE_MATRIX_SCHEMA)
