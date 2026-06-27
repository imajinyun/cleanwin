"""Non-executable execution expansion contracts."""

from __future__ import annotations

from typing import Any

DISABLE_REVERT_CONTRACT_SCHEMA = "cleanwin.disable-revert-contract.v1"
BACKUP_DELETE_CONTRACT_SCHEMA = "cleanwin.backup-delete-contract.v1"
PERMANENT_DELETE_DENIAL_SCHEMA = "cleanwin.permanent-delete-denial.v1"


def disable_revert_contract_report() -> dict[str, Any]:
    action_contracts = [
        {
            "id": "disable-revert.startup-entry",
            "target_action": "startup-disable",
            "source_report": "cleanwin.startup-service-inventory.v1",
            "required_snapshots": ["registry-export", "startup-folder-snapshot"],
            "required_rollback_metadata": ["startup_location", "entry_name", "previous_command", "restore_action", "snapshot_artifact_ref"],
            "required_review_evidence": ["publisher", "signature_status", "target_path", "target_status", "target_exists", "risk"],
            "revert_plan_schema": "cleanwin.revert.startup-entry.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "disable-revert.service",
            "target_action": "service-disable-or-stop",
            "source_report": "cleanwin.startup-service-inventory.v1",
            "required_snapshots": ["system-restore-point", "service-state", "service-registry-export"],
            "required_rollback_metadata": ["service_name", "previous_status", "previous_start_type", "restore_command", "snapshot_artifact_ref"],
            "required_review_evidence": [
                "display_name",
                "publisher",
                "signature_status",
                "target_path",
                "target_status",
                "start_type_classification",
                "dependencies",
                "trigger_start",
                "recovery_actions",
                "risk",
            ],
            "revert_plan_schema": "cleanwin.revert.service.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "disable-revert.scheduled-task",
            "target_action": "scheduled-task-disable",
            "source_report": "cleanwin.startup-service-inventory.v1",
            "required_snapshots": ["system-restore-point", "scheduled-task-state", "scheduled-task-xml-export"],
            "required_rollback_metadata": ["task_name", "previous_state", "task_xml_or_export_ref", "restore_command", "snapshot_artifact_ref"],
            "required_review_evidence": [
                "task_to_run",
                "publisher",
                "target_path",
                "target_status",
                "target_exists",
                "run_as_user",
                "run_level",
                "xml_snapshot_required",
                "risk",
            ],
            "revert_plan_schema": "cleanwin.revert.scheduled-task.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "disable-revert.policy",
            "target_action": "policy-change",
            "source_report": "cleanwin.debloat-privacy-report.v1",
            "required_snapshots": ["registry-export", "system-restore-point"],
            "required_rollback_metadata": ["hive", "subkey_path", "value_name", "previous_value", "registry_export_ref"],
            "required_review_evidence": ["policy_owner", "observed_value", "expected_value", "managed_device_state"],
            "revert_plan_schema": "cleanwin.revert.policy.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
    ]
    return {
        "schema": DISABLE_REVERT_CONTRACT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "action_contracts": action_contracts,
        "summary": {
            "contract_count": len(action_contracts),
            "execution_enabled_count": sum(1 for item in action_contracts if item["execution_enabled"]),
            "requires_snapshot_count": sum(1 for item in action_contracts if item["required_snapshots"]),
        },
        "execution_gate": {
            "disable_revert_execution_enabled": False,
            "requires_snapshot_artifacts": True,
            "requires_revert_plan": True,
            "requires_policy_simulation": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not disable startup entries.",
            "This report does not stop or disable services.",
            "This report does not disable scheduled tasks or change policies.",
        ],
    }


def backup_delete_contract_report() -> dict[str, Any]:
    backup_scopes = [
        {
            "id": "backup-delete.file-tree",
            "target_surface": "reviewed file or directory tree",
            "allowed_categories": ["app-leftovers", "future-backup-delete-only"],
            "required_identity": ["cleanwin.filesystem-identity.v1", "canonical_path", "file_id_or_stat_tuple", "size_bytes", "modified_ns"],
            "required_backup_metadata": ["backup_path", "backup_identity", "source_identity", "created_at", "verification_digest"],
            "required_audit_refs": ["plan_source_fingerprint", "dry_run_confirmation_token", "operation_log_ref"],
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "backup-delete.registry-key",
            "target_surface": "registry key export before registry mutation",
            "allowed_categories": ["future-registry-change"],
            "required_identity": ["hive", "subkey_path", "value_names", "observed_values"],
            "required_backup_metadata": ["registry_export_ref", "export_command", "export_digest", "previous_values"],
            "required_audit_refs": ["policy_owner_review", "plan_source_fingerprint", "operation_log_ref"],
            "execution_enabled": False,
            "auto_executable": False,
        },
    ]
    return {
        "schema": BACKUP_DELETE_CONTRACT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "backup_scopes": backup_scopes,
        "summary": {
            "scope_count": len(backup_scopes),
            "execution_enabled_count": sum(1 for item in backup_scopes if item["execution_enabled"]),
            "requires_backup_verification_count": len(backup_scopes),
        },
        "execution_gate": {
            "backup_delete_execution_enabled": False,
            "requires_pre_delete_backup": True,
            "requires_backup_verification": True,
            "requires_identity_match_before_delete": True,
            "requires_operation_log": True,
            "requires_restore_drill_evidence": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not copy backup data.",
            "This report does not delete source data after backup.",
            "This report does not replace recycle-mode execution for ordinary low-risk cleanup.",
        ],
    }


def permanent_delete_denial_report() -> dict[str, Any]:
    return {
        "schema": PERMANENT_DELETE_DENIAL_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "capability": {
            "id": "permanent-delete",
            "risk": "critical",
            "default_state": "denied",
            "execution_enabled": False,
            "ai_auto_call_allowed": False,
            "mcp_tool_exposed": False,
            "allowed_delete_modes": ["recycle"],
            "denied_delete_modes": ["permanent"],
        },
        "required_future_gates": [
            "separate explicit permanent-delete command surface",
            "stronger human confirmation phrase",
            "non-AI auto-call policy",
            "backup or recovery proof",
            "operation log with irreversible-delete marker",
            "release-specific destructive capability review",
        ],
        "current_enforcement": {
            "plan_validation_rejects_permanent": True,
            "execute_plan_passes_allow_permanent_false": True,
            "ai_host_policy_requires_recycle": True,
            "mcp_execute_schema_allows_recycle_only": True,
            "delete_ops_requires_allow_permanent_true": True,
        },
        "summary": {
            "execution_enabled_count": 0,
            "denied_mode_count": 1,
            "future_gate_count": 6,
        },
        "non_goals": [
            "This report does not enable permanent deletion.",
            "This report does not add permanent deletion to AI or MCP tools.",
            "This report does not relax recycle-mode execution requirements.",
        ],
    }
