from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.promotion_gates import PROMOTION_GATES_SCHEMA, promotion_gates_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_promotion_gates_are_non_destructive_and_keep_system_execution_disabled(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = promotion_gates_report()

    assert_readonly_report(report, PROMOTION_GATES_SCHEMA)
    assert_execution_disabled(report)
    assert_summary_counts(report, {"report_only_gate_count": 4})
    assert_any_text_contains(report["non_goals"], "does not enable registry")


def test_promotion_gates_cover_high_risk_report_surfaces(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = promotion_gates_report()
    by_id = {gate["id"]: gate for gate in report["gates"]}

    assert_contains_all(
        by_id,
        [
            "registry-privacy-to-registry-change",
            "startup-entry-to-disable-plan",
            "service-task-to-disable-plan",
            "official-command-to-executable-action",
            "browser-profile-to-cache-plan",
        ],
    )

    registry_gate = by_id["registry-privacy-to-registry-change"]
    assert_field_values(registry_gate, {"default_state": "report-only"})
    assert_execution_disabled(registry_gate, "ai_auto_call_allowed")
    assert_contains_all(registry_gate["required_snapshots"], ["registry-export"])
    assert_contains_all(registry_gate["required_tests"], ["rollback-metadata-validation"])

    browser_gate = by_id["browser-profile-to-cache-plan"]
    assert_field_values(browser_gate, {"default_state": "low-risk-cache-only", "ai_auto_call_allowed": True})
    assert_contains_all(browser_gate["required_evidence"], ["sensitive_exclusions"])


def test_cli_ai_provider_and_schema_registry_expose_promotion_gates(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("promotion-gates", PROMOTION_GATES_SCHEMA)
