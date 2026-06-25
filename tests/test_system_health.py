from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.system_health import SYSTEM_HEALTH_REPORT_SCHEMA, system_health_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[list[str]], dict[str, JSONPayload]]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertSafeToExecuteDisabled = Callable[[JSONPayload], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
AssertAllMatch = Callable[[Sequence[JSONPayload], Callable[[JSONPayload], bool]], Sequence[JSONPayload]]


def test_system_health_report_is_read_only_and_gated(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = system_health_report()

    assert_readonly_report(report, SYSTEM_HEALTH_REPORT_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "system_repair_execution_enabled", "ai_auto_call_allowed")
    assert_summary_counts(report, {"auto_executable_count": 0})
    assert_any_text_contains(report["non_goals"], "does not execute DISM")


def test_system_health_recommendations_use_official_tools_without_execution(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_contains_all: AssertContainsAll,
    assert_all_match: AssertAllMatch,
) -> None:
    report = system_health_report()
    by_id = {item["id"]: item for item in report["recommendations"]}

    assert_contains_all(
        by_id,
        [
            "health.component-store.dism-scanhealth",
            "health.system-files.sfc-scannow",
            "health.disk.chkdsk-scan",
            "health.windows-update.troubleshooter",
        ],
    )
    assert by_id["health.component-store.dism-scanhealth"]["commands"][0][0] == "dism.exe"
    assert by_id["health.system-files.sfc-scannow"]["commands"][0] == ["sfc.exe", "/scannow"]
    for item in report["recommendations"]:
        assert_execution_disabled(item)
        assert_safe_to_execute_disabled(item)
    assert_all_match(report["recommendations"], lambda item: item["evidence_required"])


def test_cli_provider_and_schema_registry_expose_system_health(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample, assert_schema_samples: AssertSchemaSamples
) -> None:
    assert_cli_provider_schema_sample("system-health-report", SYSTEM_HEALTH_REPORT_SCHEMA)
    assert_schema_samples(["cleanwin.registry-privacy-evidence.v1"])
