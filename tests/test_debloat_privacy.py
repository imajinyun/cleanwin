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
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertExactSequence = Callable[[Sequence[Any], Sequence[Any]], Sequence[Any]]
AssertExactCount = Callable[[Sequence[Any], int], Sequence[Any]]


def test_report_is_non_destructive_and_gated(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = debloat_privacy_report(raw_registry_values={}, raw_appx_packages=[], env={})

    assert_readonly_report(report, DEBLOAT_PRIVACY_REPORT_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "system_execution_enabled")
    assert_field_values(report["execution_gate"], {"requires_registry_export": True})
    assert_any_text_contains(report["non_goals"], "does not remove AppX")


def test_registry_policy_values_are_classified(
    assert_payload_schema: AssertPayloadSchema,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_exact_sequence: AssertExactSequence,
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

    assert_field_values(by_id["privacy.telemetry.allow-telemetry"], {"state": "review-recommended"})
    assert_field_values(by_id["privacy.ad-id.disabled"], {"state": "privacy-hardened"})
    assert_safe_to_execute_disabled(by_id["privacy.telemetry.allow-telemetry"])
    evidence = by_id["privacy.telemetry.allow-telemetry"]["change_evidence"]
    assert_payload_schema(evidence, "cleanwin.registry-privacy-evidence.v1")
    assert_field_values(evidence, {"hive": "HKLM", "value_name": "AllowTelemetry"})
    assert_exact_sequence(evidence["required_export_command"][:2], ["reg.exe", "export"])
    assert_contains_all(evidence["rollback_metadata_required"], ["previous_value"])
    assert_summary_counts(report, {"review_recommended_count": 1, "privacy_hardened_count": 1})


def test_extended_privacy_policy_surface_is_reported(
    assert_payload_schema: AssertPayloadSchema,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    report = debloat_privacy_report(
        raw_registry_values={
            r"HKCU\Software\Policies\Microsoft\Windows\WindowsAI\DisableAIDataAnalysis": 1,
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Privacy\TailoredExperiencesWithDiagnosticDataEnabled": 1,
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System\UploadUserActivities": 1,
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection\DisableDiagnosticDataViewer": 1,
        },
        raw_appx_packages=[],
        env={},
    )
    by_id = {finding["id"]: finding for finding in report["findings"]}

    recall = by_id["privacy.recall.disabled"]
    tailored = by_id["privacy.tailored-experiences.disabled"]
    upload = by_id["privacy.activity-history.upload-disabled"]
    viewer = by_id["privacy.diagnostic-data-viewer.disabled"]
    assert_field_values(recall, {"state": "privacy-hardened", "risk": "high"})
    assert_field_values(tailored, {"state": "review-recommended"})
    assert_field_values(upload, {"state": "review-recommended"})
    assert_field_values(viewer, {"state": "privacy-hardened"})
    assert_payload_schema(recall["change_evidence"], "cleanwin.registry-privacy-evidence.v1")
    assert_safe_to_execute_disabled(tailored)
    assert_summary_counts(report, {"registry_policy_count": 35, "privacy_hardened_count": 2})


def test_privatezilla_style_privacy_baseline_is_reported(
    assert_payload_schema: AssertPayloadSchema,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    report = debloat_privacy_report(
        raw_registry_values={
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors\DisableLocation": 1,
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam\Value": "Allow",
            r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System\EnableSmartScreen": 0,
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager\SilentInstalledAppsEnabled": 1,
            r"HKLM\SOFTWARE\Policies\Microsoft\Dsh\AllowNewsAndInterests": 0,
            r"HKCU\Software\Microsoft\Speech_OneCore\Settings\OnlineSpeechPrivacy\HasAccepted": 0,
            r"HKCU\Software\Policies\Microsoft\InputPersonalization\RestrictImplicitTextCollection": 0,
            r"HKLM\SOFTWARE\Policies\Microsoft\FindMyDevice\AllowFindMyDevice": 1,
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager\RotatingLockScreenEnabled": 0,
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager\SubscribedContent-338389Enabled": 1,
            r"HKLM\SOFTWARE\Policies\Microsoft\Edge\PersonalizationReportingEnabled": 0,
            r"HKLM\SOFTWARE\Policies\Microsoft\Edge\EdgeShoppingAssistantEnabled": 1,
        },
        raw_appx_packages=[],
        env={},
    )
    by_id = {finding["id"]: finding for finding in report["findings"]}

    assert_field_values(by_id["privacy.location.disabled"], {"state": "privacy-hardened"})
    assert_field_values(by_id["privacy.webcam-access.disabled"], {"state": "review-recommended"})
    assert_field_values(by_id["privacy.smartscreen.enabled"], {"state": "review-recommended", "risk": "high"})
    assert_field_values(by_id["privacy.silent-installed-apps.disabled"], {"state": "review-recommended"})
    assert_field_values(by_id["privacy.widgets.disabled"], {"state": "privacy-hardened"})
    assert_field_values(by_id["privacy.online-speech.disabled"], {"state": "privacy-hardened"})
    assert_field_values(by_id["privacy.implicit-text-collection.disabled"], {"state": "review-recommended"})
    assert_field_values(by_id["privacy.find-my-device.disabled"], {"state": "review-recommended"})
    assert_field_values(by_id["privacy.lock-screen-spotlight.disabled"], {"state": "privacy-hardened"})
    assert_field_values(by_id["privacy.third-party-suggestions.disabled"], {"state": "review-recommended"})
    assert_field_values(by_id["privacy.edge-personalization-reporting.disabled"], {"state": "privacy-hardened"})
    assert_field_values(by_id["privacy.edge-shopping-assistant.disabled"], {"state": "review-recommended"})
    assert_payload_schema(by_id["privacy.webcam-access.disabled"]["change_evidence"], "cleanwin.registry-privacy-evidence.v1")
    assert_safe_to_execute_disabled(by_id["privacy.smartscreen.enabled"])
    assert_summary_counts(report, {"registry_policy_count": 35, "privacy_hardened_count": 5})


def test_appx_and_oem_findings_are_review_only(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
    assert_exact_count: AssertExactCount,
) -> None:
    program_files = tmp_path / "Program Files"
    support_assist = program_files / "Dell" / "SupportAssistAgent"
    write_text_file(support_assist / "SupportAssist.exe", "exe")

    report = debloat_privacy_report(
        raw_registry_values={},
        raw_appx_packages=[
            {"Name": "Microsoft.XboxGamingOverlay", "Publisher": "CN=Microsoft", "Version": "1.0.0.0"},
            {"Name": "Microsoft.GetHelp", "Publisher": "CN=Microsoft", "Version": "1.0.0.0"},
        ],
        env={"PROGRAMFILES": str(program_files)},
    )

    appx_findings = [finding for finding in report["findings"] if finding["kind"] == "appx-package"]
    oem_findings = [finding for finding in report["findings"] if finding["kind"] == "oem-app-location"]
    assert_exact_count(appx_findings, 2)
    by_package = {finding["package"]["name"]: finding for finding in appx_findings}
    assert_field_values(by_package["Microsoft.XboxGamingOverlay"], {"state": "review-recommended", "review_category": "gaming"})
    assert_field_values(by_package["Microsoft.GetHelp"], {"matched_token": "gethelp", "review_category": "support"})
    assert_safe_to_execute_disabled(appx_findings[0])
    assert_exact_count(oem_findings, 1)
    assert_any_text_contains([oem_findings[0]["path"]], "SupportAssistAgent")
    assert_summary_counts(report, {"appx_review_count": 2, "oem_location_count": 1})


def test_cli_and_ai_provider_expose_report(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("debloat-privacy-report", DEBLOAT_PRIVACY_REPORT_SCHEMA)
