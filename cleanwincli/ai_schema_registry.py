"""AI schema registry and plan schema negotiation for cleanwin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cleanwincli.ai_schema_samples import schema_sample


@dataclass(frozen=True)
class SchemaEntry:
    name: str
    version: int
    module: str
    stability: str
    kind: str
    producer: str
    consumers: tuple[str, ...]
    latest: bool


_REGISTRY: tuple[tuple[str, int, str, str, str, str, tuple[str, ...]], ...] = (
    ("cleanwin.plan.v1", 1, "cleanwincli.models", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp")),
    ("cleanwin.inspect.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.execute.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.review.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp")),
    ("cleanwin.error.v1", 1, "cleanwincli.cli", "stable", "error", "cleanwin", ("cli", "ai-host", "mcp")),
    ("cleanwin.validate-plan.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.doctor.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.filesystem-identity.v1", 1, "cleanwincli.identity", "stable", "contract", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.ai-tools.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-openai-functions.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("openai" ,)),
    ("cleanwin.ai-anthropic-tools.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("anthropic",)),
    ("cleanwin.ai-provider-export-parity.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host",)),
    ("cleanwin.ai-schema-validation.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-tool-argument-validation.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-host-policy.v1", 1, "cleanwincli.ai_host_policy", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-host-policy-validation.v1", 1, "cleanwincli.ai_host_policy", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-host-tool-call-decision.v1", 1, "cleanwincli.ai_host_policy", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-policy-simulation.v1", 1, "cleanwincli.core", "stable", "ai", "cleanwin", ("ai-host", "cli")),
    ("cleanwin.ai-schema-registry.v1", 1, "cleanwincli.ai_versioning", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-readiness.v1", 1, "cleanwincli.ai_readiness", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.ai-readiness-validation.v1", 1, "cleanwincli.ai_readiness", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-self-test.v1", 1, "cleanwincli.ai_self_test", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.ai-runbook.v1", 1, "cleanwincli.ai_runbook", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.workflow-router.v1", 1, "cleanwincli.workflow_router", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.environment-index.v1", 1, "cleanwincli.environment_index", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.workflow-decision.v1", 1, "cleanwincli.workflow_artifacts", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.workflow-trace.v1", 1, "cleanwincli.workflow_artifacts", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.recovery-readiness.v1", 1, "cleanwincli.recovery", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.backup-delete-contract.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.file-report.v1", 1, "cleanwincli.file_reports", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.scan-governance.v1", 1, "cleanwincli.scan_governance", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.external-rule-review.v1", 1, "cleanwincli.scan_governance", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.script-boundary-contract.v1", 1, "cleanwincli.scan_governance", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.script-boundary-validation.v1", 1, "cleanwincli.scan_governance", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.external-rule-translation.v1", 1, "cleanwincli.external_rules", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.external-rule-candidate.v1", 1, "cleanwincli.external_rules", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.external-rule-import-sandbox.v1", 1, "cleanwincli.external_rules", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.external-rule-quality-summary.v1", 1, "cleanwincli.external_rules", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.installed-app-inventory.v1", 1, "cleanwincli.installed_apps", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.installed-app-leftover-evidence-link.v1", 1, "cleanwincli.installed_apps", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-inventory.v1", 1, "cleanwincli.windows_inventory", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-inventory-collection-plan.v1", 1, "cleanwincli.windows_inventory", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-package-classification.v1", 1, "cleanwincli.windows_inventory", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-package-snapshot.v1", 1, "cleanwincli.windows_inventory", "stable", "artifact", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.provisioned-appx-package-snapshot.v1", 1, "cleanwincli.windows_inventory", "stable", "artifact", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.browser-profile-inventory.v1", 1, "cleanwincli.browser_inventory", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.locked-state.v1", 1, "cleanwincli.browser_inventory", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.official-command-plan.v1", 1, "cleanwincli.official_commands", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.official-action-contract.v1", 1, "cleanwincli.official_commands", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.preset-catalog.v1", 1, "cleanwincli.presets", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.preset-plan-template.v1", 1, "cleanwincli.presets", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.rule-pack-catalog.v1", 1, "cleanwincli.rule_catalog", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.cleanup-rule-pack.v1", 1, "cleanwincli.rule_catalog", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.rule-quality-score.v1", 1, "cleanwincli.rule_catalog", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.rule-quality-dashboard.v1", 1, "cleanwincli.rule_catalog", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.promotion-gates.v1", 1, "cleanwincli.promotion_gates", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.promotion-gate-validation.v1", 1, "cleanwincli.promotion_gates", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.low-risk-cache-execution-readiness.v1", 1, "cleanwincli.cache_readiness", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.low-risk-cache-readiness-validation.v1", 1, "cleanwincli.cache_readiness", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.operation-log-readiness.v1", 1, "cleanwincli.operation_log_readiness", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.operation-log-readiness-validation.v1", 1, "cleanwincli.operation_log_readiness", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.contract-exposure-matrix.v1", 1, "cleanwincli.contract_exposure", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.contract-exposure-validation.v1", 1, "cleanwincli.contract_exposure", "stable", "governance", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.debloat-privacy-report.v1", 1, "cleanwincli.debloat_privacy", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.registry-privacy-evidence.v1", 1, "cleanwincli.debloat_privacy", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.disable-revert-contract.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.permanent-delete-denial.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.registry-privacy-plan.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.registry-privacy-change.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.registry-privacy-revert.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.registry-privacy-plan-validation.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-removal-plan.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-removal-change.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-removal-revert.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-removal-plan-validation.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.service-task-disable-plan.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.service-disable-change.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.scheduled-task-disable-change.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.service-task-revert.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.service-task-disable-plan-validation.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.rollback-drill-report.v1", 1, "cleanwincli.execution_contracts", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.rollback-drill-case.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.rollback-drill-validation.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.registry-privacy-rollback-drill.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.appx-per-user-rollback-drill.v1", 1, "cleanwincli.execution_contracts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.startup-service-inventory.v1", 1, "cleanwincli.startup_inventory", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.system-health-report.v1", 1, "cleanwincli.system_health", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.system-health-evidence.v1", 1, "cleanwincli.system_health", "stable", "report", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.dism-component-store-analysis.v1", 1, "cleanwincli.system_health", "stable", "artifact", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.dism-health-evidence.v1", 1, "cleanwincli.system_health", "stable", "artifact", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.pending-reboot-registry-evidence.v1", 1, "cleanwincli.system_health", "stable", "artifact", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.windows-native-artifact-layout.v1", 1, "cleanwincli.windows_artifact_validation", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-native-collector-manifest.v1", 1, "cleanwincli.windows_artifact_validation", "stable", "artifact", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.windows-native-artifact-validation.v1", 1, "cleanwincli.windows_artifact_validation", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-native-artifact-validation-issue.v1", 1, "cleanwincli.windows_artifact_validation", "stable", "contract", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.windows-native-artifacts.v1", 1, "cleanwincli.windows_native_artifacts", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-native-artifact-contract.v1", 1, "cleanwincli.windows_native_artifacts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-native-collector-wrapper.v1", 1, "cleanwincli.windows_native_artifacts", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-native-artifact-parse.v1", 1, "cleanwincli.windows_native_artifacts", "stable", "artifact", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.windows-smoke-matrix.v1", 1, "cleanwincli.windows_smoke", "stable", "governance", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.windows-snapshot-artifact-matrix.v1", 1, "cleanwincli.windows_smoke", "stable", "governance", "cleanwin", ("cli", "ai-host", "ci")),
    ("cleanwin.windows-evidence-bundle.v1", 1, "cleanwincli.evidence_bundle", "stable", "artifact", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.windows-evidence-bundle-record.v1", 1, "cleanwincli.evidence_bundle", "stable", "artifact", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.mcp-tool-error.v1", 1, "cleanwincli.mcp_server", "stable", "mcp", "cleanwin", ("mcp",)),
    ("cleanwin.mcp-text-output.v1", 1, "cleanwincli.mcp_server", "stable", "mcp", "cleanwin", ("mcp",)),
)

LATEST_PLAN_SCHEMA = "cleanwin.plan.v1"
SUPPORTED_PLAN_SCHEMAS: tuple[str, ...] = (LATEST_PLAN_SCHEMA,)


def schema_registry() -> dict[str, Any]:
    entries = [
        {
            "name": name,
            "version": version,
            "module": module,
            "stability": stability,
            "kind": kind,
            "producer": producer,
            "consumers": list(consumers),
            "latest": True,
        }
        for name, version, module, stability, kind, producer, consumers in _REGISTRY
    ]
    samples = {}
    for entry in entries:
        sample = schema_sample(str(entry["name"]))
        if sample is not None:
            samples[entry["name"]] = sample
    return {
        "schema": "cleanwin.ai-schema-registry.v1",
        "latest_plan_schema": LATEST_PLAN_SCHEMA,
        "supported_plan_schemas": list(SUPPORTED_PLAN_SCHEMAS),
        "schema_count": len(entries),
        "entries": entries,
        "samples": samples,
    }



def negotiate_plan_schema(requested: str | None) -> dict[str, Any]:
    if not requested:
        requested = LATEST_PLAN_SCHEMA
    accepted = requested in SUPPORTED_PLAN_SCHEMAS
    return {
        "schema": "cleanwin.validate-plan.v1",
        "requested_schema": requested,
        "accepted": accepted,
        "selected_schema": requested if accepted else None,
        "supported_plan_schemas": list(SUPPORTED_PLAN_SCHEMAS),
        "error": None if accepted else f"Unsupported plan schema: {requested}",
    }

