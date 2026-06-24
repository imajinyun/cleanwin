from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cleanwincli.debloat_privacy import DEBLOAT_PRIVACY_REPORT_SCHEMA, debloat_privacy_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def test_report_is_non_destructive_and_gated() -> None:
    report = debloat_privacy_report(raw_registry_values={}, raw_appx_packages=[], env={})

    assert report["schema"] == DEBLOAT_PRIVACY_REPORT_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["execution_gate"]["system_execution_enabled"] is False
    assert report["execution_gate"]["requires_registry_export"] is True
    assert any("does not remove AppX" in item for item in report["non_goals"])


def test_registry_policy_values_are_classified() -> None:
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
    assert by_id["privacy.telemetry.allow-telemetry"]["safe_to_execute"] is False
    evidence = by_id["privacy.telemetry.allow-telemetry"]["change_evidence"]
    assert evidence["schema"] == "cleanwin.registry-privacy-evidence.v1"
    assert evidence["hive"] == "HKLM"
    assert evidence["value_name"] == "AllowTelemetry"
    assert evidence["required_export_command"][:2] == ["reg.exe", "export"]
    assert "previous_value" in evidence["rollback_metadata_required"]
    assert report["summary"]["review_recommended_count"] == 1
    assert report["summary"]["privacy_hardened_count"] == 1


def test_appx_and_oem_findings_are_review_only(tmp_path: Path) -> None:
    program_files = tmp_path / "Program Files"
    support_assist = program_files / "Dell" / "SupportAssistAgent"
    support_assist.mkdir(parents=True)

    report = debloat_privacy_report(
        raw_registry_values={},
        raw_appx_packages=[{"Name": "Microsoft.XboxGamingOverlay", "Publisher": "CN=Microsoft", "Version": "1.0.0.0"}],
        env={"PROGRAMFILES": str(program_files)},
    )

    appx_findings = [finding for finding in report["findings"] if finding["kind"] == "appx-package"]
    oem_findings = [finding for finding in report["findings"] if finding["kind"] == "oem-app-location"]
    assert len(appx_findings) == 1
    assert appx_findings[0]["state"] == "review-recommended"
    assert appx_findings[0]["safe_to_execute"] is False
    assert len(oem_findings) == 1
    assert "SupportAssistAgent" in oem_findings[0]["path"]
    assert report["summary"]["appx_review_count"] == 1
    assert report["summary"]["oem_location_count"] == 1


def test_cli_and_ai_provider_expose_report(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("debloat-privacy-report")
    assert cli["schema"] == DEBLOAT_PRIVACY_REPORT_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "debloat-privacy-report")
    assert provider["schema"] == DEBLOAT_PRIVACY_REPORT_SCHEMA
