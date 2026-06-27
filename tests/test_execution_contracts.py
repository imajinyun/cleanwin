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
    REGISTRY_PRIVACY_CHANGE_SCHEMA,
    REGISTRY_PRIVACY_PLAN_SCHEMA,
    REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA,
    REGISTRY_PRIVACY_REVERT_SCHEMA,
    backup_delete_contract_report,
    disable_revert_contract_report,
    permanent_delete_denial_report,
    registry_privacy_change_plan_report,
    validate_registry_privacy_change_plan,
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
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]


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
    assert_contains_all(by_id["disable-revert.startup-entry"]["required_review_evidence"], ["target_path", "target_status"])
    assert_contains_all(by_id["disable-revert.service"]["required_snapshots"], ["service-state", "service-registry-export"])
    assert_contains_all(
        by_id["disable-revert.service"]["required_review_evidence"],
        ["target_status", "start_type_classification", "dependencies", "trigger_start", "recovery_actions"],
    )
    assert_contains_all(by_id["disable-revert.scheduled-task"]["required_snapshots"], ["scheduled-task-state", "scheduled-task-xml-export"])
    assert_contains_all(
        by_id["disable-revert.scheduled-task"]["required_review_evidence"],
        ["target_status", "run_as_user", "run_level", "xml_snapshot_required"],
    )
    assert_contains_all(by_id["disable-revert.policy"]["required_rollback_metadata"], ["previous_value"])
    for contract in report["action_contracts"]:
        assert_execution_disabled(contract)


def test_backup_delete_contract_requires_backup_identity_and_audit_refs(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = backup_delete_contract_report()

    assert_readonly_report(report, BACKUP_DELETE_CONTRACT_SCHEMA)
    assert_summary_counts(report, {"execution_enabled_count": 0})
    assert_execution_disabled(report["execution_gate"], "backup_delete_execution_enabled")
    assert_field_values(
        report["execution_gate"],
        {
            "requires_pre_delete_backup": True,
            "requires_backup_verification": True,
            "requires_operation_log": True,
        },
    )

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
    assert_field_values: AssertFieldValues,
) -> None:
    report = permanent_delete_denial_report()

    assert_readonly_report(report, PERMANENT_DELETE_DENIAL_SCHEMA)
    assert_field_values(
        report["capability"],
        {
            "risk": "critical",
            "default_state": "denied",
            "mcp_tool_exposed": False,
            "allowed_delete_modes": ["recycle"],
            "denied_delete_modes": ["permanent"],
        },
    )
    assert_execution_disabled(report["capability"], "ai_auto_call_allowed")
    assert_summary_counts(report, {"execution_enabled_count": 0})
    assert_field_values(
        report["current_enforcement"],
        {
            "plan_validation_rejects_permanent": True,
            "execute_plan_passes_allow_permanent_false": True,
            "ai_host_policy_requires_recycle": True,
            "mcp_execute_schema_allows_recycle_only": True,
            "delete_ops_requires_allow_permanent_true": True,
        },
    )


def test_registry_privacy_plan_is_simulation_only_and_revertible(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    source_report = {
        "schema": "cleanwin.debloat-privacy-report.v1",
        "findings": [
            {
                "id": "privacy.telemetry.allow-telemetry",
                "kind": "registry-policy",
                "risk": "high",
                "state": "review-recommended",
                "change_evidence": {
                    "hive": "HKLM",
                    "subkey_path": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                    "value_name": "AllowTelemetry",
                    "observed_value": "3",
                    "expected_private_values": ["0"],
                    "required_export_command": [
                        "reg.exe",
                        "export",
                        r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                        "<export-file.reg>",
                        "/y",
                    ],
                },
            }
        ],
    }

    report = assert_readonly_report(registry_privacy_change_plan_report(source_report), REGISTRY_PRIVACY_PLAN_SCHEMA)

    assert_summary_counts(
        report,
        {
            "change_count": 1,
            "execution_enabled_count": 0,
            "requires_registry_export_count": 1,
            "requires_owner_review_count": 1,
            "requires_dry_run_token_count": 1,
        },
    )
    assert_field_values(
        report["execution_gate"],
        {
            "registry_privacy_execution_enabled": False,
            "requires_registry_export": True,
            "requires_previous_value": True,
            "requires_managed_device_detection": True,
            "requires_policy_owner_review": True,
            "requires_matching_dry_run_token": True,
        },
    )
    change = assert_payload_schema(report["changes"][0], REGISTRY_PRIVACY_CHANGE_SCHEMA)
    assert_execution_disabled(change, "auto_executable", "safe_to_execute")
    assert_field_values(
        change,
        {
            "state": "simulated",
            "previous_value": "3",
            "target_value": "0",
            "managed_device_detection.required": True,
            "owner_review.required": True,
            "dry_run_confirmation.required": True,
        },
    )
    assert_contains_all(change["required_export_command"], ["reg.exe", "export"])
    assert_payload_schema(change["rollback"], REGISTRY_PRIVACY_REVERT_SCHEMA)
    assert_field_values(change["rollback"], {"previous_value": "3"})
    assert_field_values(report["validation"], {"valid": True})


def test_registry_privacy_plan_validator_reports_missing_evidence(
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = assert_payload_schema(
        validate_registry_privacy_change_plan(
            {
                "schema": REGISTRY_PRIVACY_PLAN_SCHEMA,
                "changes": [
                    {
                        "schema": REGISTRY_PRIVACY_CHANGE_SCHEMA,
                        "hive": "HKLM",
                        "subkey_path": "",
                        "value_name": "AllowTelemetry",
                        "target_value": "0",
                        "execution_enabled": True,
                    }
                ],
            }
        ),
        REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA,
    )

    assert_field_values(validation, {"valid": False})
    assert_contains_all(
        {violation["code"] for violation in validation["violations"]},
        [
            "MISSING_FIELD",
            "EXECUTION_MUST_STAY_DISABLED",
            "MANAGED_DEVICE_DETECTION_REQUIRED",
            "OWNER_REVIEW_REQUIRED",
            "DRY_RUN_TOKEN_REQUIRED",
            "ROLLBACK_PLAN_REQUIRED",
        ],
    )


@pytest.mark.parametrize(
    ("command", "schema"),
    [
        ("disable-revert-contract", DISABLE_REVERT_CONTRACT_SCHEMA),
        ("backup-delete-contract", BACKUP_DELETE_CONTRACT_SCHEMA),
        ("permanent-delete-denial", PERMANENT_DELETE_DENIAL_SCHEMA),
        ("registry-privacy-plan", REGISTRY_PRIVACY_PLAN_SCHEMA),
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
    if schema == REGISTRY_PRIVACY_PLAN_SCHEMA:
        assert_execution_disabled(sample["execution_gate"], "registry_privacy_execution_enabled")


def test_ai_host_and_execute_schema_continue_to_deny_permanent_delete(
    assert_payload_status_false: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    tool = next(tool for tool in tool_catalog()["tools"] if tool["name"] == "cleanwin_execute_plan")

    delete_mode = tool["parameters"]["properties"]["delete_mode"]
    assert_field_values(delete_mode, {"enum": ["recycle"]})

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
