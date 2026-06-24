from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import tool_catalog
from cleanwincli.ai_versioning import schema_registry, schema_sample
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


def test_disable_revert_contract_is_non_executable() -> None:
    report = disable_revert_contract_report()

    assert report["schema"] == DISABLE_REVERT_CONTRACT_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["summary"]["execution_enabled_count"] == 0
    assert report["execution_gate"]["disable_revert_execution_enabled"] is False
    assert report["execution_gate"]["ai_auto_call_allowed"] is False
    assert any("does not disable startup" in item for item in report["non_goals"])


def test_disable_revert_contracts_require_snapshots_and_revert_metadata() -> None:
    report = disable_revert_contract_report()
    by_id = {contract["id"]: contract for contract in report["action_contracts"]}

    assert "disable-revert.startup-entry" in by_id
    assert "disable-revert.service" in by_id
    assert "disable-revert.scheduled-task" in by_id
    assert "disable-revert.policy" in by_id
    assert "registry-export" in by_id["disable-revert.startup-entry"]["required_snapshots"]
    assert "service-state" in by_id["disable-revert.service"]["required_snapshots"]
    assert "scheduled-task-state" in by_id["disable-revert.scheduled-task"]["required_snapshots"]
    assert "previous_value" in by_id["disable-revert.policy"]["required_rollback_metadata"]
    assert all(contract["execution_enabled"] is False for contract in report["action_contracts"])
    assert all(contract["auto_executable"] is False for contract in report["action_contracts"])


def test_cli_provider_and_schema_registry_expose_disable_revert_contract(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("disable-revert-contract")
    assert cli["schema"] == DISABLE_REVERT_CONTRACT_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "disable-revert-contract")
    assert provider["schema"] == DISABLE_REVERT_CONTRACT_SCHEMA

    registry = schema_registry()
    assert DISABLE_REVERT_CONTRACT_SCHEMA in {entry["name"] for entry in registry["entries"]}
    sample = schema_sample(DISABLE_REVERT_CONTRACT_SCHEMA)
    assert sample is not None
    assert sample["schema"] == DISABLE_REVERT_CONTRACT_SCHEMA


def test_backup_delete_contract_requires_backup_identity_and_audit_refs() -> None:
    report = backup_delete_contract_report()

    assert report["schema"] == BACKUP_DELETE_CONTRACT_SCHEMA
    assert report["destructive"] is False
    assert report["executes_system_commands"] is False
    assert report["summary"]["execution_enabled_count"] == 0
    assert report["execution_gate"]["backup_delete_execution_enabled"] is False
    assert report["execution_gate"]["requires_pre_delete_backup"] is True
    assert report["execution_gate"]["requires_backup_verification"] is True
    assert report["execution_gate"]["requires_operation_log"] is True

    by_id = {scope["id"]: scope for scope in report["backup_scopes"]}
    assert "backup-delete.file-tree" in by_id
    assert "backup-delete.registry-key" in by_id
    assert "cleanwin.filesystem-identity.v1" in by_id["backup-delete.file-tree"]["required_identity"]
    assert "verification_digest" in by_id["backup-delete.file-tree"]["required_backup_metadata"]
    assert "operation_log_ref" in by_id["backup-delete.registry-key"]["required_audit_refs"]
    assert all(scope["execution_enabled"] is False for scope in report["backup_scopes"])
    assert all(scope["auto_executable"] is False for scope in report["backup_scopes"])


def test_cli_provider_and_schema_registry_expose_backup_delete_contract(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("backup-delete-contract")
    assert cli["schema"] == BACKUP_DELETE_CONTRACT_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "backup-delete-contract")
    assert provider["schema"] == BACKUP_DELETE_CONTRACT_SCHEMA

    registry = schema_registry()
    assert BACKUP_DELETE_CONTRACT_SCHEMA in {entry["name"] for entry in registry["entries"]}
    sample = schema_sample(BACKUP_DELETE_CONTRACT_SCHEMA)
    assert sample is not None
    assert sample["schema"] == BACKUP_DELETE_CONTRACT_SCHEMA


def test_permanent_delete_denial_contract_keeps_irreversible_delete_disabled() -> None:
    report = permanent_delete_denial_report()

    assert report["schema"] == PERMANENT_DELETE_DENIAL_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["capability"]["risk"] == "critical"
    assert report["capability"]["default_state"] == "denied"
    assert report["capability"]["execution_enabled"] is False
    assert report["capability"]["ai_auto_call_allowed"] is False
    assert report["capability"]["mcp_tool_exposed"] is False
    assert report["capability"]["allowed_delete_modes"] == ["recycle"]
    assert report["capability"]["denied_delete_modes"] == ["permanent"]
    assert report["summary"]["execution_enabled_count"] == 0
    assert report["current_enforcement"]["plan_validation_rejects_permanent"] is True
    assert report["current_enforcement"]["execute_plan_passes_allow_permanent_false"] is True
    assert report["current_enforcement"]["ai_host_policy_requires_recycle"] is True
    assert report["current_enforcement"]["mcp_execute_schema_allows_recycle_only"] is True
    assert report["current_enforcement"]["delete_ops_requires_allow_permanent_true"] is True


def test_cli_provider_and_schema_registry_expose_permanent_delete_denial(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("permanent-delete-denial")
    assert cli["schema"] == PERMANENT_DELETE_DENIAL_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "permanent-delete-denial")
    assert provider["schema"] == PERMANENT_DELETE_DENIAL_SCHEMA

    registry = schema_registry()
    assert PERMANENT_DELETE_DENIAL_SCHEMA in {entry["name"] for entry in registry["entries"]}
    sample = schema_sample(PERMANENT_DELETE_DENIAL_SCHEMA)
    assert sample is not None
    assert sample["schema"] == PERMANENT_DELETE_DENIAL_SCHEMA
    assert sample["capability"]["execution_enabled"] is False


def test_ai_host_and_execute_schema_continue_to_deny_permanent_delete() -> None:
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
    assert denied["allowed"] is False
    assert "RECYCLE_MODE_REQUIRED" in {reason["code"] for reason in denied["blocking_reasons"]}
