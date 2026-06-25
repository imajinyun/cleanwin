from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.official_commands import OFFICIAL_COMMAND_PLAN_SCHEMA, official_command_plan_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[[JSONPayload], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]


def test_report_is_non_destructive_and_blocks_auto_execution(assert_readonly_report: AssertReadonlyReport) -> None:
    report = official_command_plan_report()

    assert_readonly_report(report, OFFICIAL_COMMAND_PLAN_SCHEMA)
    assert report["execution_gate"]["system_execution_enabled"] is False
    assert report["execution_gate"]["ai_auto_call_allowed"] is False
    assert any("does not execute DISM" in item for item in report["non_goals"])
    assert report["summary"]["auto_executable_count"] == 0
    assert report["summary"]["action_contract_count"] == report["summary"]["command_count"]
    assert report["summary"]["execution_enabled_action_count"] == 0


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


def test_official_commands_include_structured_non_executable_action_contracts(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    report = official_command_plan_report()

    for command in report["commands"]:
        contract = command["action_contract"]
        assert_payload_schema(contract, "cleanwin.official-action-contract.v1")
        assert contract["action_id"] == command["id"]
        assert contract["allowlisted_command"] == command["command"]
        assert contract["argument_policy"] == "exact-argv-only"
        assert_execution_disabled(contract)
        assert contract["requires_human_review"] is True
        assert contract["requires_matching_dry_run_token"] is True
        assert contract["expected_effects"]
        assert contract["forbidden_effects"]

    dism_contract = {
        command["id"]: command["action_contract"]
        for command in report["commands"]
    }["windows.component-cleanup.dism-startcomponentcleanup"]
    assert "administrator" in dism_contract["required_privileges"]
    assert "recovery-readiness" in dism_contract["blocked_without"]


def test_cli_and_ai_provider_expose_official_command_plan(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("official-command-plan", OFFICIAL_COMMAND_PLAN_SCHEMA)
