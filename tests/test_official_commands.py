from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.official_commands import OFFICIAL_COMMAND_PLAN_SCHEMA, official_command_plan_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]


def test_report_is_non_destructive_and_blocks_auto_execution(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = official_command_plan_report()

    assert_readonly_report(report, OFFICIAL_COMMAND_PLAN_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "system_execution_enabled", "ai_auto_call_allowed")
    assert_any_text_contains(report["non_goals"], "does not execute DISM")
    assert_summary_counts(
        report,
        {
            "auto_executable_count": 0,
            "action_contract_count": len(report["commands"]),
            "command_count": len(report["commands"]),
            "execution_enabled_action_count": 0,
        },
    )


def test_report_covers_windows_owned_cleanup_surfaces(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = official_command_plan_report()
    by_id = {command["id"]: command for command in report["commands"]}

    assert_contains_all(
        by_id,
        [
            "windows.component-cleanup.dism-startcomponentcleanup",
            "windows.update-cache.storage-sense",
            "windows.delivery-optimization.settings",
            "windows.wer.disk-cleanup",
            "windows.thumbnail-cache.disk-cleanup",
            "windows.defender.cleanup-settings",
            "windows.memory-dumps.storage-settings",
        ],
    )
    assert_contains_all(by_id["windows.component-cleanup.dism-startcomponentcleanup"]["command"], ["/StartComponentCleanup"])
    assert_contains_all(
        by_id["windows.component-cleanup.dism-startcomponentcleanup"]["required_snapshots"],
        ["system-restore-point"],
    )
    for command in report["commands"]:
        assert_execution_disabled(command)


def test_official_commands_include_structured_non_executable_action_contracts(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
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
    assert_contains_all(dism_contract["required_privileges"], ["administrator"])
    assert_contains_all(dism_contract["blocked_without"], ["recovery-readiness"])


def test_cli_and_ai_provider_expose_official_command_plan(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("official-command-plan", OFFICIAL_COMMAND_PLAN_SCHEMA)
