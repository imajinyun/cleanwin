"""Non-executable execution expansion contracts."""

from __future__ import annotations

from typing import Any

DISABLE_REVERT_CONTRACT_SCHEMA = "cleanwin.disable-revert-contract.v1"
BACKUP_DELETE_CONTRACT_SCHEMA = "cleanwin.backup-delete-contract.v1"
PERMANENT_DELETE_DENIAL_SCHEMA = "cleanwin.permanent-delete-denial.v1"
REGISTRY_PRIVACY_PLAN_SCHEMA = "cleanwin.registry-privacy-plan.v1"
REGISTRY_PRIVACY_CHANGE_SCHEMA = "cleanwin.registry-privacy-change.v1"
REGISTRY_PRIVACY_REVERT_SCHEMA = "cleanwin.registry-privacy-revert.v1"
REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA = "cleanwin.registry-privacy-plan-validation.v1"


def _registry_privacy_change_from_finding(finding: dict[str, Any]) -> dict[str, Any]:
    evidence = finding.get("change_evidence", {})
    expected_values = evidence.get("expected_private_values", [])
    target_value = str(expected_values[0]) if isinstance(expected_values, list) and expected_values else ""
    hive = str(evidence.get("hive") or "")
    subkey_path = str(evidence.get("subkey_path") or "")
    value_name = str(evidence.get("value_name") or "")
    observed_value = str(evidence.get("observed_value") or "")
    registry_export_ref = f"snapshot://registry/{finding.get('id')}.reg"
    return {
        "schema": REGISTRY_PRIVACY_CHANGE_SCHEMA,
        "id": f"registry-privacy.change.{finding['id']}",
        "source_finding_id": finding["id"],
        "target_action": "registry-privacy-change",
        "risk": finding.get("risk", "medium"),
        "state": "simulated",
        "hive": hive,
        "subkey_path": subkey_path,
        "value_name": value_name,
        "previous_value": observed_value,
        "target_value": target_value,
        "registry_export_ref": registry_export_ref,
        "required_export_command": evidence.get("required_export_command", ["reg.exe", "export", rf"{hive}\{subkey_path}", "<export-file.reg>", "/y"]),
        "restore_command": ["reg.exe", "import", "<export-file.reg>"],
        "managed_device_detection": {
            "required": True,
            "signals": ["domain_joined", "mdm_enrolled", "policy_key_owned_by_organization"],
            "state": "not-evaluated",
        },
        "owner_review": {
            "required": True,
            "policy_owner": "unknown",
            "review_state": "required",
        },
        "dry_run_confirmation": {
            "required": True,
            "token_ref": "cleanwin.ai-confirmation-summary.v1.confirmation_token",
            "provided": False,
        },
        "rollback": {
            "schema": REGISTRY_PRIVACY_REVERT_SCHEMA,
            "registry_export_ref": registry_export_ref,
            "previous_value": observed_value,
            "restore_command": ["reg.exe", "import", "<export-file.reg>"],
            "verification": ["query exact registry value after restore", "compare previous value"],
        },
        "execution_enabled": False,
        "auto_executable": False,
        "safe_to_execute": False,
    }


def registry_privacy_change_plan_report(source_report: dict[str, Any] | None = None) -> dict[str, Any]:
    if source_report is None:
        from cleanwincli.debloat_privacy import debloat_privacy_report

        source_report = debloat_privacy_report()
    findings = [
        finding
        for finding in source_report.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("kind") == "registry-policy"
        and finding.get("state") == "review-recommended"
        and isinstance(finding.get("change_evidence"), dict)
    ]
    changes = [_registry_privacy_change_from_finding(finding) for finding in findings]
    return {
        "schema": REGISTRY_PRIVACY_PLAN_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "source_report_schema": source_report.get("schema"),
        "plan_state": "simulation-only",
        "changes": changes,
        "summary": {
            "change_count": len(changes),
            "execution_enabled_count": sum(1 for change in changes if change["execution_enabled"]),
            "requires_registry_export_count": len(changes),
            "requires_owner_review_count": len(changes),
            "requires_dry_run_token_count": len(changes),
        },
        "validation": validate_registry_privacy_change_plan({"schema": REGISTRY_PRIVACY_PLAN_SCHEMA, "changes": changes}),
        "execution_gate": {
            "registry_privacy_execution_enabled": False,
            "requires_registry_export": True,
            "requires_previous_value": True,
            "requires_managed_device_detection": True,
            "requires_policy_owner_review": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not write registry values.",
            "This report does not import registry rollback files.",
            "This report does not bypass managed-device policy ownership.",
        ],
    }


def validate_registry_privacy_change_plan(plan: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if plan.get("schema") != REGISTRY_PRIVACY_PLAN_SCHEMA:
        violations.append({"path": "schema", "code": "INVALID_SCHEMA", "message": f"schema must be {REGISTRY_PRIVACY_PLAN_SCHEMA}"})
    changes = plan.get("changes")
    if not isinstance(changes, list):
        violations.append({"path": "changes", "code": "MISSING_CHANGES", "message": "changes must be a list"})
        changes = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            violations.append({"path": f"changes.{index}", "code": "INVALID_CHANGE", "message": "change must be an object"})
            continue
        prefix = f"changes.{index}"
        required_fields = {
            "schema": REGISTRY_PRIVACY_CHANGE_SCHEMA,
            "hive": None,
            "subkey_path": None,
            "value_name": None,
            "previous_value": None,
            "target_value": None,
            "registry_export_ref": None,
            "restore_command": None,
        }
        for field, expected in required_fields.items():
            value = change.get(field)
            if expected is not None and value != expected:
                violations.append({"path": f"{prefix}.{field}", "code": "INVALID_FIELD", "message": f"{field} must be {expected}"})
            elif expected is None and (value is None or value == "" or value == []):
                violations.append({"path": f"{prefix}.{field}", "code": "MISSING_FIELD", "message": f"{field} is required"})
        if change.get("execution_enabled") is not False:
            violations.append({"path": f"{prefix}.execution_enabled", "code": "EXECUTION_MUST_STAY_DISABLED", "message": "registry privacy plan must remain simulation-only"})
        managed_detection = change.get("managed_device_detection")
        if not isinstance(managed_detection, dict) or managed_detection.get("required") is not True:
            violations.append({"path": f"{prefix}.managed_device_detection", "code": "MANAGED_DEVICE_DETECTION_REQUIRED", "message": "managed device detection is required"})
        owner_review = change.get("owner_review")
        if not isinstance(owner_review, dict) or owner_review.get("required") is not True:
            violations.append({"path": f"{prefix}.owner_review", "code": "OWNER_REVIEW_REQUIRED", "message": "policy owner review is required"})
        dry_run = change.get("dry_run_confirmation")
        if not isinstance(dry_run, dict) or dry_run.get("required") is not True:
            violations.append({"path": f"{prefix}.dry_run_confirmation", "code": "DRY_RUN_TOKEN_REQUIRED", "message": "dry-run confirmation token is required"})
        rollback = change.get("rollback")
        if not isinstance(rollback, dict) or rollback.get("schema") != REGISTRY_PRIVACY_REVERT_SCHEMA:
            violations.append({"path": f"{prefix}.rollback", "code": "ROLLBACK_PLAN_REQUIRED", "message": "rollback metadata is required"})
    return {
        "schema": REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA,
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


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
