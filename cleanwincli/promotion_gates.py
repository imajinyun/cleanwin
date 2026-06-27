"""Report-to-execution promotion gates for high-risk cleanup surfaces."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

PROMOTION_GATES_SCHEMA = "cleanwin.promotion-gates.v1"
PROMOTION_GATE_VALIDATION_SCHEMA = "cleanwin.promotion-gate-validation.v1"


def _gate(
    gate_id: str,
    *,
    source_reports: list[str],
    target_action: str,
    default_state: str,
    required_evidence: list[str],
    required_snapshots: list[str],
    rollback_metadata: list[str],
    required_tests: list[str],
    human_confirmations: list[str],
    ai_auto_call_allowed: bool = False,
    rationale: str,
) -> dict[str, Any]:
    return {
        "id": gate_id,
        "source_reports": source_reports,
        "target_action": target_action,
        "default_state": default_state,
        "required_evidence": required_evidence,
        "required_snapshots": required_snapshots,
        "rollback_metadata": rollback_metadata,
        "required_tests": required_tests,
        "human_confirmations": human_confirmations,
        "ai_auto_call_allowed": ai_auto_call_allowed,
        "rationale": rationale,
    }


def promotion_gates_report() -> dict[str, Any]:
    gates = [
        _gate(
            "registry-privacy-to-registry-change",
            source_reports=["cleanwin.debloat-privacy-report.v1"],
            target_action="registry-change",
            default_state="report-only",
            required_evidence=[
                "exact_registry_key",
                "value_name",
                "observed_value",
                "expected_value",
                "policy_owner_review",
                "windows_version_evidence",
            ],
            required_snapshots=["system-restore-point", "registry-export"],
            rollback_metadata=["registry_key", "registry_export_ref", "previous_value", "restore_command"],
            required_tests=["fixture-registry-value-present", "fixture-registry-value-missing", "rollback-metadata-validation"],
            human_confirmations=["explicit-registry-change-review", "matching-dry-run-token"],
            rationale="Registry privacy changes can be policy-managed or organization-owned and must remain report-only until exact rollback evidence exists.",
        ),
        _gate(
            "startup-entry-to-disable-plan",
            source_reports=["cleanwin.startup-service-inventory.v1"],
            target_action="startup-disable",
            default_state="report-only",
            required_evidence=[
                "startup_location",
                "entry_name",
                "command",
                "target_path",
                "target_status",
                "target_exists",
                "publisher_or_signature_status",
                "risk_reason",
                "snapshot_requirements",
            ],
            required_snapshots=["registry-export", "startup-folder-snapshot"],
            rollback_metadata=["startup_location", "entry_name", "previous_command", "restore_action"],
            required_tests=[
                "fixture-missing-target",
                "fixture-existing-target",
                "fixture-environment-expansion-required",
                "rollback-metadata-validation",
            ],
            human_confirmations=["explicit-startup-disable-review", "matching-dry-run-token"],
            rationale="Startup changes alter user login behavior and need reversible state before CleanWin can disable anything.",
        ),
        _gate(
            "service-task-to-disable-plan",
            source_reports=["cleanwin.startup-service-inventory.v1"],
            target_action="service-or-scheduled-task-change",
            default_state="report-only",
            required_evidence=[
                "service_or_task_name",
                "current_state",
                "startup_type_or_task_state",
                "start_type_classification_or_run_level",
                "publisher_or_author",
                "target_path",
                "target_status",
                "dependency_or_trigger_review",
                "recovery_or_xml_snapshot_requirement",
                "risk_reason",
            ],
            required_snapshots=[
                "system-restore-point",
                "service-state",
                "service-registry-export",
                "scheduled-task-state",
                "scheduled-task-xml-export",
            ],
            rollback_metadata=[
                "object_name",
                "previous_state",
                "previous_start_type_or_task_xml",
                "restore_command",
                "snapshot_artifact_ref",
            ],
            required_tests=[
                "fixture-service-state",
                "fixture-scheduled-task-state",
                "fixture-service-target-status",
                "fixture-scheduled-task-xml-required",
                "rollback-metadata-validation",
            ],
            human_confirmations=["explicit-service-task-review", "matching-dry-run-token"],
            rationale="Service and task changes can break update, security, or vendor maintenance flows and must be reversible.",
        ),
        _gate(
            "official-command-to-executable-action",
            source_reports=["cleanwin.official-command-plan.v1"],
            target_action="official-command-execution",
            default_state="report-only",
            required_evidence=[
                "command_id",
                "structured_argv",
                "cleanup_surface",
                "prerequisites",
                "risk",
                "elevation_requirement",
            ],
            required_snapshots=["system-restore-point"],
            rollback_metadata=["command_id", "pre_execution_report_ref", "stdout_ref", "stderr_ref", "exit_code"],
            required_tests=["command-id-allowlist", "raw-shell-denied", "execution-output-captured"],
            human_confirmations=["explicit-official-command-review", "matching-dry-run-token"],
            rationale="Windows-owned cleanup should run only through allowlisted structured commands with captured output and recovery evidence.",
        ),
        _gate(
            "windows-inventory-to-appx-change",
            source_reports=["cleanwin.windows-inventory.v1", "cleanwin.debloat-privacy-report.v1"],
            target_action="appx-provisioned-package-change",
            default_state="report-only",
            required_evidence=[
                "package_name",
                "package_family_name",
                "publisher",
                "provisioned_state",
                "per_user_registration_state",
                "dependency_or_framework_classification",
                "debloat_review_category",
            ],
            required_snapshots=["system-restore-point", "appx-package-snapshot", "provisioned-appx-snapshot"],
            rollback_metadata=["package_name", "package_family_name", "previous_registration_state", "restore_command"],
            required_tests=["fixture-appx-framework-protected", "fixture-provisioned-package-state", "rollback-metadata-validation"],
            human_confirmations=["explicit-appx-change-review", "matching-dry-run-token"],
            rationale="AppX and provisioned package changes can affect framework packages, per-user registrations, Store repair, and future user profiles.",
        ),
        _gate(
            "windows-inventory-to-feature-change",
            source_reports=["cleanwin.windows-inventory.v1"],
            target_action="windows-feature-change",
            default_state="report-only",
            required_evidence=[
                "feature_name",
                "current_state",
                "parent_feature_or_capability",
                "dependency_review",
                "reboot_requirement",
                "windows_version_evidence",
            ],
            required_snapshots=["system-restore-point", "windows-feature-snapshot"],
            rollback_metadata=["feature_name", "previous_state", "restore_command", "reboot_required"],
            required_tests=["fixture-feature-dependency", "fixture-feature-state", "rollback-metadata-validation"],
            human_confirmations=["explicit-windows-feature-review", "matching-dry-run-token"],
            rationale="Windows feature changes may remove shared OS capabilities and must be modeled through reversible official Windows mechanisms.",
        ),
        _gate(
            "windows-inventory-to-component-store-cleanup",
            source_reports=["cleanwin.windows-inventory.v1", "cleanwin.official-command-plan.v1"],
            target_action="component-store-cleanup",
            default_state="report-only",
            required_evidence=[
                "component_store_analysis",
                "recommended_cleanup",
                "pending_reboot_state",
                "servicing_stack_health",
                "official_command_id",
                "elevated_terminal_requirement",
            ],
            required_snapshots=["system-restore-point", "component-store-analysis"],
            rollback_metadata=["analysis_ref", "command_id", "pre_execution_report_ref", "stdout_ref", "stderr_ref", "exit_code"],
            required_tests=["fixture-dism-analysis", "command-id-allowlist", "execution-output-captured"],
            human_confirmations=["explicit-component-store-review", "matching-dry-run-token"],
            rationale="Component store cleanup must use DISM/official command surfaces and must never become direct WinSxS file deletion.",
        ),
        _gate(
            "windows-inventory-to-installer-cache-cleanup",
            source_reports=["cleanwin.windows-inventory.v1", "cleanwin.installed-app-inventory.v1"],
            target_action="installer-cache-cleanup",
            default_state="report-only",
            required_evidence=[
                "installer_cache_path",
                "owning_product_code",
                "installed_application_state",
                "repair_uninstall_dependency_review",
                "orphan_detection_evidence",
            ],
            required_snapshots=["installer-cache-snapshot", "installed-app-inventory-snapshot"],
            rollback_metadata=["installer_cache_path", "owning_product_code", "previous_identity", "recycle_destination"],
            required_tests=["fixture-installer-cache-owned", "fixture-installer-cache-orphan", "rollback-metadata-validation"],
            human_confirmations=["explicit-installer-cache-review", "matching-dry-run-token"],
            rationale="Windows Installer cache can be required for repair, patching, and uninstall; direct cleanup must stay blocked without ownership evidence.",
        ),
        _gate(
            "windows-inventory-to-recycle-bin-empty",
            source_reports=["cleanwin.windows-inventory.v1"],
            target_action="recycle-bin-empty",
            default_state="report-only",
            required_evidence=[
                "sid_or_user_scope",
                "item_count",
                "bytes_reported",
                "oldest_item_age",
                "cloud_sync_path_review",
                "user_confirmation_scope",
            ],
            required_snapshots=["recycle-bin-inventory-snapshot"],
            rollback_metadata=["sid_or_user_scope", "pre_empty_inventory_ref", "operation_log_ref"],
            required_tests=["fixture-recycle-bin-user-scope", "fixture-cloud-path-exclusion", "operation-log-required"],
            human_confirmations=["explicit-recycle-bin-empty-review", "matching-dry-run-token"],
            rationale="Emptying Recycle Bin is irreversible from ordinary user workflows and must remain separate from recycle-mode file cleanup.",
        ),
        _gate(
            "browser-profile-to-cache-plan",
            source_reports=["cleanwin.browser-profile-inventory.v1"],
            target_action="browser-cache-delete",
            default_state="low-risk-cache-only",
            required_evidence=[
                "browser",
                "profile_name",
                "profile_path",
                "cache_layer",
                "locked_profile_state",
                "sensitive_exclusions",
            ],
            required_snapshots=[],
            rollback_metadata=["profile_path", "cache_layer", "recycle_destination"],
            required_tests=["fixture-locked-profile", "fixture-sensitive-data-excluded", "cache-layer-classification"],
            human_confirmations=["matching-dry-run-token"],
            ai_auto_call_allowed=True,
            rationale="Only regenerated browser cache layers may be promoted; cookies, passwords, sessions, extensions, and profile databases stay excluded.",
        ),
    ]
    return {
        "schema": PROMOTION_GATES_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "execution_enabled": False,
        "gate_count": len(gates),
        "gates": gates,
        "summary": {
            "report_only_gate_count": sum(1 for gate in gates if gate["default_state"] == "report-only"),
            "ai_auto_call_allowed_count": sum(1 for gate in gates if gate["ai_auto_call_allowed"]),
            "requires_snapshot_count": sum(1 for gate in gates if gate["required_snapshots"]),
        },
        "global_requirements": [
            "No raw shell command strings in executable plans.",
            "Every promoted action must keep source report evidence in the plan.",
            "Every destructive action must pass validate-plan, review-plan, policy-simulate, dry-run, and execute-plan gates.",
            "Every rollback-capable system action must reference captured snapshot artifacts before execution.",
        ],
        "non_goals": [
            "This report does not enable registry, startup, service, scheduled task, debloat, or official-command execution.",
            "This report does not weaken CleanWin dry-run, recycle, confirmation phrase, operation log, or AI host policy gates.",
        ],
    }


def _values_from_mapping(payload: Mapping[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if isinstance(value, Mapping):
        return {str(item) for item in value.keys()}
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return {str(item) for item in value}
    return set()


def _gate_for_action(gates: list[dict[str, Any]], proposed_action: Mapping[str, Any]) -> dict[str, Any] | None:
    gate_id = str(proposed_action.get("gate_id") or "")
    target_action = str(proposed_action.get("target_action") or "")
    for gate in gates:
        if gate_id and gate["id"] == gate_id:
            return gate
        if target_action and gate["target_action"] == target_action:
            return gate
    return None


def validate_promotion_gate_action(
    *,
    source_report: Mapping[str, Any],
    proposed_action: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate whether a proposed action has the evidence required by a gate."""
    gates = promotion_gates_report()["gates"]
    gate = _gate_for_action(gates, proposed_action)
    source_schema = str(source_report.get("schema") or proposed_action.get("source_report_schema") or "")
    provided_evidence = _values_from_mapping(proposed_action, "evidence")
    provided_snapshots = _values_from_mapping(proposed_action, "snapshots")
    provided_rollback_metadata = _values_from_mapping(proposed_action, "rollback_metadata")
    provided_tests = _values_from_mapping(proposed_action, "tests")
    provided_confirmations = _values_from_mapping(proposed_action, "human_confirmations")

    if gate is None:
        return {
            "schema": PROMOTION_GATE_VALIDATION_SCHEMA,
            "valid": False,
            "destructive": False,
            "dry_run": True,
            "execution_enabled": False,
            "gate_id": "",
            "target_action": str(proposed_action.get("target_action") or ""),
            "source_report_schema": source_schema,
            "missing_source_reports": [],
            "missing_evidence": [],
            "missing_snapshots": [],
            "missing_rollback_metadata": [],
            "missing_tests": [],
            "missing_human_confirmations": [],
            "errors": [{"code": "UNKNOWN_PROMOTION_GATE", "detail": "No promotion gate matches the proposed action."}],
            "safe_to_execute": False,
        }

    missing_source_reports = [] if source_schema in gate["source_reports"] else list(gate["source_reports"])
    missing_evidence = [item for item in gate["required_evidence"] if item not in provided_evidence]
    missing_snapshots = [item for item in gate["required_snapshots"] if item not in provided_snapshots]
    missing_rollback_metadata = [item for item in gate["rollback_metadata"] if item not in provided_rollback_metadata]
    missing_tests = [item for item in gate["required_tests"] if item not in provided_tests]
    missing_confirmations = [item for item in gate["human_confirmations"] if item not in provided_confirmations]
    errors = []
    for code, missing in [
        ("MISSING_SOURCE_REPORT", missing_source_reports),
        ("MISSING_REQUIRED_EVIDENCE", missing_evidence),
        ("MISSING_REQUIRED_SNAPSHOTS", missing_snapshots),
        ("MISSING_ROLLBACK_METADATA", missing_rollback_metadata),
        ("MISSING_REQUIRED_TESTS", missing_tests),
        ("MISSING_HUMAN_CONFIRMATIONS", missing_confirmations),
    ]:
        if missing:
            errors.append({"code": code, "detail": ", ".join(missing)})

    return {
        "schema": PROMOTION_GATE_VALIDATION_SCHEMA,
        "valid": not errors,
        "destructive": False,
        "dry_run": True,
        "execution_enabled": False,
        "gate_id": gate["id"],
        "target_action": gate["target_action"],
        "source_report_schema": source_schema,
        "missing_source_reports": missing_source_reports,
        "missing_evidence": missing_evidence,
        "missing_snapshots": missing_snapshots,
        "missing_rollback_metadata": missing_rollback_metadata,
        "missing_tests": missing_tests,
        "missing_human_confirmations": missing_confirmations,
        "errors": errors,
        "safe_to_execute": False,
    }
