"""AI schema registry and plan schema negotiation for cleanwin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cleanwincli.evidence_bundle import windows_evidence_bundle_report
from cleanwincli.execution_contracts import (
    appx_removal_plan_report,
    registry_privacy_change_plan_report,
    rollback_drill_report,
    service_task_disable_plan_report,
    validate_appx_removal_plan,
    validate_registry_privacy_change_plan,
    validate_rollback_drills,
    validate_service_task_disable_plan,
)
from cleanwincli.external_rules import external_rule_translation_sample
from cleanwincli.promotion_gates import validate_promotion_gate_action
from cleanwincli.rule_catalog import rule_pack_catalog_report, rule_quality_dashboard_report
from cleanwincli.system_health import system_health_evidence_report
from cleanwincli.windows_artifact_validation import (
    artifact_layout_report,
    artifact_validation_sample,
    sample_collector_manifest,
)
from cleanwincli.windows_inventory import appx_snapshot_artifact_contract
from cleanwincli.windows_native_artifacts import (
    windows_native_artifact_parse_sample,
    windows_native_artifacts_report,
    windows_native_collector_wrapper_contract,
)
from cleanwincli.windows_smoke import windows_snapshot_artifact_matrix


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


def _sample_identity() -> dict[str, Any]:
    return {
        "schema": "cleanwin.filesystem-identity.v1",
        "path": r"C:\\Users\\tester\\AppData\\Local\\npm-cache\\_cacache",
        "canonical_path": r"C:\\Users\\tester\\AppData\\Local\\npm-cache\\_cacache",
        "platform_os_name": "nt",
        "source": "python-stdlib-stat+windows-native",
        "exists": True,
        "file_type": "directory",
        "is_symlink": False,
        "is_junction": False,
        "size_bytes": 1024,
        "modified_ns": 1710000000000000000,
        "device": 1234,
        "file_id": 5678,
        "mode": 16895,
        "windows_file_attributes": 16,
        "windows_reparse_tag": None,
        "owner_sid": "S-1-5-21-example",
    }


def _sample_candidate() -> dict[str, Any]:
    return {
        "path": r"C:\\Users\\tester\\AppData\\Local\\npm-cache\\_cacache",
        "category": "dev-cache",
        "size_bytes": 1024,
        "reason": r"npm cache entry under C:\\Users\\tester\\AppData\\Local\\npm-cache",
        "safe_to_delete": True,
        "delete_mode": "recycle",
        "requires_admin": False,
        "risk": "low",
        "discovered_by": "collector",
        "modified_at": "2026-06-20T00:00:00+00:00",
        "identity": _sample_identity(),
        "rule_id": "dev-cache.npm.cache",
        "cache_owner": "npm",
        "official_cleanup_command": "npm cache clean --force",
        "safe_to_delete_rationale": "npm content-addressed cache entries are verified package artifacts that can be regenerated by npm.",
    }


def _sample_package_candidate() -> dict[str, Any]:
    candidate = _sample_candidate()
    candidate.update(
        {
            "path": r"C:\Users\tester\AppData\Local\Microsoft\WinGet\Packages",
            "category": "package-cache",
            "reason": r"WinGet package cache at C:\Users\tester\AppData\Local\Microsoft\WinGet\Packages",
            "rule_id": "package-cache.winget.packages",
            "cache_owner": "WinGet",
            "official_cleanup_command": "winget source reset --force or remove stale installer payloads only after review",
            "safe_to_delete_rationale": "WinGet package download payloads are installer artifacts that can be re-downloaded by winget.",
        }
    )
    return candidate


def _sample_browser_candidate() -> dict[str, Any]:
    candidate = _sample_candidate()
    candidate.update(
        {
            "path": r"C:\Users\tester\AppData\Local\Google\Chrome\User Data\Default\Cache",
            "category": "browser-cache",
            "reason": r"Google Chrome cache directory at C:\Users\tester\AppData\Local\Google\Chrome\User Data\Default\Cache",
            "rule_id": "browser-cache.chrome.default.cache",
            "cache_owner": "Google Chrome",
            "official_cleanup_command": "Use Chrome > Clear browsing data and clear cached images/files only.",
            "safe_to_delete_rationale": "Chrome Cache directory stores temporary web resources separate from Cookies, Login Data, and profile databases.",
        }
    )
    return candidate


def _sample_app_leftover_candidate() -> dict[str, Any]:
    candidate = _sample_candidate()
    candidate.update(
        {
            "path": r"C:\Users\tester\AppData\Roaming\Code\CachedData",
            "category": "app-leftovers",
            "reason": r"Visual Studio Code uninstall leftover cache/log at C:\Users\tester\AppData\Roaming\Code\CachedData",
            "rule_id": "app-leftovers.vscode.cached-data",
            "cache_owner": "Visual Studio Code",
            "official_cleanup_command": "Uninstall Visual Studio Code from Settings > Apps, then remove reviewed Code cache/log leftovers.",
            "safe_to_delete_rationale": "VS Code CachedData contains regenerated extension host and workbench cache artifacts, not user projects or settings.",
        }
    )
    return candidate


def _sample_finding() -> dict[str, Any]:
    return {
        "category": "docker-report",
        "title": "Docker cleanup is read-only",
        "detail": "Docker images, containers, volumes, BuildKit cache, and Docker Desktop WSL data are reported only.",
        "risk": "high",
        "safe_to_execute": False,
        "rule_id": "report.docker.manual-cleanup",
        "owner": "Docker Desktop",
        "official_cleanup_command": "docker system df; docker builder prune; docker system prune --volumes only after manual review",
        "review_details": {
            "suggested_paths": [r"%LOCALAPPDATA%\\Docker", r"%LOCALAPPDATA%\\Docker\\wsl"],
            "risk_notes": ["Docker volumes may contain databases or local development state."],
            "manual_review_steps": ["Inspect disk usage with docker system df before pruning."],
        },
    }


def _sample_recovery_readiness() -> dict[str, Any]:
    return {
        "schema": "cleanwin.recovery-readiness.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "ready_for_recovery_planning": True,
        "ready_for_system_execution": False,
        "capabilities": [
            {
                "id": "system_restore_point_supported",
                "available": True,
                "reason": "windows-host",
                "evidence": {"os_name": "nt", "platform": "Windows-11"},
            },
            {
                "id": "service_registry_export_supported",
                "available": True,
                "reason": "windows-host",
                "evidence": {"command": r"reg export HKLM\SYSTEM\CurrentControlSet\Services\<service-name>"},
            },
            {
                "id": "scheduled_task_xml_export_supported",
                "available": True,
                "reason": "windows-host",
                "evidence": {"command": "schtasks /Query /TN <task-name> /XML"},
            }
        ],
        "snapshot_specs": [
            {
                "id": "system-restore-point",
                "purpose": "Create an OS rollback point before service, task, policy, AppX, or Windows cleanup changes.",
                "command": ["powershell", "-NoProfile", "Checkpoint-Computer", "-Description", "CleanWin pre-change restore point"],
                "output_schema": "cleanwin.snapshot.system-restore-point.v1",
                "required_before": ["windows-cleanup", "debloat", "service-change"],
                "rollback_use": "Use Windows System Restore if a system-level change breaks Windows behavior.",
                "executed_by_report": False,
            },
            {
                "id": "service-registry-export",
                "purpose": "Export exact service registry keys before changing service configuration.",
                "command": ["reg", "export", r"HKLM\SYSTEM\CurrentControlSet\Services\<service-name>", "<snapshot-file.reg>", "/y"],
                "output_schema": "cleanwin.snapshot.service-registry-export.v1",
                "required_before": ["service-change", "debloat"],
                "rollback_use": "Import the exported service registry key after review to restore service configuration.",
                "executed_by_report": False,
            },
            {
                "id": "scheduled-task-xml-export",
                "purpose": "Export scheduled task XML before disabling or deleting tasks.",
                "command": ["schtasks", "/Query", "/TN", "<task-name>", "/XML"],
                "output_schema": "cleanwin.snapshot.scheduled-task-xml-export.v1",
                "required_before": ["scheduled-task-change", "debloat"],
                "rollback_use": "Recreate the scheduled task from the XML export if rollback is required.",
                "executed_by_report": False,
            }
        ],
        "execution_gate": {
            "requires_recovery_snapshot": True,
            "requires_restore_point_for_system_changes": True,
            "requires_registry_export_for_registry_changes": True,
            "requires_snapshot_reference_in_plan": True,
            "system_execution_enabled": False,
        },
        "non_goals": ["This report does not create restore points."],
    }


def _sample_installed_app_inventory() -> dict[str, Any]:
    return {
        "schema": "cleanwin.installed-app-inventory.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "sources": [
            {
                "id": "registry-uninstall-hklm",
                "available": True,
                "reason": "registry-key-read",
                "evidence": {"key": r"HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"},
            },
            {
                "id": "winget",
                "available": False,
                "reason": "external-command-not-executed",
                "evidence": {"command": "winget list"},
            },
        ],
        "applications": [
            {
                "source": "registry-uninstall",
                "key_path": r"HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Slack",
                "display_name": "Slack",
                "display_version": "4.40.0",
                "publisher": "Slack Technologies LLC",
                "install_location": r"C:\\Users\\tester\\AppData\\Local\\slack",
                "product_code": "",
                "package_id": "",
                "winget_id": "",
                "uninstall_string_present": True,
                "quiet_uninstall_string_present": False,
                "estimated_size_kb": 250000,
                "windows_installer": False,
                "system_component": False,
                "release_type": "",
                "install_date": "20260620",
                "uninstall_strategy": {
                    "schema": "cleanwin.uninstall-strategy.v1",
                    "strategy_id": "registry-uninstall-string",
                    "preferred": "Settings > Apps or vendor uninstall entry",
                    "confidence": "high",
                    "risk": "medium",
                    "uninstall_string_present": True,
                    "quiet_uninstall_string_present": False,
                    "windows_installer": False,
                    "system_component": False,
                    "executes_by_report": False,
                    "auto_executable": False,
                    "review_steps": ["Review application identity, publisher, install location, and source before uninstall."],
                },
            }
        ],
        "leftover_correlations": [
            {
                "rule_id": "app-leftovers.slack.cache",
                "owner": "Slack",
                "state": "installed-application-present",
                "recommendation": "skip-leftover-cleanup-until-uninstalled",
                "leftover_path": "",
                "matched_applications": [
                    {
                        "display_name": "Slack",
                        "publisher": "Slack Technologies LLC",
                        "source": "registry-uninstall",
                        "install_location": r"C:\\Users\\tester\\AppData\\Local\\slack",
                        "uninstall_key": r"HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Slack",
                        "product_code": "",
                        "package_id": "",
                        "winget_id": "",
                    }
                ],
                "evidence_links": [_sample_installed_app_leftover_evidence_link()],
            }
        ],
        "summary": {
            "application_count": 1,
            "registry_application_count": 1,
            "leftover_correlation_count": 1,
            "potential_uninstall_leftover_count": 0,
            "installed_application_present_count": 1,
            "uninstall_strategy_counts": {"registry-uninstall-string": 1},
            "manual_review_strategy_count": 0,
        },
        "non_goals": ["This report does not uninstall applications."],
    }


def _sample_installed_app_leftover_evidence_link() -> dict[str, Any]:
    return {
        "schema": "cleanwin.installed-app-leftover-evidence-link.v1",
        "owner": "Slack",
        "match_basis": "owner-token",
        "matched_fields": ["display_name", "publisher", "install_location", "key_path"],
        "display_name": "Slack",
        "publisher": "Slack Technologies LLC",
        "install_location": r"C:\\Users\\tester\\AppData\\Local\\slack",
        "uninstall_key": r"HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Slack",
        "product_code": "",
        "winget_id": "",
        "package_manager": "",
        "package_id": "",
        "source": "registry-uninstall",
        "safe_to_execute": False,
        "executes_by_report": False,
    }


def _sample_windows_inventory() -> dict[str, Any]:
    collection_plan = _sample_windows_inventory_collection_plan()
    return {
        "schema": "cleanwin.windows-inventory.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "sections": [
            {
                "id": "appx-packages",
                "title": "Installed AppX/MSIX packages",
                "risk": "high",
                "source": {
                    "id": "appx-packages",
                    "available": True,
                    "reason": "test-fixture",
                    "evidence": {
                        "fixture_item_count": 1,
                        "collection_method": "powershell-appx-package-inventory",
                        "executes_by_report": False,
                        "expected_artifact_schema": "cleanwin.appx-package-snapshot.v1",
                    },
                },
                "collection_plan": collection_plan,
                "items": [
                    {
                        "name": "Microsoft.XboxGamingOverlay",
                        "publisher": "Microsoft",
                        "cleanwin_classification": _sample_appx_package_classification(),
                    }
                ],
                "item_count": 1,
                "review_guidance": ["Classify Microsoft, OEM, framework, and user apps before any future debloat plan."],
                "protected_surfaces": ["package identity", "per-user registration", "framework packages"],
                "executes_by_report": False,
                "auto_executable": False,
            },
            {
                "id": "component-store",
                "title": "Windows component store",
                "risk": "high",
                "source": {
                    "id": "component-store",
                    "available": False,
                    "reason": "external-command-not-executed",
                    "evidence": {
                        "command": "dism.exe /Online /Cleanup-Image /AnalyzeComponentStore",
                        "command_argv": ["dism.exe", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"],
                        "collection_method": "dism-component-store-analysis",
                        "requires_admin": True,
                        "windows_only": True,
                        "executes_by_report": False,
                        "expected_artifact_schema": "cleanwin.component-store-analysis.v1",
                    },
                },
                "collection_plan": {
                    **collection_plan,
                    "method": "dism-component-store-analysis",
                    "command": ["dism.exe", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"],
                    "command_display": "dism.exe /Online /Cleanup-Image /AnalyzeComponentStore",
                    "expected_artifact_schema": "cleanwin.component-store-analysis.v1",
                    "promotion_gate_id": "windows-inventory-to-component-store-cleanup",
                },
                "items": [],
                "item_count": 0,
                "review_guidance": ["Use DISM or Storage Settings only; never delete WinSxS directly."],
                "protected_surfaces": [r"C:\\Windows\\WinSxS", "servicing stack", "component rollback"],
                "executes_by_report": False,
                "auto_executable": False,
            },
        ],
        "summary": {
            "section_count": 11,
            "available_section_count": 1,
            "high_risk_section_count": 6,
            "total_item_count": 1,
            "appx_package_count": 1,
            "provisioned_appx_package_count": 0,
            "windows_feature_count": 0,
            "executes_system_command_count": 0,
            "requires_admin_collection_count": 7,
            "collection_plan_count": 11,
            "appx_classification_count": 1,
            "appx_protected_by_default_count": 0,
            "appx_manual_review_count": 1,
            "provisioned_appx_future_user_impact_count": 0,
        },
        "promotion_gate": {
            "execution_enabled": False,
            "requires_recovery_readiness": True,
            "requires_official_command_plan": True,
            "requires_human_review": True,
            "requires_matching_dry_run_token": True,
        },
        "non_goals": ["This report does not execute PowerShell, DISM, winget, or Windows Settings commands."],
    }


def _sample_windows_inventory_collection_plan() -> dict[str, Any]:
    return {
        "schema": "cleanwin.windows-inventory-collection-plan.v1",
        "method": "powershell-appx-package-inventory",
        "command": ["powershell.exe", "Get-AppxPackage", "-AllUsers"],
        "command_display": "powershell.exe Get-AppxPackage -AllUsers",
        "windows_only": True,
        "requires_admin": True,
        "executes_by_report": False,
        "default_state": "not-executed",
        "expected_artifact_schema": "cleanwin.appx-package-snapshot.v1",
        "promotion_gate_id": "windows-inventory-to-appx-change",
        "artifact_contract": appx_snapshot_artifact_contract(provisioned=False),
        "failure_modes": [
            "not-windows",
            "requires-admin",
            "command-unavailable",
            "policy-restricted",
            "external-command-not-executed",
        ],
    }


def _sample_appx_package_classification() -> dict[str, Any]:
    return {
        "schema": "cleanwin.appx-package-classification.v1",
        "category": "consumer-app",
        "confidence": "medium",
        "matched_tokens": ["xbox"],
        "package_family_name": "Microsoft.XboxGamingOverlay_8wekyb3d8bbwe",
        "publisher": "Microsoft",
        "non_removable": False,
        "dependency": False,
        "protected_by_default": False,
        "review_action": "manual-review",
        "rationale": "Consumer bundled apps may be removable for some users but require workflow, dependency, and recovery review first.",
        "provisioned_state": False,
        "future_user_profile_impact": False,
        "promotion_gate_id": "windows-inventory-to-appx-change",
        "safe_to_execute": False,
    }


def _sample_file_report() -> dict[str, Any]:
    return {
        "schema": "cleanwin.file-report.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "scan_roots": [r"C:\\Users\\tester\\Downloads", r"C:\\Users\\tester\\OneDrive"],
        "traversal_budget": {"max_files": 2000, "limit_reached": False, "skipped_roots": [], "skipped_dirs": []},
        "large_files": [
            {
                "path": r"C:\\Users\\tester\\Downloads\\installer.iso",
                "name": "installer.iso",
                "extension": ".iso",
                "size_bytes": 734003200,
                "modified_ns": 1710000000000000000,
                "onedrive_or_cloud_path": False,
                "safe_to_execute": False,
                "review_required": True,
            }
        ],
        "duplicate_groups": [
            {
                "digest": "0" * 64,
                "hash_scope": "first-1048576-bytes",
                "size_bytes": 104857600,
                "file_count": 2,
                "potential_reclaimable_bytes": 104857600,
                "files": [],
                "safe_to_execute": False,
                "review_required": True,
            }
        ],
        "extension_groups": [{"extension": ".iso", "file_count": 1, "total_bytes": 734003200}],
        "summary": {
            "file_count": 2,
            "bytes_scanned": 838860800,
            "large_file_count": 1,
            "duplicate_group_count": 1,
            "potential_duplicate_reclaimable_bytes": 104857600,
            "onedrive_or_cloud_file_count": 0,
        },
        "execution_gate": {
            "file_execution_enabled": False,
            "requires_human_review": True,
            "requires_backup_or_cloud_sync_review": True,
            "requires_exact_file_identity": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not delete large files."],
    }


def _sample_scan_governance() -> dict[str, Any]:
    return {
        "schema": "cleanwin.scan-governance.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "scan_budgets": [
            {
                "id": "file-report",
                "surface": "large-file and duplicate-file reporting",
                "max_files_scanned": 2000,
                "max_hash_bytes_per_file": 1048576,
                "protected_directory_policy": "skip-system-app-dependency-roots",
                "permission_error_policy": "aggregate-and-continue",
                "locked_file_policy": "report-and-skip",
            }
        ],
        "external_rule_contract": {
            "schema": "cleanwin.external-rule-review.v1",
            "default_state": "report-only",
            "execution_enabled": False,
            "required_source_evidence": ["upstream_project", "upstream_rule_id_or_commit", "license", "original_pattern", "translated_cleanwin_rule"],
            "required_safety_evidence": ["owner", "category", "default_path", "sensitive_exclusions", "official_cleanup_command", "rationale", "test_fixture"],
            "blocked_patterns": ["raw shell command strings", "browser profile root deletion", "user document directory deletion"],
            "promotion_requirements": ["schema validation", "fixture coverage", "review-plan evidence", "dry-run evidence", "promotion-gate approval"],
        },
        "script_boundary_contract": {
            "schema": "cleanwin.script-boundary-contract.v1",
            "default_state": "read-only-or-local-artifact-only",
            "execution_enabled": False,
            "makefile": {
                "managed_venv": ".venv",
                "required_test_entrypoints": ["make pytest", "make pytest-governance-smoke"],
                "cleanup_targets": [".pytest_cache", ".coverage", "coverage.xml", "htmlcov", "__pycache__", "build", "dist", "cleanwin.egg-info", ".mypy_cache", ".ruff_cache"],
                "protected_targets": [".venv", ".aiflow", ".harness", ".git"],
            },
            "native_collector": {
                "script_path": "scripts/collect-cleanwin-artifacts.ps1",
                "allowed_write_root": "operator-provided ArtifactRoot",
                "required_root_checks": ["ArtifactRoot must not be empty", "ArtifactRoot must not be a filesystem root"],
                "forbidden_command_fragments": ["reg.exe import", "RestoreHealth"],
            },
        },
        "script_boundary_validation": {
            "schema": "cleanwin.script-boundary-validation.v1",
            "valid": True,
            "violation_count": 0,
            "violations": [],
        },
        "summary": {"budget_count": 1, "external_rule_execution_enabled": False, "blocked_pattern_count": 3},
        "release_gate": {"requires_budget_tests": True, "requires_external_rule_review_tests": True, "requires_script_boundary_tests": True, "requires_quality": True, "required_commands": ["make quality"], "blocks_execution_expansion": True},
        "non_goals": ["This report does not import external cleaner rules automatically."],
    }


def _sample_official_command_plan() -> dict[str, Any]:
    return {
        "schema": "cleanwin.official-command-plan.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "commands": [
            {
                "id": "windows.component-cleanup.dism-startcomponentcleanup",
                "category": "windows-component-cleanup",
                "owner": "Windows servicing",
                "title": "Component store cleanup through DISM",
                "command": ["dism.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
                "risk": "high",
                "cleanup_surface": [r"C:\\Windows\\WinSxS"],
                "prerequisites": ["No pending reboot", "Run from elevated terminal"],
                "required_snapshots": ["system-restore-point", "registry-export"],
                "review_steps": ["Use DISM instead of deleting WinSxS files directly."],
                "action_contract": {
                    "schema": "cleanwin.official-action-contract.v1",
                    "action_id": "windows.component-cleanup.dism-startcomponentcleanup",
                    "allowlisted_command": ["dism.exe", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
                    "argument_policy": "exact-argv-only",
                    "execution_enabled": False,
                    "requires_human_review": True,
                    "requires_matching_dry_run_token": True,
                    "rollback_required": True,
                    "required_privileges": ["administrator"],
                    "blocked_without": ["windows-smoke-evidence", "recovery-readiness"],
                    "expected_effects": ["Reduce superseded Windows component store payloads."],
                    "forbidden_effects": ["Direct WinSxS file deletion"],
                },
                "executes_by_report": False,
                "auto_executable": False,
            }
        ],
        "summary": {"command_count": 1, "auto_executable_count": 0, "requires_snapshot_count": 1, "high_risk_count": 1, "action_contract_count": 1, "execution_enabled_action_count": 0},
        "execution_gate": {
            "system_execution_enabled": False,
            "requires_human_review": True,
            "requires_recovery_snapshot_for_system_surfaces": True,
            "requires_elevated_terminal_for_dism": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not execute DISM, Disk Cleanup, Settings URI handlers, or Defender commands."],
    }


def _sample_preset_catalog() -> dict[str, Any]:
    return {
        "schema": "cleanwin.preset-catalog.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "presets": [
            {
                "id": "preset.daily-safe-cache",
                "title": "Daily safe cache review",
                "categories": ["temp", "dev-cache", "package-cache"],
                "rule_ids": ["dev-cache.npm.cache", "dev-cache.pip.cache", "package-cache.winget.packages"],
                "risk": "low",
                "target_user": "general-developer",
                "plan_template": {
                    "schema": "cleanwin.preset-plan-template.v1",
                    "argv": ["cleanwin", "--json", "plan", "--categories", "temp,dev-cache,package-cache"],
                    "destructive": False,
                    "execution_enabled": False,
                    "requires_plan_review": True,
                    "requires_validate_plan": True,
                    "requires_matching_dry_run_token": True,
                },
                "review_steps": ["Review candidate paths before execution."],
            }
        ],
        "summary": {"preset_count": 1, "execution_enabled_count": 0, "rule_id_count": 3},
        "execution_gate": {
            "preset_execution_enabled": False,
            "requires_explicit_plan_generation": True,
            "requires_validate_plan": True,
            "requires_human_review": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not execute presets."],
    }


def _sample_debloat_privacy_report() -> dict[str, Any]:
    return {
        "schema": "cleanwin.debloat-privacy-report.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "sources": [{"id": "registry-fixture", "available": True, "reason": "registry-value-read", "evidence": {"key": "HKLM\\...\\AllowTelemetry"}}],
        "findings": [
            {
                "id": "privacy.telemetry.allow-telemetry",
                "title": "Windows telemetry policy",
                "kind": "registry-policy",
                "risk": "high",
                "state": "review-recommended",
                "registry_value": r"HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection\\AllowTelemetry",
                "observed_value": "3",
                "expected_private_values": ["0"],
                "change_evidence": {
                    "schema": "cleanwin.registry-privacy-evidence.v1",
                    "hive": "HKLM",
                    "subkey_path": r"SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection",
                    "value_name": "AllowTelemetry",
                    "observed_value": "3",
                    "expected_private_values": ["0"],
                    "exact_registry_value": r"HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection\\AllowTelemetry",
                    "required_export_command": ["reg.exe", "export", r"HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection", "<export-file.reg>", "/y"],
                    "rollback_metadata_required": ["hive", "subkey_path", "value_name", "previous_value", "registry_export_ref"],
                },
                "safe_to_execute": False,
                "review_steps": ["Export the policy key before any future registry mutation."],
            }
        ],
        "summary": {
            "finding_count": 1,
            "registry_policy_count": 125,
            "review_recommended_count": 1,
            "privacy_hardened_count": 0,
            "appx_review_count": 0,
            "oem_location_count": 0,
        },
        "execution_gate": {
            "system_execution_enabled": False,
            "requires_restore_point": True,
            "requires_registry_export": True,
            "requires_appx_inventory_snapshot": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not remove AppX packages."],
    }


def _sample_system_health_report() -> dict[str, Any]:
    return {
        "schema": "cleanwin.system-health-report.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "recommendations": [
            {
                "id": "health.component-store.dism-scanhealth",
                "title": "Check Windows component store health",
                "symptom": "Windows updates, optional features, or servicing operations fail.",
                "commands": [["dism.exe", "/Online", "/Cleanup-Image", "/ScanHealth"]],
                "risk": "medium",
                "prerequisites": ["Run from elevated terminal"],
                "evidence_required": ["DISM log excerpt", "Windows version", "pending reboot state"],
                "review_steps": ["Run scan commands before any repair command."],
                "executes_by_report": False,
                "auto_executable": False,
                "safe_to_execute": False,
            },
            {
                "id": "health.component-store.dism-checkhealth",
                "title": "Fast component store corruption check",
                "symptom": "A quick read-only health indicator is needed before considering DISM repair workflows.",
                "commands": [["dism.exe", "/Online", "/Cleanup-Image", "/CheckHealth"]],
                "risk": "low",
                "prerequisites": ["Run from elevated terminal", "No active Windows Update installation"],
                "evidence_required": ["DISM CheckHealth result", "Windows version", "pending reboot state"],
                "review_steps": ["Use CheckHealth before ScanHealth when only a quick corruption indicator is needed.", "Do not run RestoreHealth from this report."],
                "executes_by_report": False,
                "auto_executable": False,
                "safe_to_execute": False,
            },
            {
                "id": "health.windows-update.pending-reboot-review",
                "title": "Review pending reboot state before cleanup",
                "symptom": "Component store, update cache, or driver cleanup is being considered while Windows may have pending operations.",
                "commands": [
                    ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"],
                    ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"],
                ],
                "risk": "medium",
                "prerequisites": ["Run from elevated terminal", "Capture registry query exit codes"],
                "evidence_required": ["CBS RebootPending query result", "Windows Update RebootRequired query result", "recent update history"],
                "review_steps": ["Postpone cleanup if pending reboot keys are present.", "Capture query output before any servicing cleanup."],
                "executes_by_report": False,
                "auto_executable": False,
                "safe_to_execute": False,
            }
        ],
        "summary": {"recommendation_count": 3, "auto_executable_count": 0, "elevated_recommendation_count": 3},
        "execution_gate": {
            "system_repair_execution_enabled": False,
            "requires_human_review": True,
            "requires_admin_for_repair_tools": True,
            "requires_log_capture": True,
            "requires_backup_before_repair_flags": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not execute DISM, SFC, CHKDSK, troubleshooters, or Settings URI handlers."],
    }


def _sample_system_health_evidence_report() -> dict[str, Any]:
    return system_health_evidence_report(
        analyze_component_store_output="""
