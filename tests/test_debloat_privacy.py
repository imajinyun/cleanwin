from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any

from cleanwincli.debloat_privacy import DEBLOAT_PRIVACY_REPORT_SCHEMA, debloat_privacy_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertSafeToExecuteDisabled = Callable[[JSONPayload], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]


def test_report_is_non_destructive_and_gated(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = debloat_privacy_report(raw_registry_values={}, raw_appx_packages=[], env={})

    assert_readonly_report(report, DEBLOAT_PRIVACY_REPORT_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "system_execution_enabled")
    assert report["execution_gate"]["requires_registry_export"] is True
    assert_any_text_contains(report["non_goals"], "does not remove AppX")


def test_registry_policy_values_are_classified(
    assert_payload_schema: AssertPayloadSchema,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = debloat_privacy_report(
        raw_registry_values={
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection\AllowTelemetry": 3,
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo\Enabled": 0,
        },
        raw_appx_packages=[],
        env={},
    )
    by_id = {finding["id"]: finding for finding in report["findings"]}

    assert by_id["privacy.telemetry.allow-telemetry"]["state"] == "review-recommended"
    assert by_id["privacy.ad-id.disabled"]["state"] == "privacy-hardened"
    assert_safe_to_execute_disabled(by_id["privacy.telemetry.allow-telemetry"])
    evidence = by_id["privacy.telemetry.allow-telemetry"]["change_evidence"]
    assert_payload_schema(evidence, "cleanwin.registry-privacy-evidence.v1")
    assert evidence["hive"] == "HKLM"
    assert evidence["value_name"] == "AllowTelemetry"
    assert evidence["required_export_command"][:2] == ["reg.exe", "export"]
    assert_contains_all(evidence["rollback_metadata_required"], ["previous_value"])
    assert_summary_counts(report, {"review_recommended_count": 1, "privacy_hardened_count": 1})


def test_appx_and_oem_findings_are_review_only(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    program_files = tmp_path / "Program Files"
    support_assist = program_files / "Dell" / "SupportAssistAgent"
    write_text_file(support_assist / "SupportAssist.exe", "exe")

    report = debloat_privacy_report(
        raw_registry_values={},
        raw_appx_packages=[{"Name": "Microsoft.XboxGamingOverlay", "Publisher": "CN=Microsoft", "Version": "1.0.0.0"}],
        env={"PROGRAMFILES": str(program_files)},
    )

    appx_findings = [finding for finding in report["findings"] if finding["kind"] == "appx-package"]
    oem_findings = [finding for finding in report["findings"] if finding["kind"] == "oem-app-location"]
    assert len(appx_findings) == 1
    assert appx_findings[0]["state"] == "review-recommended"
    assert_safe_to_execute_disabled(appx_findings[0])
    assert len(oem_findings) == 1
    assert_any_text_contains([oem_findings[0]["path"]], "SupportAssistAgent")
    assert_summary_counts(report, {"appx_review_count": 1, "oem_location_count": 1})


def test_cli_and_ai_provider_expose_report(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("debloat-privacy-report", DEBLOAT_PRIVACY_REPORT_SCHEMA)
