"""Windows smoke evidence matrix for CleanWin release readiness."""

from __future__ import annotations

import os
import platform
from typing import Any

WINDOWS_SMOKE_MATRIX_SCHEMA = "cleanwin.windows-smoke-matrix.v1"
WINDOWS_SNAPSHOT_ARTIFACT_MATRIX_SCHEMA = "cleanwin.windows-snapshot-artifact-matrix.v1"


def _scenario(
    scenario_id: str,
    *,
    title: str,
    windows_versions: list[str],
    user_contexts: list[str],
    commands: list[list[str]],
    required_evidence: list[str],
    acceptance: list[str],
    risk: str = "medium",
) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "title": title,
        "windows_versions": windows_versions,
        "user_contexts": user_contexts,
        "commands": commands,
        "required_evidence": required_evidence,
        "acceptance": acceptance,
        "risk": risk,
        "destructive": False,
    }


def _snapshot_artifact(
    artifact_id: str,
    *,
    title: str,
    schema: str,
    collector: str,
    windows_versions: list[str],
    user_contexts: list[str],
    host_contexts: list[str],
    package_manager_contexts: list[str],
    required_fields: list[str],
    golden_fixture: str,
    promotion_surfaces: list[str],
) -> dict[str, Any]:
    return {
        "id": artifact_id,
        "title": title,
        "schema": schema,
        "collector": collector,
        "windows_versions": windows_versions,
        "user_contexts": user_contexts,
        "host_contexts": host_contexts,
        "package_manager_contexts": package_manager_contexts,
        "required_fields": required_fields,
        "golden_fixture": golden_fixture,
        "promotion_surfaces": promotion_surfaces,
        "destructive": False,
        "executes_by_report": False,
    }


def windows_snapshot_artifact_matrix() -> dict[str, Any]:
    windows_versions = ["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"]
    standard_and_admin = ["standard-user", "administrator"]
    host_contexts = ["managed-device", "unmanaged-device"]
    artifacts = [
        _snapshot_artifact(
            "appx-package-snapshot",
            title="Installed AppX package snapshot",
            schema="cleanwin.appx-package-snapshot.v1",
            collector="powershell-appx-packages",
            windows_versions=windows_versions,
            user_contexts=standard_and_admin,
            host_contexts=host_contexts,
            package_manager_contexts=["none"],
            required_fields=["Name", "PackageFullName", "PackageFamilyName", "Publisher", "InstallLocation", "NonRemovable"],
            golden_fixture="tests/fixtures/windows/appx-package-snapshot.json",
            promotion_surfaces=["appx-removal-plan"],
        ),
        _snapshot_artifact(
            "provisioned-appx-package-snapshot",
            title="Provisioned AppX package snapshot",
            schema="cleanwin.provisioned-appx-package-snapshot.v1",
            collector="powershell-provisioned-appx",
            windows_versions=windows_versions,
            user_contexts=["administrator"],
            host_contexts=host_contexts,
            package_manager_contexts=["none"],
            required_fields=["PackageName", "DisplayName", "PackageFamilyName", "InstallLocation", "future_user_impact"],
            golden_fixture="tests/fixtures/windows/provisioned-appx-package-snapshot.json",
            promotion_surfaces=["appx-removal-plan"],
        ),
        _snapshot_artifact(
            "registry-export-artifact",
            title="Registry export artifact",
            schema="cleanwin.registry-export-artifact.v1",
            collector="registry-export",
            windows_versions=windows_versions,
            user_contexts=standard_and_admin,
            host_contexts=host_contexts,
            package_manager_contexts=["none"],
            required_fields=["registry_keys", "value_count", "export_command", "policy_owner", "managed_state"],
            golden_fixture="tests/fixtures/windows/registry-export.reg",
            promotion_surfaces=["registry-privacy-plan", "service-task-disable-plan"],
        ),
        _snapshot_artifact(
            "scheduled-task-xml-artifact",
            title="Scheduled task XML artifact",
            schema="cleanwin.scheduled-task-xml-artifact.v1",
            collector="scheduled-task-xml",
            windows_versions=windows_versions,
            user_contexts=standard_and_admin,
            host_contexts=host_contexts,
            package_manager_contexts=["none"],
            required_fields=["TaskName", "Actions", "Triggers", "Principals", "Settings"],
            golden_fixture="tests/fixtures/windows/scheduled-task.xml",
            promotion_surfaces=["service-task-disable-plan"],
        ),
        _snapshot_artifact(
            "service-config-artifact",
            title="Service configuration artifact",
            schema="cleanwin.service-config-artifact.v1",
            collector="service-query-config",
            windows_versions=windows_versions,
            user_contexts=standard_and_admin,
            host_contexts=host_contexts,
            package_manager_contexts=["none"],
            required_fields=["SERVICE_NAME", "START_TYPE", "BINARY_PATH_NAME", "DEPENDENCIES", "SERVICE_START_NAME"],
            golden_fixture="tests/fixtures/windows/service-config.txt",
            promotion_surfaces=["service-task-disable-plan"],
        ),
        _snapshot_artifact(
            "dism-component-store-analysis",
            title="DISM component store analysis",
            schema="cleanwin.dism-component-store-analysis.v1",
            collector="dism-component-store",
            windows_versions=windows_versions,
            user_contexts=["administrator"],
            host_contexts=host_contexts,
            package_manager_contexts=["none"],
            required_fields=["component_store_cleanup_recommended", "reclaimable_packages", "component_store_size", "reboot_pending"],
            golden_fixture="tests/fixtures/windows/dism-component-store.txt",
            promotion_surfaces=["official-command-plan", "system-health-report"],
        ),
        _snapshot_artifact(
            "package-manager-inventory-artifacts",
            title="Package manager inventory artifacts",
            schema="cleanwin.package-manager-inventory-artifacts.v1",
            collector="collect-package-managers",
            windows_versions=windows_versions,
            user_contexts=standard_and_admin,
            host_contexts=host_contexts,
            package_manager_contexts=["winget-present", "scoop-present", "chocolatey-present", "package-manager-absent"],
            required_fields=["package_id", "name", "version", "source", "install_scope"],
            golden_fixture="tests/fixtures/windows/package-manager-inventory.json",
            promotion_surfaces=["installed-app-inventory", "app-leftovers-review"],
        ),
    ]
    return {
        "schema": WINDOWS_SNAPSHOT_ARTIFACT_MATRIX_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "artifacts": artifacts,
        "summary": {
            "artifact_count": len(artifacts),
            "windows_version_count": len(windows_versions),
            "managed_context_required": True,
            "package_manager_context_count": len(
                {context for artifact in artifacts for context in artifact["package_manager_contexts"]}
            ),
            "execution_enabled_count": sum(1 for artifact in artifacts if artifact["executes_by_report"]),
        },
        "release_gate": {
            "required_before_execution_expansion": True,
            "requires_windows_10_evidence": True,
            "requires_windows_11_evidence": True,
            "requires_admin_and_standard_user_evidence": True,
            "requires_managed_and_unmanaged_evidence": True,
            "requires_package_manager_presence_matrix": True,
            "allows_synthetic_fixture_only": False,
        },
    }