Windows Explorer Reported Size of Component Store : 8.35 GB
Actual Size of Component Store : 7.25 GB
Shared with Windows : 5.10 GB
Backups and Disabled Features : 1.80 GB
Cache and Temporary Data : 350.00 MB
Date of Last Cleanup : 2026-06-01 12:00:00
Component Store Cleanup Recommended : Yes
""",
        scanhealth_output="The component store is repairable.\nThe operation completed successfully.",
        checkhealth_output="No component store corruption detected.\nThe operation completed successfully.",
        pending_reboot_queries=[
            {
                "id": "cbs-reboot-pending",
                "command": ["reg", "query", r"HKLM\...\RebootPending"],
                "exit_code": 0,
                "stdout": r"HKEY_LOCAL_MACHINE\...\RebootPending",
                "stderr": "",
            }
        ],
    )


def _sample_disable_revert_contract() -> dict[str, Any]:
    return {
        "schema": "cleanwin.disable-revert-contract.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "action_contracts": [
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
                "required_review_evidence": ["task_to_run", "publisher", "target_path", "target_status", "target_exists", "run_as_user", "run_level", "xml_snapshot_required", "risk"],
                "revert_plan_schema": "cleanwin.revert.scheduled-task.v1",
                "execution_enabled": False,
                "auto_executable": False,
            }
        ],
        "summary": {"contract_count": 3, "execution_enabled_count": 0, "requires_snapshot_count": 3},
        "execution_gate": {
            "disable_revert_execution_enabled": False,
            "requires_snapshot_artifacts": True,
            "requires_revert_plan": True,
            "requires_policy_simulation": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not disable startup entries."],
    }


def _sample_backup_delete_contract() -> dict[str, Any]:
    return {
        "schema": "cleanwin.backup-delete-contract.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "backup_scopes": [
            {
                "id": "backup-delete.file-tree",
                "target_surface": "reviewed file or directory tree",
                "allowed_categories": ["app-leftovers", "future-backup-delete-only"],
                "required_identity": ["cleanwin.filesystem-identity.v1", "canonical_path", "file_id_or_stat_tuple", "size_bytes", "modified_ns"],
                "required_backup_metadata": ["backup_path", "backup_identity", "source_identity", "created_at", "verification_digest"],
                "required_audit_refs": ["plan_source_fingerprint", "dry_run_confirmation_token", "operation_log_ref"],
                "execution_enabled": False,
                "auto_executable": False,
            }
        ],
        "summary": {"scope_count": 1, "execution_enabled_count": 0, "requires_backup_verification_count": 1},
        "execution_gate": {
            "backup_delete_execution_enabled": False,
            "requires_pre_delete_backup": True,
            "requires_backup_verification": True,
            "requires_identity_match_before_delete": True,
            "requires_operation_log": True,
            "requires_restore_drill_evidence": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not copy backup data."],
    }


def _sample_permanent_delete_denial() -> dict[str, Any]:
    return {
        "schema": "cleanwin.permanent-delete-denial.v1",
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
        "required_future_gates": ["separate explicit permanent-delete command surface"],
        "current_enforcement": {
            "plan_validation_rejects_permanent": True,
            "execute_plan_passes_allow_permanent_false": True,
            "ai_host_policy_requires_recycle": True,
            "mcp_execute_schema_allows_recycle_only": True,
            "delete_ops_requires_allow_permanent_true": True,
        },
        "summary": {"execution_enabled_count": 0, "denied_mode_count": 1, "future_gate_count": 1},
        "non_goals": ["This report does not enable permanent deletion."],
    }


def _sample_promotion_gates() -> dict[str, Any]:
    return {
        "schema": "cleanwin.promotion-gates.v1",
        "destructive": False,
        "dry_run": True,
        "execution_enabled": False,
        "gate_count": 5,
        "gates": [
            {
                "id": "registry-privacy-to-registry-change",
                "source_reports": ["cleanwin.debloat-privacy-report.v1"],
                "target_action": "registry-change",
                "default_state": "report-only",
                "required_evidence": ["exact_registry_key", "value_name", "observed_value", "expected_value"],
                "required_snapshots": ["system-restore-point", "registry-export"],
                "rollback_metadata": ["registry_key", "registry_export_ref", "previous_value", "restore_command"],
                "required_tests": ["fixture-registry-value-present", "rollback-metadata-validation"],
                "human_confirmations": ["explicit-registry-change-review", "matching-dry-run-token"],
                "ai_auto_call_allowed": False,
                "rationale": "Registry privacy changes must remain report-only until exact rollback evidence exists.",
            },
            {
                "id": "startup-entry-to-disable-plan",
                "source_reports": ["cleanwin.startup-service-inventory.v1"],
                "target_action": "startup-disable",
                "default_state": "report-only",
                "required_evidence": ["startup_location", "entry_name", "command", "target_path", "target_status", "target_exists", "snapshot_requirements"],
                "required_snapshots": ["registry-export", "startup-folder-snapshot"],
                "rollback_metadata": ["startup_location", "entry_name", "previous_command", "restore_action"],
                "required_tests": ["fixture-missing-target", "fixture-environment-expansion-required", "rollback-metadata-validation"],
                "human_confirmations": ["explicit-startup-disable-review", "matching-dry-run-token"],
                "ai_auto_call_allowed": False,
                "rationale": "Startup changes alter user login behavior and need reversible state before CleanWin can disable anything.",
            },
            {
                "id": "service-task-to-disable-plan",
                "source_reports": ["cleanwin.startup-service-inventory.v1"],
                "target_action": "service-or-scheduled-task-change",
                "default_state": "report-only",
                "required_evidence": [
                    "service_or_task_name",
                    "target_status",
                    "dependency_or_trigger_review",
                    "recovery_or_xml_snapshot_requirement",
                ],
                "required_snapshots": [
                    "system-restore-point",
                    "service-state",
                    "service-registry-export",
                    "scheduled-task-state",
                    "scheduled-task-xml-export",
                ],
                "rollback_metadata": ["object_name", "previous_state", "previous_start_type_or_task_xml", "restore_command", "snapshot_artifact_ref"],
                "required_tests": ["fixture-service-target-status", "fixture-scheduled-task-xml-required", "rollback-metadata-validation"],
                "human_confirmations": ["explicit-service-task-review", "matching-dry-run-token"],
                "ai_auto_call_allowed": False,
                "rationale": "Service and task changes can break update, security, or vendor maintenance flows and must be reversible.",
            },
            {
                "id": "windows-inventory-to-component-store-cleanup",
                "source_reports": ["cleanwin.windows-inventory.v1", "cleanwin.official-command-plan.v1"],
                "target_action": "component-store-cleanup",
                "default_state": "report-only",
                "required_evidence": ["component_store_analysis", "official_command_id", "pending_reboot_state"],
                "required_snapshots": ["system-restore-point", "component-store-analysis"],
                "rollback_metadata": ["analysis_ref", "command_id", "stdout_ref", "stderr_ref", "exit_code"],
                "required_tests": ["fixture-dism-analysis", "command-id-allowlist", "execution-output-captured"],
                "human_confirmations": ["explicit-component-store-review", "matching-dry-run-token"],
                "ai_auto_call_allowed": False,
                "rationale": "Component store cleanup must use DISM/official command surfaces and must never become direct WinSxS file deletion.",
            },
            {
                "id": "browser-profile-to-cache-plan",
                "source_reports": ["cleanwin.browser-profile-inventory.v1"],
                "target_action": "browser-cache-delete",
                "default_state": "low-risk-cache-only",
                "required_evidence": ["browser", "profile_name", "profile_path", "cache_layer", "locked_profile_state", "sensitive_exclusions"],
                "required_snapshots": [],
                "rollback_metadata": ["profile_path", "cache_layer", "recycle_destination"],
                "required_tests": ["fixture-locked-profile", "fixture-sensitive-data-excluded", "cache-layer-classification"],
                "human_confirmations": ["matching-dry-run-token"],
                "ai_auto_call_allowed": True,
                "rationale": "Only regenerated browser cache layers may be promoted.",
            },
        ],
        "summary": {"report_only_gate_count": 4, "ai_auto_call_allowed_count": 1, "requires_snapshot_count": 4},
        "global_requirements": ["No raw shell command strings in executable plans."],
        "non_goals": ["This report does not enable registry, startup, service, scheduled task, debloat, or official-command execution."],
    }


def _sample_browser_profile_inventory() -> dict[str, Any]:
    return {
        "schema": "cleanwin.browser-profile-inventory.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "sources": [{"id": "chrome", "available": True, "reason": "profile-root-scan", "evidence": {"root": r"C:\\Users\\tester\\AppData\\Local\\Google\\Chrome\\User Data"}}],
        "profiles": [
            {
                "browser": "chrome",
                "owner": "Google Chrome",
                "engine": "chromium",
                "profile_name": "Default",
                "profile_path": r"C:\\Users\\tester\\AppData\\Local\\Google\\Chrome\\User Data\\Default",
                "profile_exists": True,
                "locked_profile": {
                    "schema": "cleanwin.locked-state.v1",
                    "locked": True,
                    "state": "locked-or-running",
                    "evidence": [{"path": r"C:\\...\\SingletonLock", "exists": True, "indicator_type": "process-lock-file"}],
                    "blocked_reasons": ["profile-lock-file-present"],
                    "method": "filesystem-lock-indicator-scan",
                    "process_scan_performed": False,
                    "safe_to_execute": False,
                },
                "cache_layers": [
                    {
                        "name": "Cache",
                        "type": "http-cache",
                        "path": r"C:\\Users\\tester\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache",
                        "exists": True,
                        "size_bytes": 1024,
                        "promotable": True,
                        "locked_state": {
                            "schema": "cleanwin.locked-state.v1",
                            "locked": True,
                            "state": "locked-or-running",
                            "evidence": [{"path": r"C:\\...\\SingletonLock", "exists": True, "indicator_type": "process-lock-file"}],
                            "blocked_reasons": ["profile-lock-file-present"],
                            "method": "profile-and-cache-layer-lock-indicator-scan",
                            "process_scan_performed": False,
                            "safe_to_execute": False,
                        },
                        "blocked_reasons": ["profile-lock-file-present"],
                        "safe_to_execute": False,
                    }
                ],
                "sensitive_exclusions": ["Cookies", "Login Data", "Sessions", "Extensions", "History"],
                "safe_to_execute": False,
            }
        ],
        "summary": {"profile_count": 1, "locked_profile_count": 1, "locked_cache_layer_count": 1, "cache_layer_count": 1, "existing_cache_layer_count": 1, "promotable_cache_layer_count": 1, "bytes_reported": 1024},
        "execution_gate": {"system_execution_enabled": False, "cache_execution_enabled": False, "requires_locked_profile_check": True, "requires_sensitive_exclusions": True, "ai_auto_call_allowed": False},
        "non_goals": ["This report does not delete browser cache files."],
    }


def _sample_startup_service_inventory() -> dict[str, Any]:
    return {
        "schema": "cleanwin.startup-service-inventory.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "sources": [{"id": "registry-startup", "available": True, "reason": "registry-key-read", "evidence": {"key": r"HKCU\\...\\Run"}}],
        "startup_entries": [
            {
                "source": "registry-run",
                "location": r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                "name": "Example",
                "command": r"C:\\Program Files\\Example\\example.exe",
                "target_exists": True,
                "publisher": "",
                "signature_status": "not-checked",
                "risk": "medium",
                "safe_to_execute": False,
            }
        ],
        "registry_extension_entries": [
            {
                "source": "registry-extension",
                "entry_type": "winlogon",
                "location": r"HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon",
                "name": "Shell",
                "raw_value": "explorer.exe",
                "publisher": "",
                "signature_status": "not-checked",
                "risk": "high",
                "safe_to_execute": False,
            }
        ],
        "services": [
            {
                "name": "ExampleUpdater",
                "display_name": "Example Updater",
                "status": "Running",
                "start_type": "Automatic",
                "start_type_classification": "auto-start",
                "service_type": "service",
                "is_driver": False,
                "binary_path": r"C:\\Program Files\\Example\\example-updater.exe",
                "target_path": r"C:\\Program Files\\Example\\example-updater.exe",
                "target_exists": True,
                "target_status": "exists",
                "publisher": "Example Corp",
                "signature_status": "not-checked",
                "dependencies": ["RpcSs"],
                "trigger_start": True,
                "recovery_actions": ["restart-service"],
                "snapshot_requirements": [
                    "sc.exe qc",
                    "Get-CimInstance Win32_Service",
                    r"registry export HKLM\\SYSTEM\\CurrentControlSet\\Services",
                ],
                "risk": "high",
                "safe_to_execute": False,
            }
        ],
        "scheduled_tasks": [
            {
                "name": r"\\Example\\Updater",
                "task_path": r"\\Example\\Updater",
                "task_folder": r"\\Example",
                "state": "Ready",
                "task_to_run": r"C:\\Program Files\\Example\\example-updater.exe",
                "target_path": r"C:\\Program Files\\Example\\example-updater.exe",
                "target_exists": True,
                "target_status": "exists",
                "author": "Example Corp",
                "publisher": "Example Corp",
                "run_as_user": "ExampleUser",
                "run_level": "Highest",
                "schedule_type": "At logon time",
                "last_result": "0",
                "xml_snapshot_required": True,
                "snapshot_requirements": ["schtasks /Query /XML", "schtasks /Query /FO CSV /V"],
                "risk": "medium",
                "safe_to_execute": False,
            }
        ],
        "summary": {
            "startup_entry_count": 1,
            "registry_extension_entry_count": 1,
            "high_risk_extension_count": 1,
            "service_count": 1,
            "driver_service_count": 0,
            "auto_start_service_count": 1,
            "scheduled_task_count": 1,
            "elevated_task_count": 1,
            "missing_target_count": 0,
            "missing_service_target_count": 0,
            "auto_executable_count": 0,
        },
        "execution_gate": {
            "system_execution_enabled": False,
            "requires_service_snapshot": True,
            "requires_scheduled_task_snapshot": True,
            "requires_registry_export": True,
            "requires_publisher_or_signature_review": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not disable startup entries."],
    }


def _sample_windows_smoke_matrix() -> dict[str, Any]:
    return {
        "schema": "cleanwin.windows-smoke-matrix.v1",
        "destructive": False,
        "dry_run": True,
        "platform": {"os_name": "nt", "platform": "Windows-11", "is_windows": True},
        "scenario_count": 4,
        "scenarios": [
            {
                "id": "debloat-privacy-readonly-baseline",
                "title": "Debloat/privacy baseline remains read-only",
                "windows_versions": ["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
                "user_contexts": ["standard-user", "administrator", "managed-device"],
                "commands": [["python", "cleanwin.py", "--json", "debloat-privacy-report"]],
                "required_evidence": ["registry_policy_count", "registry_privacy_evidence_schema", "registry_export_required", "safe_to_execute_false"],
                "acceptance": ["Privacy and debloat findings never mutate registry values or AppX packages."],
                "risk": "high",
                "destructive": False,
            },
            {
                "id": "startup-service-task-readonly-inventory",
                "title": "Startup, service, and scheduled task inventory remains read-only",
                "windows_versions": ["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
                "user_contexts": ["standard-user", "administrator"],
                "commands": [["python", "cleanwin.py", "--json", "startup-service-inventory"]],
                "required_evidence": ["service_target_status", "task_xml_snapshot_required", "service_registry_export_required", "scheduled_task_xml_export_required"],
                "acceptance": ["Inventory reports service/task target status without disabling anything."],
                "risk": "high",
                "destructive": False,
            },
            {
                "id": "system-health-readonly-diagnostics",
                "title": "System health diagnostics remain scan-only",
                "windows_versions": ["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
                "user_contexts": ["administrator"],
                "commands": [["python", "cleanwin.py", "--json", "system-health-report"]],
                "required_evidence": ["dism_scanhealth_only", "repair_flags_absent", "safe_to_execute_false"],
                "acceptance": ["System-health recommendations use diagnostic or Settings paths only."],
                "risk": "high",
                "destructive": False,
            },
            {
                "id": "browser-profile-lock-and-sensitive-exclusion",
                "title": "Browser profile locks and privacy exclusions",
                "windows_versions": ["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
                "user_contexts": ["standard-user"],
                "commands": [["python", "cleanwin.py", "--json", "browser-profile-inventory"]],
                "required_evidence": ["profile_count", "locked_profile_state", "cache_layers", "sensitive_exclusions"],
                "acceptance": ["Cookies, passwords, sessions, extensions, history, bookmarks, and profile DBs are excluded."],
                "risk": "medium",
                "destructive": False,
            }
        ],
        "summary": {"windows_version_count": 3, "admin_scenario_count": 3, "high_risk_scenario_count": 3, "destructive_scenario_count": 0},
        "release_gate": {
            "required_before_execution_expansion": True,
            "requires_windows_10_evidence": True,
            "requires_windows_11_evidence": True,
            "requires_json_artifacts": True,
            "allows_synthetic_fixture_only": False,
        },
        "non_goals": ["This matrix does not execute Windows smoke scenarios by itself."],
    }


def _sample_workflow_router() -> dict[str, Any]:
    return {
        "schema": "cleanwin.workflow-router.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "purpose": "Route AI/MCP host intent to the safest CleanWin command path before selecting tools.",
        "routing_dimensions": ["intent", "risk", "required_artifacts"],
        "global_invariants": [
            "Default to read-only inventory and planning.",
            "No route may accept raw shell commands.",
            "Destructive cleanup is never auto-callable.",
        ],
        "routes": [
            {
                "id": "read-only-inventory",
                "intents": ["inspect", "inventory", "report"],
                "risk": "readonly",
                "destructive": False,
                "auto_call_allowed": True,
                "allowed_tools": ["cleanwin_inspect"],
                "required_previous_steps": [],
                "blocked_actions": ["delete", "registry mutation", "startup disable"],
            },
            {
                "id": "recycle-execution",
                "intents": ["execute", "cleanup", "delete-reviewed-candidates"],
                "risk": "destructive",
                "destructive": True,
                "auto_call_allowed": False,
                "allowed_tools": ["cleanwin_execute_plan"],
                "required_previous_steps": ["validate-and-review", "dry-run-execution"],
                "required_artifacts": ["validated plan", "human review", "policy simulation allow decision", "matching dry-run confirmation token", "operation log path"],
                "required_arguments": {
                    "delete_mode": "recycle",
                    "operation_log": "required JSONL path",
                    "require_plan_context": True,
                    "confirmation_phrase": "exact cleanwin confirmation phrase",
                    "confirmation_token": "must match dry-run token",
                },
                "blocked_actions": ["permanent delete", "raw shell command"],
            },
        ],
        "route_not_matched": {"default_action": "fall back to read-only capabilities and ask for explicit intent", "allowed_tools": ["cleanwin_capabilities"], "destructive": False},
        "non_goals": ["This router does not execute cleanup."],
    }


def _sample_environment_index() -> dict[str, Any]:
    return {
        "schema": "cleanwin.environment-index.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": "nt", "system": "Windows", "is_windows": True, "python_version": "3.12.0"},
        "cleanwin": {
            "version": "0.1.0",
            "test_mode": False,
            "entrypoints": [
                {"name": "cleanwin", "available": True, "path": r"C:\Tools\cleanwin.exe", "executes_by_report": False},
                {"name": "cleanwin-mcp", "available": True, "path": r"C:\Tools\cleanwin-mcp.exe", "executes_by_report": False},
            ],
        },
        "capabilities": [
            {"id": "read-only-inventory", "available": True, "reason": "pure-python-readonly-reports", "routes": ["discover-capabilities", "read-only-inventory"]},
            {"id": "windows-recycle-execution", "available": True, "reason": "windows-host", "routes": ["recycle-execution"]},
        ],
        "operation_log": {"default_path": r"C:\Users\tester\.cleanwin\operations.jsonl", "parent_exists": True, "write_checked": False, "required_for_execution": True},
        "fail_closed": ["non-windows recycle execution without CLEANWIN_TEST_MODE", "permanent delete route is not exposed"],
        "non_goals": ["This report does not install tools.", "This report does not execute cleanup."],
    }


def _sample_workflow_decision() -> dict[str, Any]:
    return {
        "schema": "cleanwin.workflow-decision.v1",
        "allowed": False,
        "route_id": "recycle-execution",
        "requested_tool": "cleanwin_execute_plan",
        "risk": "destructive",
        "destructive": True,
        "auto_call_allowed": False,
        "allowed_tools": ["cleanwin_execute_plan"],
        "provided_artifacts": [],
        "required_artifacts": ["validated plan", "human review", "policy simulation allow decision", "matching dry-run confirmation token", "operation log path"],
        "missing_artifacts": ["validated plan", "human review", "policy simulation allow decision", "matching dry-run confirmation token", "operation log path"],
        "blocking_reasons": [
            {"code": "MISSING_REQUIRED_ARTIFACTS", "detail": "validated plan, human review, policy simulation allow decision, matching dry-run confirmation token, operation log path"},
            {"code": "DESTRUCTIVE_ROUTE_REQUIRES_MANUAL_GATES", "detail": "Destructive routes are not auto-callable and require explicit execution gates."},
        ],
    }


def _sample_workflow_trace() -> dict[str, Any]:
    return {
        "schema": "cleanwin.workflow-trace.v1",
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "purpose": "Describe the auditable artifact chain expected for a CleanWin AI/MCP workflow.",
        "artifact_chain": [
            {"step": 1, "route": "discover-capabilities", "artifact_schema": "cleanwin.workflow-router.v1", "required": True},
            {"step": 2, "route": "read-only-inventory", "artifact_schema": "cleanwin.inspect.v1", "required": True},
            {"step": 3, "route": "plan-cleanup", "artifact_schema": "cleanwin.plan.v1", "required": True},
            {"step": 4, "route": "validate-and-review", "artifact_schema": "cleanwin.review.v1", "required": True},
            {"step": 5, "route": "dry-run-execution", "artifact_schema": "cleanwin.ai-confirmation-summary.v1", "required": True},
        ],
        "execution_gate": {"requires_all_prior_artifacts": True, "requires_matching_dry_run_token": True, "requires_operation_log": True, "ai_auto_call_allowed": False},
        "non_goals": ["This report does not read local artifact files.", "This report does not execute cleanup."],
    }


def schema_sample(schema_name: str) -> dict[str, Any] | None:
    if schema_name == "cleanwin.inspect.v1":
        return {
            "schema": "cleanwin.inspect.v1",
            "categories": ["dev-cache", "package-cache", "browser-cache", "app-leftovers", "docker-report"],
            "filters": {"rule_ids": ["dev-cache.npm.cache", "package-cache.winget.packages", "browser-cache.chrome.default.cache", "app-leftovers.vscode.cached-data", "report.docker.manual-cleanup"]},
            "candidates": [_sample_candidate(), _sample_package_candidate(), _sample_browser_candidate(), _sample_app_leftover_candidate()],
            "findings": [_sample_finding()],
            "summary": {"candidate_count": 4, "finding_count": 1, "bytes_reclaimable": 4096},
        }
    if schema_name == "cleanwin.plan.v1":
        return {
            "schema": "cleanwin.plan.v1",
            "categories": ["dev-cache"],
            "context": {
                "hostname": "TEST-WIN",
                "platform": "Windows-11",
                "os_name": "nt",
                "user": "tester",
                "home": r"C:\\Users\\tester",
            },
            "candidates": [_sample_candidate()],
            "created_at": "2026-06-20T00:00:00+00:00",
            "source_fingerprint": "0" * 64,
            "summary": {"candidate_count": 1, "safe_candidate_count": 1, "bytes_reclaimable": 1024},
        }
    if schema_name == "cleanwin.execute.v1":
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "dry_run": True,
            "validation": {"schema": "cleanwin.validate-plan.v1", "valid": True, "errors": [], "candidate_count": 1},
            "results": [
                {
                    "status": "dry-run",
                    "path": r"C:\Users\tester\AppData\Local\npm-cache\_cacache",
                    "mode": "recycle",
                }
            ],
            "summary": {"result_count": 1, "status_counts": {"dry-run": 1}},
            "confirmation": {
                "schema": "cleanwin.ai-confirmation-summary.v1",
                "required_phrase": "确认执行 cleanwin 清理",
                "confirmation_token": "1" * 64,
                "delete_mode": "recycle",
            },
        }
    if schema_name == "cleanwin.ai-tool-argument-validation.v1":
        return {
            "schema": "cleanwin.ai-tool-argument-validation.v1",
            "tool": "cleanwin_review_plan",
            "valid": False,
            "violation_count": 1,
            "violations": ["arguments.plan_file is required"],
        }
    if schema_name == "cleanwin.review.v1":
        return {
            "schema": "cleanwin.review.v1",
            "destructive": False,
            "plan_schema": "cleanwin.plan.v1",
            "plan_source_fingerprint": "0" * 64,
            "validation": {"schema": "cleanwin.validate-plan.v1", "valid": True, "errors": [], "candidate_count": 1},
            "summary": {"candidate_count": 1, "safe_candidate_count": 1, "bytes_reclaimable": 1024},
            "category_counts": [{"category": "dev-cache", "candidate_count": 1}],
            "risk_summary": [{"risk": "low", "candidate_count": 1}],
            "rule_ids": ["dev-cache.npm.cache"],
            "rule_summary": [
                {
                    "rule_id": "dev-cache.npm.cache",
                    "cache_owner": "npm",
                    "candidate_count": 1,
                    "bytes_reclaimable": 1024,
                    "official_cleanup_command": "npm cache clean --force",
                }
            ],
            "official_cleanup_commands": ["npm cache clean --force"],
            "cleanup_strategy": {
                "preferred": "official-cli-command",
                "fallback": "cleanwin-recycle-execution",
                "requires_review": True,
                "official_cleanup_commands": ["npm cache clean --force"],
            },
            "manual_only_categories": [],
            "sensitive_exclusions": [],
            "execution_handoff": {
                "safe_to_execute": True,
                "requires_human_confirmation": True,
                "requires_matching_dry_run_token": True,
                "requires_plan_context": True,
                "required_predecessor_tools": ["cleanwin_validate_plan", "cleanwin_policy_simulate", "cleanwin_dry_run_plan", "cleanwin_execute_plan"],
                "blocked_reasons": [],
            },
        }
    if schema_name == "cleanwin.filesystem-identity.v1":
        return _sample_identity()
    if schema_name == "cleanwin.doctor.v1":
        return {
            "schema": "cleanwin.doctor.v1",
            "destructive": False,
            "dry_run": True,
            "ready": True,
            "failed_check_ids": [],
            "check_count": 4,
            "passed_count": 4,
            "checks": [
                {
                    "id": "single_destructive_exit",
                    "passed": True,
                    "detail": "All destructive cleanup must route through cleanwincli.delete_ops.safe_delete.",
                    "evidence": {"deletion_exit": "cleanwincli.delete_ops.safe_delete"},
                },
                {
                    "id": "delete_primitives_owned_by_delete_ops",
                    "passed": True,
                    "detail": "Low-level delete/move primitives must not appear outside cleanwincli.delete_ops.",
                    "evidence": {"violations": []},
                },
                {
                    "id": "ai_contracts_valid",
                    "passed": True,
                    "detail": "AI tool schema and provider parity must validate.",
                    "evidence": {"violation_count": 0},
                },
                {
                    "id": "version_consistency",
                    "passed": True,
                    "detail": "Package metadata, installed distribution metadata, cleanwincli.__version__, and capabilities version must stay in sync.",
                    "evidence": {"pyproject_version": "0.1.0", "distribution_version": "0.1.0", "package_version": "0.1.0", "capabilities_version": "0.1.0"},
                },
            ],
            "recommended_commands": [
                ["make", "pytest"],
                ["make", "lint"],
                ["make", "type"],
                ["make", "quality"],
                ["make", "version-smoke"],
                ["make", "package-install-smoke"],
                ["make", "sdist-install-smoke"],
            ],
        }
    if schema_name == "cleanwin.recovery-readiness.v1":
        return _sample_recovery_readiness()
    if schema_name == "cleanwin.backup-delete-contract.v1":
        return _sample_backup_delete_contract()
    if schema_name == "cleanwin.file-report.v1":
        return _sample_file_report()
    if schema_name == "cleanwin.scan-governance.v1":
        return _sample_scan_governance()
    if schema_name == "cleanwin.external-rule-review.v1":
        return _sample_scan_governance()["external_rule_contract"]
    if schema_name == "cleanwin.script-boundary-contract.v1":
        return _sample_scan_governance()["script_boundary_contract"]
    if schema_name == "cleanwin.script-boundary-validation.v1":
        return _sample_scan_governance()["script_boundary_validation"]
    if schema_name == "cleanwin.external-rule-translation.v1":
        return external_rule_translation_sample()
    if schema_name == "cleanwin.external-rule-candidate.v1":
        return external_rule_translation_sample()["candidates"][0]
    if schema_name == "cleanwin.external-rule-import-sandbox.v1":
        return external_rule_translation_sample()["import_sandbox"]
    if schema_name == "cleanwin.installed-app-inventory.v1":
        return _sample_installed_app_inventory()
    if schema_name == "cleanwin.installed-app-leftover-evidence-link.v1":
        return _sample_installed_app_leftover_evidence_link()
    if schema_name == "cleanwin.windows-inventory.v1":
        return _sample_windows_inventory()
    if schema_name == "cleanwin.windows-inventory-collection-plan.v1":
        return _sample_windows_inventory_collection_plan()
    if schema_name == "cleanwin.appx-package-classification.v1":
        return _sample_appx_package_classification()
    if schema_name == "cleanwin.appx-package-snapshot.v1":
        return appx_snapshot_artifact_contract(provisioned=False)
    if schema_name == "cleanwin.provisioned-appx-package-snapshot.v1":
        return appx_snapshot_artifact_contract(provisioned=True)
    if schema_name == "cleanwin.browser-profile-inventory.v1":
        return _sample_browser_profile_inventory()
    if schema_name == "cleanwin.locked-state.v1":
        return _sample_browser_profile_inventory()["profiles"][0]["locked_profile"]
    if schema_name == "cleanwin.official-command-plan.v1":
        return _sample_official_command_plan()
    if schema_name == "cleanwin.official-action-contract.v1":
        return _sample_official_command_plan()["commands"][0]["action_contract"]
    if schema_name == "cleanwin.preset-catalog.v1":
        return _sample_preset_catalog()
    if schema_name == "cleanwin.preset-plan-template.v1":
        return _sample_preset_catalog()["presets"][0]["plan_template"]
    if schema_name == "cleanwin.rule-pack-catalog.v1":
        return rule_pack_catalog_report()
    if schema_name == "cleanwin.cleanup-rule-pack.v1":
        return rule_pack_catalog_report()["packs"][0]
    if schema_name == "cleanwin.rule-quality-score.v1":
        catalog = rule_pack_catalog_report()
        pack = catalog["packs"][0]
        return {
            "schema": "cleanwin.rule-quality-score.v1",
            "score": pack["quality"]["minimum_score"],
            "risk": "low",
            "recoverability": "high",
            "owner_evidence": True,
            "official_cleanup_evidence": True,
            "rationale_evidence": True,
            "active_install_marker_count": 1,
            "sensitive_exclusion_matches": [],
            "test_coverage": "catalog-fixture",
            "provenance": "builtin",
            "review_status": "manual-reviewed",
        }
    if schema_name == "cleanwin.rule-quality-dashboard.v1":
        return rule_quality_dashboard_report()
    if schema_name == "cleanwin.promotion-gates.v1":
        return _sample_promotion_gates()
    if schema_name == "cleanwin.promotion-gate-validation.v1":
        return validate_promotion_gate_action(
            source_report={"schema": "cleanwin.windows-inventory.v1"},
            proposed_action={
                "target_action": "appx-provisioned-package-change",
                "evidence": ["package_name"],
                "snapshots": [],
                "rollback_metadata": [],
                "tests": [],
                "human_confirmations": [],
            },
        )
    if schema_name == "cleanwin.debloat-privacy-report.v1":
        return _sample_debloat_privacy_report()
    if schema_name == "cleanwin.registry-privacy-evidence.v1":
        return _sample_debloat_privacy_report()["findings"][0]["change_evidence"]
    if schema_name == "cleanwin.disable-revert-contract.v1":
        return _sample_disable_revert_contract()
    if schema_name == "cleanwin.permanent-delete-denial.v1":
        return _sample_permanent_delete_denial()
    if schema_name == "cleanwin.registry-privacy-plan.v1":
        return registry_privacy_change_plan_report(_sample_debloat_privacy_report())
    if schema_name == "cleanwin.registry-privacy-change.v1":
        return registry_privacy_change_plan_report(_sample_debloat_privacy_report())["changes"][0]
    if schema_name == "cleanwin.registry-privacy-revert.v1":
        return registry_privacy_change_plan_report(_sample_debloat_privacy_report())["changes"][0]["rollback"]
    if schema_name == "cleanwin.registry-privacy-plan-validation.v1":
        return validate_registry_privacy_change_plan(registry_privacy_change_plan_report(_sample_debloat_privacy_report()))
    if schema_name == "cleanwin.appx-removal-plan.v1":
        return appx_removal_plan_report(_sample_windows_inventory())
    if schema_name == "cleanwin.appx-removal-change.v1":
        return appx_removal_plan_report(_sample_windows_inventory())["changes"][0]
    if schema_name == "cleanwin.appx-removal-revert.v1":
        return appx_removal_plan_report(_sample_windows_inventory())["changes"][0]["rollback"]
    if schema_name == "cleanwin.appx-removal-plan-validation.v1":
        return validate_appx_removal_plan(appx_removal_plan_report(_sample_windows_inventory()))
    if schema_name == "cleanwin.service-task-disable-plan.v1":
        return service_task_disable_plan_report(_sample_startup_service_inventory())
    if schema_name == "cleanwin.service-disable-change.v1":
        return service_task_disable_plan_report(_sample_startup_service_inventory())["changes"][0]
    if schema_name == "cleanwin.scheduled-task-disable-change.v1":
        return service_task_disable_plan_report(_sample_startup_service_inventory())["changes"][1]
    if schema_name == "cleanwin.service-task-revert.v1":
        return service_task_disable_plan_report(_sample_startup_service_inventory())["changes"][0]["rollback"]
    if schema_name == "cleanwin.service-task-disable-plan-validation.v1":
        return validate_service_task_disable_plan(service_task_disable_plan_report(_sample_startup_service_inventory()))
    if schema_name == "cleanwin.rollback-drill-report.v1":
        return rollback_drill_report()
    if schema_name == "cleanwin.rollback-drill-case.v1":
        return rollback_drill_report()["drills"][0]
    if schema_name == "cleanwin.rollback-drill-validation.v1":
        return validate_rollback_drills(rollback_drill_report())
    if schema_name == "cleanwin.registry-privacy-rollback-drill.v1":
        return rollback_drill_report()["drills"][0]["registry_rollback_fixture"]
    if schema_name == "cleanwin.appx-per-user-rollback-drill.v1":
        return rollback_drill_report()["drills"][3]["appx_per_user_rollback_fixture"]
    if schema_name == "cleanwin.startup-service-inventory.v1":
        return _sample_startup_service_inventory()
    if schema_name == "cleanwin.system-health-report.v1":
        return _sample_system_health_report()
    if schema_name == "cleanwin.system-health-evidence.v1":
        return _sample_system_health_evidence_report()
    if schema_name == "cleanwin.dism-component-store-analysis.v1":
        return _sample_system_health_evidence_report()["evidence"][0]
    if schema_name == "cleanwin.dism-health-evidence.v1":
        return _sample_system_health_evidence_report()["evidence"][1]
    if schema_name == "cleanwin.pending-reboot-registry-evidence.v1":
        return _sample_system_health_evidence_report()["evidence"][3]
    if schema_name == "cleanwin.windows-native-artifact-layout.v1":
        return artifact_layout_report()
    if schema_name == "cleanwin.windows-native-collector-manifest.v1":
        return sample_collector_manifest()
    if schema_name == "cleanwin.windows-native-artifact-validation.v1":
        return artifact_validation_sample()
    if schema_name == "cleanwin.windows-native-artifact-validation-issue.v1":
        return {
            "schema": "cleanwin.windows-native-artifact-validation-issue.v1",
            "severity": "error",
            "code": "HASH_MISMATCH",
            "path": "records[0].sha256",
            "record_id": "powershell-appx-packages",
            "message": "sha256 mismatch for appx-packages.json",
        }
    if schema_name == "cleanwin.windows-native-artifacts.v1":
        return windows_native_artifacts_report()
    if schema_name == "cleanwin.windows-native-artifact-contract.v1":
        return windows_native_artifacts_report()["contracts"][0]
    if schema_name == "cleanwin.windows-native-collector-wrapper.v1":
        return windows_native_collector_wrapper_contract()
    if schema_name == "cleanwin.windows-native-artifact-parse.v1":
        return windows_native_artifact_parse_sample()
    if schema_name == "cleanwin.windows-smoke-matrix.v1":
        return _sample_windows_smoke_matrix()
    if schema_name == "cleanwin.windows-snapshot-artifact-matrix.v1":
        return windows_snapshot_artifact_matrix()
    if schema_name == "cleanwin.windows-evidence-bundle.v1":
        return windows_evidence_bundle_report()
    if schema_name == "cleanwin.windows-evidence-bundle-record.v1":
        return windows_evidence_bundle_report()["records"][0]
    if schema_name == "cleanwin.workflow-router.v1":
        return _sample_workflow_router()
    if schema_name == "cleanwin.environment-index.v1":
        return _sample_environment_index()
    if schema_name == "cleanwin.workflow-decision.v1":
        return _sample_workflow_decision()
    if schema_name == "cleanwin.workflow-trace.v1":
        return _sample_workflow_trace()
    return None


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
