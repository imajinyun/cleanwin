from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

import pytest

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import tool_catalog
from cleanwincli.execution_contracts import (
    BACKUP_DELETE_CONTRACT_SCHEMA,
    DISABLE_REVERT_CONTRACT_SCHEMA,
    PERMANENT_DELETE_DENIAL_SCHEMA,
    backup_delete_contract_report,
    disable_revert_contract_report,
    permanent_delete_denial_report,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]


def test_disable_revert_contract_is_non_executable(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = disable_revert_contract_report()

    assert_readonly_report(report, DISABLE_REVERT_CONTRACT_SCHEMA)
    assert_summary_counts(report, {"execution_enabled_count": 0})
    assert_execution_disabled(report["execution_gate"], "disable_revert_execution_enabled", "ai_auto_call_allowed")
    assert_any_text_contains(report["non_goals"], "does not disable startup")


def test_disable_revert_contracts_require_snapshots_and_revert_metadata(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = disable_revert_contract_report()
    by_id = {contract["id"]: contract for contract in report["action_contracts"]}

    assert_contains_all(
        by_id,
        [
            "disable-revert.startup-entry",
            "disable-revert.service",
            "disable-revert.scheduled-task",
            "disable-revert.policy",
        ],
    )
    assert_contains_all(by_id["disable-revert.startup-entry"]["required_snapshots"], ["registry-export"])
    assert_contains_all(by_id["disable-revert.service"]["required_snapshots"], ["service-state"])
    assert_contains_all(by_id["disable-revert.scheduled-task"]["required_snapshots"], ["scheduled-task-state"])
    assert_contains_all(by_id["disable-revert.policy"]["required_rollback_metadata"], ["previous_value"])
    for contract in report["action_contracts"]:
        assert_execution_disabled(contract)


def test_backup_delete_contract_requires_backup_identity_and_audit_refs(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = backup_delete_contract_report()

    assert_readonly_report(report, BACKUP_DELETE_CONTRACT_SCHEMA)
    assert_summary_counts(report, {"execution_enabled_count": 0})
    assert_execution_disabled(report["execution_gate"], "backup_delete_execution_enabled")
    assert report["execution_gate"]["requires_pre_delete_backup"] is True
    assert report["execution_gate"]["requires_backup_verification"] is True
    assert report["execution_gate"]["requires_operation_log"] is True

    by_id = {scope["id"]: scope for scope in report["backup_scopes"]}
    assert_contains_all(by_id, ["backup-delete.file-tree", "backup-delete.registry-key"])
    assert_contains_all(by_id["backup-delete.file-tree"]["required_identity"], ["cleanwin.filesystem-identity.v1"])
    assert_contains_all(by_id["backup-delete.file-tree"]["required_backup_metadata"], ["verification_digest"])
    assert_contains_all(by_id["backup-delete.registry-key"]["required_audit_refs"], ["operation_log_ref"])
    for scope in report["backup_scopes"]:
        assert_execution_disabled(scope)


def test_permanent_delete_denial_contract_keeps_irreversible_delete_disabled(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    report = permanent_delete_denial_report()

    assert_readonly_report(report, PERMANENT_DELETE_DENIAL_SCHEMA)
    assert report["capability"]["risk"] == "critical"
    assert report["capability"]["default_state"] == "denied"
    assert_execution_disabled(report["capability"], "ai_auto_call_allowed")
    assert report["capability"]["mcp_tool_exposed"] is False
    assert report["capability"]["allowed_delete_modes"] == ["recycle"]
    assert report["capability"]["denied_delete_modes"] == ["permanent"]
    assert_summary_counts(report, {"execution_enabled_count": 0})
    assert report["current_enforcement"]["plan_validation_rejects_permanent"] is True
    assert report["current_enforcement"]["execute_plan_passes_allow_permanent_false"] is True
    assert report["current_enforcement"]["ai_host_policy_requires_recycle"] is True
    assert report["current_enforcement"]["mcp_execute_schema_allows_recycle_only"] is True
    assert report["current_enforcement"]["delete_ops_requires_allow_permanent_true"] is True


@pytest.mark.parametrize(
    ("command", "schema"),
    [
        ("disable-revert-contract", DISABLE_REVERT_CONTRACT_SCHEMA),
        ("backup-delete-contract", BACKUP_DELETE_CONTRACT_SCHEMA),
        ("permanent-delete-denial", PERMANENT_DELETE_DENIAL_SCHEMA),
    ],
)
def test_cli_provider_and_schema_registry_expose_execution_contracts(
    command: str,
    schema: str,
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    sample = assert_cli_provider_schema_sample(command, schema)
    if schema == PERMANENT_DELETE_DENIAL_SCHEMA:
        assert_execution_disabled(sample["capability"])


def test_ai_host_and_execute_schema_continue_to_deny_permanent_delete(
    assert_payload_status_false: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    tool = next(tool for tool in tool_catalog()["tools"] if tool["name"] == "cleanwin_execute_plan")

    delete_mode = tool["parameters"]["properties"]["delete_mode"]
    assert delete_mode["enum"] == ["recycle"]

    denied = evaluate_ai_host_tool_call(
        tool=tool,
        arguments={
            "delete_mode": "permanent",
            "operation_log": "ops.jsonl",
            "confirmation_phrase": "确认执行 cleanwin 清理",
            "confirmation_token": "token",
            "require_plan_context": True,
        },
        source="test",
    )
    assert_payload_status_false(denied, "allowed")
    assert_contains_all({reason["code"] for reason in denied["blocking_reasons"]}, ["RECYCLE_MODE_REQUIRED"])
