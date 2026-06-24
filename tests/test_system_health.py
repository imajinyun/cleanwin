from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.ai_versioning import schema_registry, schema_sample
from cleanwincli.system_health import SYSTEM_HEALTH_REPORT_SCHEMA, system_health_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


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


def test_cli_provider_and_schema_registry_expose_system_health(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("system-health-report")
    assert cli["schema"] == SYSTEM_HEALTH_REPORT_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "system-health-report")
    assert provider["schema"] == SYSTEM_HEALTH_REPORT_SCHEMA

    registry = schema_registry()
    assert SYSTEM_HEALTH_REPORT_SCHEMA in {entry["name"] for entry in registry["entries"]}
    assert "cleanwin.registry-privacy-evidence.v1" in {entry["name"] for entry in registry["entries"]}
    health_sample = schema_sample(SYSTEM_HEALTH_REPORT_SCHEMA)
    evidence_sample = schema_sample("cleanwin.registry-privacy-evidence.v1")
    assert health_sample is not None
    assert evidence_sample is not None
    assert health_sample["schema"] == SYSTEM_HEALTH_REPORT_SCHEMA
    assert evidence_sample["schema"] == "cleanwin.registry-privacy-evidence.v1"