def windows_smoke_matrix_report() -> dict[str, Any]:
    scenarios = [
        _scenario(
            "win10-win11-standard-user-safe-preview",
            title="Standard-user inspect/plan/validate dry-run preview",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["standard-user"],
            commands=[
                ["python", "cleanwin.py", "--json", "inspect", "--categories", "temp,dev-cache,browser-cache", "--older-than-days", "0"],
                ["python", "cleanwin.py", "--json", "plan", "--categories", "temp,dev-cache", "--older-than-days", "0", "--output", "%TEMP%\\cleanwin-plan.json"],
                ["python", "cleanwin.py", "--json", "validate-plan", "--plan-file", "%TEMP%\\cleanwin-plan.json"],
            ],
            required_evidence=["command_stdout_json", "exit_code", "plan_schema", "candidate_identity", "no_deleted_files"],
            acceptance=["All commands exit 0.", "Plan validates without context drift.", "No command deletes files."],
            risk="low",
        ),
        _scenario(
            "admin-official-command-and-recovery-readiness",
            title="Admin official-command and recovery readiness reports",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["administrator"],
            commands=[
                ["python", "cleanwin.py", "--json", "recovery-readiness"],
                ["python", "cleanwin.py", "--json", "official-command-plan"],
                ["python", "cleanwin.py", "--json", "promotion-gates"],
            ],
            required_evidence=["restore_point_capability", "official_command_ids", "promotion_gate_ids", "executes_system_commands_false"],
            acceptance=["Reports remain non-destructive.", "System execution gates remain disabled.", "Snapshot requirements are present for system surfaces."],
        ),
        _scenario(
            "debloat-privacy-readonly-baseline",
            title="Debloat/privacy baseline remains read-only",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["standard-user", "administrator", "managed-device"],
            commands=[
                ["python", "cleanwin.py", "--json", "debloat-privacy-report"],
                ["python", "cleanwin.py", "--json", "promotion-gates"],
            ],
            required_evidence=[
                "registry_policy_count",
                "registry_privacy_evidence_schema",
                "appx_review_count",
                "registry_export_required",
                "restore_point_required",
                "safe_to_execute_false",
            ],
            acceptance=[
                "Privacy and debloat findings never mutate registry values or AppX packages.",
                "Registry-policy findings include rollback metadata requirements.",
                "Managed or unknown policy state remains review-only.",
            ],
            risk="high",
        ),
        _scenario(
            "startup-service-task-readonly-inventory",
            title="Startup, service, and scheduled task inventory remains read-only",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["standard-user", "administrator"],
            commands=[
                ["python", "cleanwin.py", "--json", "startup-service-inventory"],
                ["python", "cleanwin.py", "--json", "disable-revert-contract"],
                ["python", "cleanwin.py", "--json", "recovery-readiness"],
            ],
            required_evidence=[
                "startup_entry_count",
                "service_target_status",
                "task_xml_snapshot_required",
                "service_registry_export_required",
                "scheduled_task_xml_export_required",
                "safe_to_execute_false",
            ],
            acceptance=[
                "Inventory reports service/task target status without disabling anything.",
                "Future disable/revert contracts require service registry and task XML snapshots.",
                "Execution gates remain disabled for startup, service, and task changes.",
            ],
            risk="high",
        ),
        _scenario(
            "system-health-readonly-diagnostics",
            title="System health diagnostics remain scan-only",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["administrator"],
            commands=[
                ["python", "cleanwin.py", "--json", "system-health-report"],
                ["python", "cleanwin.py", "--json", "official-command-plan"],
            ],
            required_evidence=[
                "dism_scanhealth_only",
                "sfc_scan_only",
                "chkdsk_scan_only",
                "windows_update_error_context",
                "repair_flags_absent",
                "safe_to_execute_false",
            ],
            acceptance=[
                "System-health recommendations use diagnostic or Settings paths only.",
                "Repair flags and destructive cleanup remain absent from report-generated commands.",
                "Logs and Windows version evidence are required before any repair workflow.",
            ],
            risk="high",
        ),
        _scenario(
            "onedrive-known-folders-and-user-data-protection",
            title="OneDrive/SharePoint known-folder protection",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["standard-user", "administrator"],
            commands=[
                ["python", "cleanwin.py", "--json", "inspect", "--categories", "large-files"],
                ["python", "cleanwin.py", "--json", "inspect", "--categories", "temp", "--older-than-days", "0"],
            ],
            required_evidence=["onedrive_path_detected_or_absent", "protected_user_data_paths", "no_documents_downloads_desktop_candidates"],
            acceptance=["OneDrive/Desktop/Documents/Downloads are never planned as automatic cleanup candidates.", "Large files remain report-only."],
            risk="high",
        ),
        _scenario(
            "browser-profile-lock-and-sensitive-exclusion",
            title="Browser profile locks and privacy exclusions",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["standard-user"],
            commands=[
                ["python", "cleanwin.py", "--json", "browser-profile-inventory"],
                ["python", "cleanwin.py", "--json", "inspect", "--categories", "browser-cache-report"],
            ],
            required_evidence=["profile_count", "locked_profile_state", "cache_layers", "sensitive_exclusions"],
            acceptance=["Cookies, passwords, sessions, extensions, history, bookmarks, and profile DBs are excluded.", "Locked profiles are reported, not mutated."],
        ),
        _scenario(
            "wsl-docker-visual-studio-report-only",
            title="WSL, Docker, and Visual Studio remain report-only",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["developer-user"],
            commands=[
                ["python", "cleanwin.py", "--json", "inspect", "--categories", "wsl-report,docker-report,visual-studio-report"],
            ],
            required_evidence=["finding_count", "safe_to_execute_false", "official_cleanup_commands", "risk_notes"],
            acceptance=["No candidates are produced for WSL, Docker, or Visual Studio reports.", "Manual review details include official commands and risk notes."],
            risk="high",
        ),
        _scenario(
            "filesystem-edge-cases",
            title="Filesystem edge cases: symlink, junction, long path, non-English path, locked file",
            windows_versions=["Windows 10 22H2", "Windows 11 23H2", "Windows 11 24H2"],
            user_contexts=["standard-user", "administrator"],
            commands=[
                ["python", "cleanwin.py", "--json", "inspect", "--categories", "temp", "--older-than-days", "0"],
                ["python", "cleanwin.py", "--json", "execute-plan", "--plan-file", "%TEMP%\\cleanwin-plan.json"],
            ],
            required_evidence=["symlink_rejected", "junction_rejected", "long_path_handled", "non_english_path_handled", "locked_file_reported"],
            acceptance=["Symlinks and junctions fail closed.", "Dry-run does not delete locked files.", "Non-English and long paths are represented in JSON without encoding loss."],
            risk="high",
        ),
    ]
    return {
        "schema": WINDOWS_SMOKE_MATRIX_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "snapshot_artifact_matrix": windows_snapshot_artifact_matrix(),
        "summary": {
            "windows_version_count": len({version for scenario in scenarios for version in scenario["windows_versions"]}),
            "admin_scenario_count": sum(1 for scenario in scenarios if "administrator" in scenario["user_contexts"]),
            "high_risk_scenario_count": sum(1 for scenario in scenarios if scenario["risk"] == "high"),
            "destructive_scenario_count": sum(1 for scenario in scenarios if scenario["destructive"]),
        },
        "release_gate": {
            "required_before_execution_expansion": True,
            "requires_windows_10_evidence": True,
            "requires_windows_11_evidence": True,
            "requires_json_artifacts": True,
            "allows_synthetic_fixture_only": False,
        },
        "non_goals": [
            "This matrix does not execute Windows smoke scenarios by itself.",
            "This matrix does not enable destructive cleanup, debloat, startup, service, or official-command execution.",
        ],
    }
