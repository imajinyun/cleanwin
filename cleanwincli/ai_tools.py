"""CleanWin AI tools registry — catalog of AI/MCP tool schema providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.ai_host_policy import render_ai_host_policy
from cleanwincli.ai_readiness import ai_readiness_report
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_schema import (
    anthropic_tools_export,
    openai_functions_export,
    provider_export_parity,
    tool_catalog,
    validate_ai_schema,
)
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.ai_versioning import schema_registry
from cleanwincli.browser_inventory import browser_profile_inventory_report
from cleanwincli.cache_readiness import low_risk_cache_execution_readiness_report
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
from cleanwincli.external_rules import external_rule_translation_sample
from cleanwincli.file_reports import file_report
from cleanwincli.installed_apps import installed_app_inventory_report
from cleanwincli.official_commands import official_command_plan_report
from cleanwincli.operation_log_readiness import operation_log_readiness_report
from cleanwincli.presets import preset_catalog_report
from cleanwincli.promotion_gates import promotion_gates_report
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
