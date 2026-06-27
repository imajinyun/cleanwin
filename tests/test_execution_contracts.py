from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

import pytest

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import tool_catalog
from cleanwincli.execution_contracts import (
    APPX_REMOVAL_CHANGE_SCHEMA,
    APPX_REMOVAL_PLAN_SCHEMA,
    APPX_REMOVAL_PLAN_VALIDATION_SCHEMA,
    APPX_REMOVAL_REVERT_SCHEMA,
    BACKUP_DELETE_CONTRACT_SCHEMA,
    DISABLE_REVERT_CONTRACT_SCHEMA,
    PERMANENT_DELETE_DENIAL_SCHEMA,
    REGISTRY_PRIVACY_CHANGE_SCHEMA,
    REGISTRY_PRIVACY_PLAN_SCHEMA,
    REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA,
    REGISTRY_PRIVACY_REVERT_SCHEMA,
    SERVICE_DISABLE_CHANGE_SCHEMA,
    SERVICE_TASK_DISABLE_PLAN_SCHEMA,
    SERVICE_TASK_DISABLE_PLAN_VALIDATION_SCHEMA,
    SERVICE_TASK_REVERT_SCHEMA,
    TASK_DISABLE_CHANGE_SCHEMA,
    appx_removal_plan_report,
    backup_delete_contract_report,
    disable_revert_contract_report,
    permanent_delete_denial_report,
    registry_privacy_change_plan_report,
    service_task_disable_plan_report,
    validate_appx_removal_plan,
    validate_registry_privacy_change_plan,
    validate_service_task_disable_plan,
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


def _appx_source_report() -> JSONPayload:
    return {
        "schema": "cleanwin.windows-inventory.v1",
        "sections": [
            {
                "id": "appx-packages",
                "items": [
                    {
                        "Name": "Microsoft.XboxGamingOverlay",
                        "PackageFullName": "Microsoft.XboxGamingOverlay_1.0.0.0_x64__8wekyb3d8bbwe",
                        "PackageFamilyName": "Microsoft.XboxGamingOverlay_8wekyb3d8bbwe",
                        "Publisher": "CN=Microsoft",
                        "cleanwin_classification": {
                            "category": "consumer-app",
                            "protected_by_default": False,
                            "dependency": False,
                            "non_removable": False,
                            "provisioned_state": False,
                            "safe_to_execute": False,
                        },
                    },
                    {
                        "Name": "Microsoft.VCLibs.140.00.UWPDesktop",
                        "PackageFullName": "Microsoft.VCLibs_1.0.0.0_x64__8wekyb3d8bbwe",
                        "cleanwin_classification": {
                            "category": "framework",
                            "protected_by_default": True,
                            "dependency": True,
                            "non_removable": False,
                            "provisioned_state": False,
                            "safe_to_execute": False,
                        },
                    },
                    {
                        "Name": "Unknown.Package",
                        "PackageFullName": "Unknown.Package_1.0.0.0_x64__example",
                        "cleanwin_classification": {
                            "category": "unknown",
                            "protected_by_default": True,
                            "dependency": False,
                            "non_removable": False,
                            "provisioned_state": False,
                            "safe_to_execute": False,
                        },
                    },
                ],
            },
            {
                "id": "provisioned-appx-packages",
                "items": [
                    {
                        "PackageName": "Microsoft.ZuneMusic_1.0.0.0_neutral_~_8wekyb3d8bbwe",
                        "DisplayName": "Microsoft.ZuneMusic",
                        "cleanwin_classification": {
                            "category": "consumer-app",
                            "protected_by_default": False,
                            "dependency": False,
                            "non_removable": False,
                            "provisioned_state": True,
                            "safe_to_execute": False,
                        },
                    }
                ],
            },
        ],
    }


def test_appx_removal_plan_allows_only_per_user_consumer_simulation(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    report = assert_readonly_report(appx_removal_plan_report(_appx_source_report()), APPX_REMOVAL_PLAN_SCHEMA)

    assert_summary_counts(
        report,
        {
            "change_count": 1,
            "blocked_package_count": 3,
            "execution_enabled_count": 0,
            "per_user_scope_count": 1,
        },
    )
    assert_field_values(
        report["execution_gate"],
        {
            "appx_removal_execution_enabled": False,
            "requires_appx_snapshot": True,
            "requires_consumer_app_classification": True,
            "requires_non_framework_non_system": True,
            "requires_non_provisioned_scope": True,
            "requires_restore_command": True,
        },
    )
    change = assert_payload_schema(report["changes"][0], APPX_REMOVAL_CHANGE_SCHEMA)
    assert_execution_disabled(change, "auto_executable", "safe_to_execute")
    assert_field_values(
        change,
        {
            "scope": "per-user",
            "package.name": "Microsoft.XboxGamingOverlay",
            "classification.category": "consumer-app",
        },
    )
    assert_contains_all(change["remove_command"], ["powershell.exe", "Remove-AppxPackage"])
    assert_payload_schema(change["rollback"], APPX_REMOVAL_REVERT_SCHEMA)
    assert_contains_all(change["rollback"]["restore_command"], ["powershell.exe", "Add-AppxPackage"])
    blocked_reasons = {reason for blocked in report["blocked_packages"] for reason in blocked["blocked_reasons"]}
    assert_contains_all(blocked_reasons, ["category:framework", "category:unknown", "provisioned_package"])
    assert_field_values(report["validation"], {"valid": True})


def test_appx_removal_plan_validator_reports_protected_or_incomplete_changes(
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = assert_payload_schema(
        validate_appx_removal_plan(
            {
                "schema": APPX_REMOVAL_PLAN_SCHEMA,
                "changes": [
                    {
                        "schema": APPX_REMOVAL_CHANGE_SCHEMA,
                        "scope": "all-users",
                        "package": {"package_full_name": ""},
                        "classification": {"category": "framework", "protected_by_default": True},
                        "execution_enabled": True,
                    }
                ],
            }
        ),
        APPX_REMOVAL_PLAN_VALIDATION_SCHEMA,
    )

    assert_field_values(validation, {"valid": False})
    assert_contains_all(
        {violation["code"] for violation in validation["violations"]},
        [
            "PER_USER_SCOPE_REQUIRED",
            "CONSUMER_APP_REQUIRED",
            "PACKAGE_IDENTITY_REQUIRED",
            "APPX_SNAPSHOT_REQUIRED",
            "ROLLBACK_PLAN_REQUIRED",
            "RESTORE_COMMAND_REQUIRED",
            "EXECUTION_MUST_STAY_DISABLED",
        ],
    )


def _service_task_source_report() -> JSONPayload:
    return {
        "schema": "cleanwin.startup-service-inventory.v1",
        "services": [
            {
                "name": "ExampleUpdater",
                "display_name": "Example Updater",
                "status": "Running",
                "start_type": "Automatic",
                "start_type_classification": "auto-start",
                "service_type": "service",
                "is_driver": False,
                "binary_path": r"C:\Program Files\Example\updater.exe",
                "target_status": "exists",
                "publisher": "Example Corp",
                "dependencies": ["RpcSs"],
                "trigger_start": True,
                "recovery_actions": ["restart-service"],
            },
            {
                "name": "ExampleDriver",
                "display_name": "Example Driver",
                "status": "Running",
                "start_type": "Manual",
                "start_type_classification": "manual",
                "service_type": "Kernel Driver",
                "is_driver": True,
                "binary_path": r"C:\Windows\System32\drivers\example.sys",
                "target_status": "exists",
                "publisher": "Example Corp",
                "dependencies": [],
                "trigger_start": "unknown",
                "recovery_actions": [],
            },
            {
                "name": "MicrosoftUpdate",
                "display_name": "Microsoft Update Service",
                "status": "Running",
                "start_type": "Automatic",
                "start_type_classification": "auto-start",
                "service_type": "service",
                "is_driver": False,
                "binary_path": r"C:\Windows\System32\update.exe",
                "target_status": "exists",
                "publisher": "Microsoft",
                "dependencies": [],
                "trigger_start": "unknown",
                "recovery_actions": [],
            },
        ],
        "scheduled_tasks": [
            {
                "name": r"\Example\Updater",
                "task_path": r"\Example\Updater",
                "state": "Ready",
                "task_to_run": r"C:\Program Files\Example\updater.exe",
                "target_status": "exists",
                "publisher": "Example Corp",
                "run_as_user": "ExampleUser",
                "run_level": "LeastPrivilege",
            },
            {
                "name": r"\Microsoft\Windows\UpdateTask",
                "task_path": r"\Microsoft\Windows\UpdateTask",
                "state": "Ready",
                "task_to_run": r"C:\Windows\System32\update.exe",
                "target_status": "exists",
                "publisher": "Microsoft",
                "run_as_user": "SYSTEM",
                "run_level": "Highest",
            },
        ],
    }


def test_service_task_disable_plan_allows_only_third_party_simulation(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    report = assert_readonly_report(service_task_disable_plan_report(_service_task_source_report()), SERVICE_TASK_DISABLE_PLAN_SCHEMA)

    assert_summary_counts(
        report,
        {
            "change_count": 2,
            "blocked_target_count": 3,
            "service_change_count": 1,
            "scheduled_task_change_count": 1,
            "execution_enabled_count": 0,
        },
    )
    assert_field_values(
        report["execution_gate"],
        {
            "service_task_disable_execution_enabled": False,
            "requires_service_registry_export": True,
            "requires_service_state_snapshot": True,
            "requires_task_xml_export": True,
            "requires_dependency_trigger_recovery_review": True,
            "requires_restore_command": True,
        },
    )
    service_change = assert_payload_schema(report["changes"][0], SERVICE_DISABLE_CHANGE_SCHEMA)
    task_change = assert_payload_schema(report["changes"][1], TASK_DISABLE_CHANGE_SCHEMA)
    assert_execution_disabled(service_change, "auto_executable", "safe_to_execute")
    assert_execution_disabled(task_change, "auto_executable", "safe_to_execute")
    assert_field_values(
        service_change,
        {
            "service_name": "ExampleUpdater",
            "target_start_type": "disabled",
            "dependencies": ["RpcSs"],
            "trigger_start": True,
            "recovery_actions": ["restart-service"],
        },
    )
    assert_contains_all(service_change["required_snapshot_commands"][1], ["reg.exe", "export"])
    assert_payload_schema(service_change["rollback"], SERVICE_TASK_REVERT_SCHEMA)
    assert_field_values(task_change, {"task_name": r"\Example\Updater", "run_as_user": "ExampleUser"})
    assert_contains_all(task_change["required_snapshot_commands"][0], ["schtasks", "/XML"])
    assert_payload_schema(task_change["rollback"], SERVICE_TASK_REVERT_SCHEMA)
    blocked_reasons = {reason for blocked in report["blocked_targets"] for reason in blocked["blocked_reasons"]}
    assert_contains_all(blocked_reasons, ["driver_service", "protected_vendor_or_core_surface", "system_principal"])
    assert_field_values(report["validation"], {"valid": True})


def test_service_task_disable_plan_validator_reports_missing_evidence(
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = assert_payload_schema(
        validate_service_task_disable_plan(
            {
                "schema": SERVICE_TASK_DISABLE_PLAN_SCHEMA,
                "changes": [
                    {
                        "schema": SERVICE_DISABLE_CHANGE_SCHEMA,
                        "service_name": "",
                        "execution_enabled": True,
                    },
                    {
                        "schema": TASK_DISABLE_CHANGE_SCHEMA,
                        "task_name": "",
                        "snapshot_refs": [],
                        "restore_command": [],
                        "required_snapshot_commands": [],
                        "rollback": {},
                        "execution_enabled": False,
                    },
                ],
            }
        ),
        SERVICE_TASK_DISABLE_PLAN_VALIDATION_SCHEMA,
    )

    assert_field_values(validation, {"valid": False})
    assert_contains_all(
        {violation["code"] for violation in validation["violations"]},
        [
            "SNAPSHOT_REQUIRED",
            "RESTORE_COMMAND_REQUIRED",
            "ROLLBACK_PLAN_REQUIRED",
            "EXECUTION_MUST_STAY_DISABLED",
            "SERVICE_NAME_REQUIRED",
            "SERVICE_REVIEW_FIELD_REQUIRED",
            "TASK_NAME_REQUIRED",
            "TASK_XML_EXPORT_REQUIRED",
        ],
    )


@pytest.mark.parametrize(
    ("command", "schema"),
    [
        ("disable-revert-contract", DISABLE_REVERT_CONTRACT_SCHEMA),
        ("backup-delete-contract", BACKUP_DELETE_CONTRACT_SCHEMA),
        ("permanent-delete-denial", PERMANENT_DELETE_DENIAL_SCHEMA),
        ("registry-privacy-plan", REGISTRY_PRIVACY_PLAN_SCHEMA),
        ("appx-removal-plan", APPX_REMOVAL_PLAN_SCHEMA),
        ("service-task-disable-plan", SERVICE_TASK_DISABLE_PLAN_SCHEMA),
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
    if schema == APPX_REMOVAL_PLAN_SCHEMA:
        assert_execution_disabled(sample["execution_gate"], "appx_removal_execution_enabled")
    if schema == SERVICE_TASK_DISABLE_PLAN_SCHEMA:
        assert_execution_disabled(sample["execution_gate"], "service_task_disable_execution_enabled")


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
