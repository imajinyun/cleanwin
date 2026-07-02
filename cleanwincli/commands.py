"""CleanWin command dispatch — thin wrappers that route CLI commands to domain modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cleanwincli.ai_host_policy import render_ai_host_policy, validate_ai_host_policy
from cleanwincli.ai_readiness import ai_readiness_report, validate_ai_readiness
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_schema import tool_catalog
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.browser_inventory import browser_profile_inventory_report
from cleanwincli.cache_readiness import low_risk_cache_execution_readiness_report
from cleanwincli.contract_exposure import contract_exposure_matrix, validate_contract_exposure_matrix
from cleanwincli.debloat_privacy import debloat_privacy_report
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
from cleanwincli.workflow_artifacts import workflow_trace_report
from cleanwincli.workflow_router import workflow_router_report


def host_policy_report(*, validate: bool = False) -> dict[str, Any]:
    policy = render_ai_host_policy(tool_catalog=tool_catalog())
    if validate:
        return validate_ai_host_policy(policy)
    return policy

def ai_readiness_command(*, validate: bool = False) -> dict[str, Any]:
    report = ai_readiness_report()
    if validate:
        return validate_ai_readiness(report)
    return report

def ai_self_test_command() -> dict[str, Any]:
    return ai_self_test_report()

def ai_runbook_command() -> dict[str, Any]:
    return ai_runbook_report()

def contract_exposure_matrix_command(*, validate: bool = False) -> dict[str, Any]:
    report = contract_exposure_matrix()
    if validate:
        return validate_contract_exposure_matrix(report)
    return report

def workflow_router_command() -> dict[str, Any]:
    return workflow_router_report()

def environment_index_command() -> dict[str, Any]:
    return environment_index_report()

def workflow_trace_command() -> dict[str, Any]:
    return workflow_trace_report()

def recovery_readiness_command() -> dict[str, Any]:
    return recovery_readiness_report()

def low_risk_cache_readiness_command() -> dict[str, Any]:
    return low_risk_cache_execution_readiness_report()

def operation_log_readiness_command() -> dict[str, Any]:
    return operation_log_readiness_report()

def file_report_command() -> dict[str, Any]:
    return file_report()

def scan_governance_command() -> dict[str, Any]:
    return scan_governance_report()

def installed_app_inventory_command() -> dict[str, Any]:
    return installed_app_inventory_report()

def official_command_plan_command() -> dict[str, Any]:
    return official_command_plan_report()

def browser_profile_inventory_command() -> dict[str, Any]:
    return browser_profile_inventory_report()

def debloat_privacy_report_command() -> dict[str, Any]:
    return debloat_privacy_report()

def startup_service_inventory_command() -> dict[str, Any]:
    return startup_service_inventory_report()

def system_health_report_command() -> dict[str, Any]:
    return system_health_report()

def windows_inventory_command() -> dict[str, Any]:
    return windows_inventory_report()

def windows_native_artifacts_command() -> dict[str, Any]:
    return windows_native_artifacts_report()

def preset_catalog_command() -> dict[str, Any]:
    return preset_catalog_report()

def rule_pack_catalog_command() -> dict[str, Any]:
    return rule_pack_catalog_report()

def rule_quality_dashboard_command() -> dict[str, Any]:
    return rule_quality_dashboard_report()

def promotion_gates_command() -> dict[str, Any]:
    return promotion_gates_report()

def backup_delete_contract_command() -> dict[str, Any]:
    return backup_delete_contract_report()

def disable_revert_contract_command() -> dict[str, Any]:
    return disable_revert_contract_report()

def permanent_delete_denial_command() -> dict[str, Any]:
    return permanent_delete_denial_report()

def registry_privacy_plan_command() -> dict[str, Any]:
    return registry_privacy_change_plan_report()

def appx_removal_plan_command() -> dict[str, Any]:
    return appx_removal_plan_report()

def service_task_disable_plan_command() -> dict[str, Any]:
    return service_task_disable_plan_report()

def rollback_drill_report_command() -> dict[str, Any]:
    return rollback_drill_report()

def windows_artifact_layout_command() -> dict[str, Any]:
    return artifact_layout_report()

def windows_artifact_validate_command(manifest_path: Path | None = None) -> dict[str, Any]:
    return artifact_validation_report(manifest_path)

def windows_smoke_matrix_command() -> dict[str, Any]:
    return windows_smoke_matrix_report()

def windows_evidence_bundle_command() -> dict[str, Any]:
    return windows_evidence_bundle_report()
