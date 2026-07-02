"""CleanWin orchestration for inspect, plan, validation, and execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cleanwincli import __version__
from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call, render_ai_host_policy
from cleanwincli.ai_readiness import ai_readiness_report
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_schema import (
    AI_TOOL_DEFINITIONS,
    CONFIRMATION_PHRASE,
    DEFAULT_OPERATION_LOG,
    anthropic_tools_export,
    openai_functions_export,
    provider_export_parity,
    tool_catalog,
    validate_ai_schema,
)
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.ai_versioning import negotiate_plan_schema, schema_registry
from cleanwincli.browser_inventory import browser_profile_inventory_report
from cleanwincli.cache_readiness import low_risk_cache_execution_readiness_report
from cleanwincli.collectors import collect_candidates, collect_findings
from cleanwincli.contract_exposure import contract_exposure_matrix
from cleanwincli.debloat_privacy import debloat_privacy_report
from cleanwincli.doctor import doctor_report
from cleanwincli.environment_index import environment_index_report
from cleanwincli.evidence_bundle import windows_evidence_bundle_report
from cleanwincli.execution_contracts import (
    appx_removal_plan_report,
    backup_delete_contract_report,
    disable_revert_contract_report,
    permanent_delete_denial_report,
    registry_privacy_change_plan_report,
    rollback_drill_report,
    service_task_disable_plan_report,
)
from cleanwincli.external_rules import external_rule_translation_sample, translate_external_rules_file
from cleanwincli.file_reports import file_report
from cleanwincli.identity import capture_filesystem_identity, compare_identity
from cleanwincli.installed_apps import installed_app_inventory_report
from cleanwincli.models import (
    CATEGORY_APP_LEFTOVERS,
    CATEGORY_BROWSER_CACHE,
    CATEGORY_DEV_CACHE,
    CATEGORY_PACKAGE_CACHE,
    CATEGORY_TEMP,
    EXECUTABLE_CACHE_CATEGORIES,
    PLAN_SCHEMA,
    HostContext,
    Plan,
    plan_from_dict,
)
from cleanwincli.official_commands import official_command_plan_report
from cleanwincli.operation_log_readiness import operation_log_readiness_report
from cleanwincli.presets import preset_catalog_report
from cleanwincli.promotion_gates import promotion_gates_report
from cleanwincli.protection import validate_filesystem_candidate
from cleanwincli.recovery import recovery_readiness_report
from cleanwincli.rule_catalog import rule_pack_catalog_report, rule_quality_dashboard_report
from cleanwincli.scan_governance import scan_governance_report
from cleanwincli.startup_inventory import startup_service_inventory_report
from cleanwincli.system_health import system_health_report
from cleanwincli.windows_artifact_validation import artifact_layout_report, artifact_validation_report
from cleanwincli.windows_inventory import windows_inventory_report
from cleanwincli.windows_native_artifacts import windows_native_artifacts_report
from cleanwincli.windows_smoke import windows_smoke_matrix_report
from cleanwincli.workflow_artifacts import workflow_decision_report, workflow_trace_report
from cleanwincli.workflow_router import workflow_router_report


def capabilities() -> dict[str, Any]:
    return {
        "tool": "cleanwin",
        "version": __version__,
        "default_dry_run": True,
        "plan_schema": PLAN_SCHEMA,
        "execution_requires_execute_flag": True,
        "deletion_exit": "cleanwincli.delete_ops.safe_delete",
        "default_delete_mode": "recycle",
        "fail_closed": [
            "non-windows recycle execution without CLEANWIN_TEST_MODE",
            "symlink or junction candidates",
            "protected Windows paths",
            "protected user data paths",
            "operation log write failures",
        ],
        "safe_categories": [CATEGORY_APP_LEFTOVERS, CATEGORY_BROWSER_CACHE, CATEGORY_DEV_CACHE, CATEGORY_PACKAGE_CACHE, CATEGORY_TEMP],
        "executable_cache_categories": sorted(EXECUTABLE_CACHE_CATEGORIES),
        "read_only_categories": [
            "browser-cache-report",
            "backup-delete-contract",
            "browser-profile-inventory",
            "docker-report",
            "file-report",
            "large-files",
            "permanent-delete-denial",
            "registry-report",
            "scan-governance",
            "startup-report",
            "system-health-report",
            "disable-revert-contract",
            "visual-studio-report",
            "windows-inventory",
            "windows-report",
            "wsl-report",
        ],
        "never_auto_execute": ["registry-clean", "startup-disable", "windows-component-clean"],
        "promotion_gates_schema": "cleanwin.promotion-gates.v1",
        "ai": {
            "tool_catalog_schema": "cleanwin.ai-tools.v1",
            "workflow_router_schema": "cleanwin.workflow-router.v1",
            "host_policy_schema": "cleanwin.ai-host-policy.v1",
            "destructive_tool": "cleanwin_execute_plan",
            "confirmation_phrase": CONFIRMATION_PHRASE,
        },
    }


def inspect(categories: list[str], *, older_than_days: int, max_items: int, rule_ids: list[str] | None = None) -> dict[str, Any]:
    candidates = collect_candidates(categories, older_than_days_value=older_than_days, max_items=max_items, rule_ids=rule_ids)
    findings = collect_findings(categories, rule_ids=rule_ids)
    return {
        "schema": "cleanwin.inspect.v1",
        "categories": categories,
        "filters": {"rule_ids": rule_ids or []},
        "candidates": [candidate.to_dict() for candidate in candidates],
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "candidate_count": len(candidates),
            "finding_count": len(findings),
            "bytes_reclaimable": sum(candidate.size_bytes for candidate in candidates if candidate.safe_to_delete),
        },
    }


def build_plan(categories: list[str], *, older_than_days: int, max_items: int, rule_ids: list[str] | None = None) -> Plan:
    candidates = collect_candidates(categories, older_than_days_value=older_than_days, max_items=max_items, rule_ids=rule_ids)
    return Plan(candidates=candidates, categories=categories)


def load_plan(path: Path) -> tuple[Plan, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    plan = plan_from_dict(raw)
    return plan, raw


def validate_plan_payload(plan: Plan, raw: dict[str, Any], *, require_context: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    negotiation = negotiate_plan_schema(str(raw.get("schema") or ""))
    if raw.get("schema") != PLAN_SCHEMA:
        errors.append(f"Unsupported plan schema: {raw.get('schema')}")
    expected_fingerprint = plan.source_fingerprint()
    if raw.get("source_fingerprint") != expected_fingerprint:
        errors.append("Plan source_fingerprint does not match current payload")
    if require_context:
        current = HostContext.current()
        raw_context = plan.context
        if raw_context.home and raw_context.home != current.home:
            errors.append("Plan home context does not match current user home")
        if raw_context.user and raw_context.user != current.user:
            errors.append("Plan user context does not match current user")
    for candidate in plan.candidates:
        if not candidate.safe_to_delete:
            errors.append(f"Candidate is not marked safe_to_delete: {candidate.path}")
            continue
        if candidate.delete_mode != "recycle":
            errors.append(f"Unsupported plan delete_mode for MVP: {candidate.path} uses {candidate.delete_mode}")
            continue
        if candidate.requires_admin:
            errors.append(f"Admin-scoped candidate is not executable in MVP: {candidate.path}")
            continue
        if candidate.category not in EXECUTABLE_CACHE_CATEGORIES:
            errors.append(
                f"Category is not enabled for controlled low-risk cache execution: {candidate.path} uses {candidate.category}"
            )
            continue
        if candidate.risk != "low":
            errors.append(f"Only low-risk cache candidates are executable in MVP: {candidate.path} uses {candidate.risk}")
            continue
        if not candidate.safe_to_delete_rationale:
            errors.append(f"Low-risk cache execution requires a regeneration rationale: {candidate.path}")
            continue
        try:
            candidate_path = Path(candidate.path)
            validate_filesystem_candidate(candidate_path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        current_identity = capture_filesystem_identity(candidate_path)
        identity_mismatches = compare_identity(candidate.identity, current_identity)
        if identity_mismatches:
            errors.append(f"Filesystem identity mismatch for {candidate.path}: {'; '.join(identity_mismatches)}")
    return {
        "schema": "cleanwin.validate-plan.v1",
        "valid": not errors,
        "errors": errors,
        "candidate_count": len(plan.candidates),
        "plan_schema": negotiation,
    }


def confirmation_token_for_plan(plan: Plan, raw_payload: dict[str, Any]) -> str:
    fingerprint = str(raw_payload.get("source_fingerprint") or plan.source_fingerprint())
    token_context = {
        "schema": "cleanwin.ai-confirmation-token-context.v1",
        "plan_fingerprint": fingerprint,
        "delete_mode": "recycle",
        "candidate_count": len(plan.candidates),
        "categories": plan.categories,
    }
    encoded = json.dumps(token_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()



_AI_TOOLS_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "catalog": tool_catalog,
    "openai": openai_functions_export,
    "anthropic": anthropic_tools_export,
    "parity": provider_export_parity,
    "validation": validate_ai_schema,
    "registry": schema_registry,
    "host-policy": lambda: render_ai_host_policy(tool_catalog=tool_catalog()),
    "readiness": ai_readiness_report,
    "self-test": ai_self_test_report,
    "runbook": ai_runbook_report,
    "workflow-router": workflow_router_report,
    "environment-index": environment_index_report,
    "workflow-decision": lambda: workflow_decision_report(route_id="recycle-execution", requested_tool="cleanwin_execute_plan"),
    "workflow-trace": workflow_trace_report,
    "doctor": doctor_report,
    "file-report": file_report,
    "recovery-readiness": recovery_readiness_report,
    "scan-governance": scan_governance_report,
    "external-rule-translate": external_rule_translation_sample,
    "installed-app-inventory": installed_app_inventory_report,
    "official-command-plan": official_command_plan_report,
    "preset-catalog": preset_catalog_report,
    "rule-pack-catalog": rule_pack_catalog_report,
    "rule-quality-dashboard": rule_quality_dashboard_report,
    "promotion-gates": promotion_gates_report,
    "low-risk-cache-readiness": low_risk_cache_execution_readiness_report,
    "operation-log-readiness": operation_log_readiness_report,
    "contract-exposure-matrix": contract_exposure_matrix,
    "browser-profile-inventory": browser_profile_inventory_report,
    "debloat-privacy-report": debloat_privacy_report,
    "backup-delete-contract": backup_delete_contract_report,
    "disable-revert-contract": disable_revert_contract_report,
    "permanent-delete-denial": permanent_delete_denial_report,
    "registry-privacy-plan": registry_privacy_change_plan_report,
    "appx-removal-plan": appx_removal_plan_report,
    "service-task-disable-plan": service_task_disable_plan_report,
    "rollback-drill-report": rollback_drill_report,
    "startup-service-inventory": startup_service_inventory_report,
    "system-health-report": system_health_report,
    "windows-artifact-layout": artifact_layout_report,
    "windows-artifact-validate": artifact_validation_report,
    "windows-native-artifacts": windows_native_artifacts_report,
    "windows-inventory": windows_inventory_report,
    "windows-smoke-matrix": windows_smoke_matrix_report,
    "windows-evidence-bundle": windows_evidence_bundle_report,
}


def ai_tools_report(provider: str = "catalog") -> dict[str, Any]:
    if provider == "review-sample":
        sample = schema_registry().get("samples", {}).get("cleanwin.review.v1")
        if isinstance(sample, dict):
            return sample
        raise RuntimeError("Schema sample unavailable: cleanwin.review.v1")
    handler = _AI_TOOLS_REGISTRY.get(provider)
    if handler is None:
        raise RuntimeError(f"Unsupported ai-tools provider: {provider}")
    result = handler()
    if not isinstance(result, dict):
        raise RuntimeError(f"AI tools provider {provider} did not return a dict")
    return result


def workflow_decision_command(
    *,
    route_id: str,
    requested_tool: str | None = None,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    return workflow_decision_report(route_id=route_id, requested_tool=requested_tool, artifacts=artifacts or [])


def external_rule_translate_command(
    path: Path,
    *,
    source_format: str,
    upstream_project: str | None,
    upstream_rule_id_or_commit: str,
    license_name: str,
) -> dict[str, Any]:
    return translate_external_rules_file(
        path,
        source_format=source_format,
        upstream_project=upstream_project,
        upstream_rule_id_or_commit=upstream_rule_id_or_commit,
        license_name=license_name,
    )


def policy_simulate(
    plan: Plan,
    raw_payload: dict[str, Any],
    *,
    execute: bool,
    delete_mode: str,
    operation_log: str | None,
    require_plan_context: bool,
    require_confirmation_token: bool,
    confirmation_token: str | None,
    confirmation_phrase: str | None,
) -> dict[str, Any]:
    validation = validate_plan_payload(plan, raw_payload, require_context=require_plan_context)
    tool_name = "cleanwin_execute_plan" if execute else "cleanwin_dry_run_plan"
    tool = next(tool for tool in AI_TOOL_DEFINITIONS if tool["name"] == tool_name)
    args: dict[str, Any] = {"delete_mode": delete_mode, "require_plan_context": require_plan_context}
    if operation_log is not None:
        args["operation_log"] = operation_log
    if require_confirmation_token or confirmation_token:
        args["confirmation_token"] = confirmation_token or ""
    if confirmation_phrase is not None:
        args["confirmation_phrase"] = confirmation_phrase
    decision = evaluate_ai_host_tool_call(tool=tool, arguments=args, source="cleanwin.policy-simulate")
    recommended_argv = ["cleanwin", "--json", "execute-plan", "--plan-file", "<plan-file>"]
    if execute:
        recommended_argv.extend(["--execute", "--yes", "--operation-log", operation_log or DEFAULT_OPERATION_LOG])
        recommended_argv.extend(["--confirmation-phrase", CONFIRMATION_PHRASE])
        recommended_argv.extend(["--confirmation-token", confirmation_token_for_plan(plan, raw_payload)])
    return {
        "schema": "cleanwin.ai-policy-simulation.v1",
        "execute_intent": execute,
        "delete_mode": delete_mode,
        "validation": validation,
        "decision": decision,
        "recommended_argv": recommended_argv,
        "safe_to_execute": bool(validation["valid"] and decision["allowed"] and execute),
    }
