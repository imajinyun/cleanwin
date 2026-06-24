from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.official_commands import OFFICIAL_COMMAND_PLAN_SCHEMA, official_command_plan_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def test_report_is_non_destructive_and_blocks_auto_execution() -> None:
    report = official_command_plan_report()

    assert report["schema"] == OFFICIAL_COMMAND_PLAN_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["execution_gate"]["system_execution_enabled"] is False
    assert report["execution_gate"]["ai_auto_call_allowed"] is False
    assert any("does not execute DISM" in item for item in report["non_goals"])
    assert report["summary"]["auto_executable_count"] == 0


def test_report_covers_windows_owned_cleanup_surfaces() -> None:
    report = official_command_plan_report()
    by_id = {command["id"]: command for command in report["commands"]}

    assert "windows.component-cleanup.dism-startcomponentcleanup" in by_id
    assert "windows.update-cache.storage-sense" in by_id
    assert "windows.delivery-optimization.settings" in by_id
    assert "windows.wer.disk-cleanup" in by_id
    assert "windows.thumbnail-cache.disk-cleanup" in by_id
    assert "windows.defender.cleanup-settings" in by_id
    assert "windows.memory-dumps.storage-settings" in by_id
    assert "/StartComponentCleanup" in by_id["windows.component-cleanup.dism-startcomponentcleanup"]["command"]
    assert "system-restore-point" in by_id["windows.component-cleanup.dism-startcomponentcleanup"]["required_snapshots"]
    assert all(not command["executes_by_report"] for command in report["commands"])
    assert all(not command["auto_executable"] for command in report["commands"])


def test_cli_and_ai_provider_expose_official_command_plan(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("official-command-plan")
    assert cli["schema"] == OFFICIAL_COMMAND_PLAN_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "official-command-plan")
    assert provider["schema"] == OFFICIAL_COMMAND_PLAN_SCHEMA
