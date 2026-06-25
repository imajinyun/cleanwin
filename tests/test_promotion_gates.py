from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.promotion_gates import PROMOTION_GATES_SCHEMA, promotion_gates_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]


def test_promotion_gates_are_non_destructive_and_keep_system_execution_disabled(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    report = promotion_gates_report()

    assert_readonly_report(report, PROMOTION_GATES_SCHEMA)
    assert_execution_disabled(report)
    assert_summary_counts(report, {"report_only_gate_count": 4})
    assert any("does not enable registry" in item for item in report["non_goals"])


def test_promotion_gates_cover_high_risk_report_surfaces(
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    report = promotion_gates_report()
    by_id = {gate["id"]: gate for gate in report["gates"]}

    assert "registry-privacy-to-registry-change" in by_id
    assert "startup-entry-to-disable-plan" in by_id
    assert "service-task-to-disable-plan" in by_id
    assert "official-command-to-executable-action" in by_id
    assert "browser-profile-to-cache-plan" in by_id

    registry_gate = by_id["registry-privacy-to-registry-change"]
    assert registry_gate["default_state"] == "report-only"
    assert_execution_disabled(registry_gate, "ai_auto_call_allowed")
    assert "registry-export" in registry_gate["required_snapshots"]
    assert "rollback-metadata-validation" in registry_gate["required_tests"]

    browser_gate = by_id["browser-profile-to-cache-plan"]
    assert browser_gate["default_state"] == "low-risk-cache-only"
    assert browser_gate["ai_auto_call_allowed"] is True
    assert "sensitive_exclusions" in browser_gate["required_evidence"]


def test_cli_ai_provider_and_schema_registry_expose_promotion_gates(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("promotion-gates", PROMOTION_GATES_SCHEMA)
