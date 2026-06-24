"""Report-to-execution promotion gates for high-risk cleanup surfaces."""

from __future__ import annotations

from typing import Any

PROMOTION_GATES_SCHEMA = "cleanwin.promotion-gates.v1"


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
                "target_path",
                "target_exists",
                "publisher_or_signature_status",
                "risk_reason",
            ],
            required_snapshots=["registry-export", "startup-folder-snapshot"],
            rollback_metadata=["startup_location", "entry_name", "previous_command", "restore_action"],
            required_tests=["fixture-missing-target", "fixture-existing-target", "rollback-metadata-validation"],
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
                "publisher_or_author",
                "target_path",
                "risk_reason",
            ],
            required_snapshots=["system-restore-point", "service-state", "scheduled-task-state"],
            rollback_metadata=["object_name", "previous_state", "previous_start_type", "restore_command"],
            required_tests=["fixture-service-state", "fixture-scheduled-task-state", "rollback-metadata-validation"],
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
