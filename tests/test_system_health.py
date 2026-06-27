from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.system_health import (
    SYSTEM_HEALTH_EVIDENCE_SCHEMA,
    SYSTEM_HEALTH_REPORT_SCHEMA,
    parse_dism_analyze_component_store,
    parse_dism_health_output,
    parse_pending_reboot_query,
    system_health_evidence_report,
    system_health_report,
)

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
AssertExactSequence = Callable[[Sequence[Any], Sequence[Any]], Sequence[Any]]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]


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
    assert_exact_sequence: AssertExactSequence,
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
            "health.component-store.dism-checkhealth",
            "health.windows-update.pending-reboot-review",
        ],
    )
    assert_exact_sequence(by_id["health.component-store.dism-scanhealth"]["commands"][0][:1], ["dism.exe"])
    assert_exact_sequence(by_id["health.component-store.dism-checkhealth"]["commands"][0], ["dism.exe", "/Online", "/Cleanup-Image", "/CheckHealth"])
    assert_exact_sequence(by_id["health.system-files.sfc-scannow"]["commands"][0], ["sfc.exe", "/scannow"])
    assert_contains_all(by_id["health.windows-update.pending-reboot-review"]["evidence_required"], ["CBS RebootPending query result"])
    for item in report["recommendations"]:
        assert_execution_disabled(item)
        assert_safe_to_execute_disabled(item)
    assert_all_match(report["recommendations"], lambda item: item["evidence_required"])


def test_cli_provider_and_schema_registry_expose_system_health(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample, assert_schema_samples: AssertSchemaSamples
) -> None:
    assert_cli_provider_schema_sample("system-health-report", SYSTEM_HEALTH_REPORT_SCHEMA)
    assert_schema_samples(
        [
            "cleanwin.registry-privacy-evidence.v1",
            SYSTEM_HEALTH_EVIDENCE_SCHEMA,
            "cleanwin.dism-component-store-analysis.v1",
            "cleanwin.dism-health-evidence.v1",
            "cleanwin.pending-reboot-registry-evidence.v1",
        ]
    )


def test_dism_component_store_parser_extracts_cleanup_evidence(assert_field_values: AssertFieldValues) -> None:
    evidence = parse_dism_analyze_component_store(
        """
Windows Explorer Reported Size of Component Store : 8.35 GB
Actual Size of Component Store : 7.25 GB
Shared with Windows : 5.10 GB
Backups and Disabled Features : 1.80 GB
Cache and Temporary Data : 350.00 MB
Date of Last Cleanup : 2026-06-01 12:00:00
Component Store Cleanup Recommended : Yes
"""
    )

    assert_field_values(
        evidence,
        {
            "schema": "cleanwin.dism-component-store-analysis.v1",
            "cleanup_recommended": True,
            "actual_component_store_size": "7.25 GB",
            "safe_to_execute": False,
        },
    )


def test_dism_health_parser_classifies_repairable_and_healthy_states(assert_field_values: AssertFieldValues) -> None:
    repairable = parse_dism_health_output(
        "The component store is repairable.\nThe operation completed successfully.",
        parser="dism-scanhealth",
    )
    healthy = parse_dism_health_output(
        "No component store corruption detected.\nThe operation completed successfully.",
        parser="dism-checkhealth",
    )

    assert_field_values(repairable, {"health_state": "repairable", "requires_repair_review": True})
    assert_field_values(healthy, {"health_state": "healthy", "requires_repair_review": False})


def test_pending_reboot_query_parser_marks_present_keys(assert_field_values: AssertFieldValues) -> None:
    evidence = parse_pending_reboot_query(
        {
            "id": "windows-update-reboot-required",
            "command": ["reg", "query", r"HKLM\...\RebootRequired"],
            "exit_code": 0,
            "stdout": r"HKEY_LOCAL_MACHINE\...\RebootRequired",
            "stderr": "",
        }
    )

    assert_field_values(
        evidence,
        {
            "schema": "cleanwin.pending-reboot-registry-evidence.v1",
            "state": "pending-reboot",
            "key_present": True,
            "safe_to_execute": False,
        },
    )


def test_system_health_evidence_report_is_read_only_and_summarizes_findings(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = system_health_evidence_report(
        analyze_component_store_output="Component Store Cleanup Recommended : Yes",
        scanhealth_output="The component store is repairable.\nThe operation completed successfully.",
        pending_reboot_queries=[
            {
                "id": "cbs-reboot-pending",
                "command": ["reg", "query", r"HKLM\...\RebootPending"],
                "exit_code": 0,
                "stdout": r"HKEY_LOCAL_MACHINE\...\RebootPending",
                "stderr": "",
            }
        ],
    )

    assert_readonly_report(report, SYSTEM_HEALTH_EVIDENCE_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "system_repair_execution_enabled", "system_cleanup_execution_enabled", "ai_auto_call_allowed")
    assert_summary_counts(
        report,
        {
            "evidence_count": 3,
            "dism_evidence_count": 2,
            "pending_reboot_key_count": 1,
            "cleanup_recommended_count": 1,
            "repair_review_count": 1,
        },
    )
    assert_contains_all(
        {finding["id"] for finding in report["findings"]},
        [
            "finding.component-store.cleanup-recommended",
            "finding.component-store.repair-review",
            "finding.pending-reboot.cbs-reboot-pending",
        ],
    )
