from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.system_health import SYSTEM_HEALTH_REPORT_SCHEMA, system_health_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchema = Callable[[str, str], None]
AssertSchemaSample = Callable[[str], JSONPayload]


def test_system_health_report_is_read_only_and_gated() -> None:
    report = system_health_report()

    assert report["schema"] == SYSTEM_HEALTH_REPORT_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["execution_gate"]["system_repair_execution_enabled"] is False
    assert report["execution_gate"]["ai_auto_call_allowed"] is False
    assert report["summary"]["auto_executable_count"] == 0
    assert any("does not execute DISM" in item for item in report["non_goals"])


def test_system_health_recommendations_use_official_tools_without_execution() -> None:
    report = system_health_report()
    by_id = {item["id"]: item for item in report["recommendations"]}

    assert "health.component-store.dism-scanhealth" in by_id
    assert "health.system-files.sfc-scannow" in by_id
    assert "health.disk.chkdsk-scan" in by_id
    assert "health.windows-update.troubleshooter" in by_id
    assert by_id["health.component-store.dism-scanhealth"]["commands"][0][0] == "dism.exe"
    assert by_id["health.system-files.sfc-scannow"]["commands"][0] == ["sfc.exe", "/scannow"]
    assert all(item["executes_by_report"] is False for item in report["recommendations"])
    assert all(item["safe_to_execute"] is False for item in report["recommendations"])
    assert all(item["evidence_required"] for item in report["recommendations"])


def test_cli_provider_and_schema_registry_expose_system_health(
    assert_cli_provider_schema: AssertCliProviderSchema, assert_schema_sample: AssertSchemaSample
) -> None:
    assert_cli_provider_schema("system-health-report", SYSTEM_HEALTH_REPORT_SCHEMA)
    assert_schema_sample(SYSTEM_HEALTH_REPORT_SCHEMA)
    assert_schema_sample("cleanwin.registry-privacy-evidence.v1")
