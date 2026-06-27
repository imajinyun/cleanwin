"""Read-only Windows native artifact contracts and fixture parsers."""

from __future__ import annotations

import csv
import io
import os
import platform
import re
from typing import Any

WINDOWS_NATIVE_ARTIFACTS_SCHEMA = "cleanwin.windows-native-artifacts.v1"
WINDOWS_NATIVE_ARTIFACT_CONTRACT_SCHEMA = "cleanwin.windows-native-artifact-contract.v1"
WINDOWS_NATIVE_COLLECTOR_WRAPPER_SCHEMA = "cleanwin.windows-native-collector-wrapper.v1"
WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA = "cleanwin.windows-native-artifact-parse.v1"


def _artifact_contract(
    artifact_id: str,
    *,
    title: str,
    command: list[str],
    output_schema: str,
    parser: str,
    requires_admin: bool,
    protected_surfaces: list[str],
    review_notes: list[str],
) -> dict[str, Any]:
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_CONTRACT_SCHEMA,
        "id": artifact_id,
        "title": title,
        "command": command,
        "command_display": " ".join(command),
        "windows_only": True,
        "requires_admin": requires_admin,
        "default_state": "not-executed",
        "executes_by_report": False,
        "safe_to_execute": False,
        "output_schema": output_schema,
        "parser": parser,
        "protected_surfaces": protected_surfaces,
        "review_notes": review_notes,
        "failure_modes": ["not-windows", "command-unavailable", "requires-admin", "policy-restricted"],
    }


def windows_native_collector_wrapper_contract() -> dict[str, Any]:
    script_path = "scripts/collect-cleanwin-artifacts.ps1"
    commands = [
        {
            "id": "collect-appx-packages",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "appx-packages", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["powershell-appx-packages"],
            "output_path": r"<artifact-root>\appx-packages.json",
            "requires_admin": True,
        },
        {
            "id": "collect-provisioned-appx",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "provisioned-appx", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["powershell-provisioned-appx"],
            "output_path": r"<artifact-root>\provisioned-appx.json",
            "requires_admin": True,
        },
        {
            "id": "collect-registry-export",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "registry-export", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["registry-export"],
            "output_path": r"<artifact-root>\registry-export.reg",
            "requires_admin": False,
        },
        {
            "id": "collect-scheduled-tasks",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "scheduled-tasks", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["scheduled-task-xml", "scheduled-task-csv"],
            "output_path": r"<artifact-root>\scheduled-tasks",
            "requires_admin": False,
        },
        {
            "id": "collect-services",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "services", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["service-query-config"],
            "output_path": r"<artifact-root>\services",
            "requires_admin": False,
        },
        {
            "id": "collect-package-managers",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "package-managers", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["winget-list", "winget-export", "scoop-list", "chocolatey-list"],
            "output_path": r"<artifact-root>\package-managers",
            "requires_admin": False,
        },
        {
            "id": "collect-dism-health",
            "argv": ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path, "-Mode", "dism-health", "-ArtifactRoot", "<artifact-root>"],
            "captures": ["dism-features", "dism-component-store"],
            "output_path": r"<artifact-root>\dism",
            "requires_admin": True,
        },
    ]
    return {
        "schema": WINDOWS_NATIVE_COLLECTOR_WRAPPER_SCHEMA,
        "id": "cleanwin-windows-native-collector-wrapper",
        "title": "Read-only Windows native collector wrapper",
        "wrapper_kind": "powershell-thin-wrapper",
        "script_name": "collect-cleanwin-artifacts.ps1",
        "script_path": script_path,
        "destructive": False,
        "executes_by_report": False,
        "safe_to_execute": False,
        "default_state": "implemented-read-only",
        "stdout_contract": "json-summary",
        "stderr_contract": "diagnostic-text",
        "manifest_schema": "cleanwin.windows-native-collector-manifest.v1",
        "artifact_root_argument": "--artifact-root",
        "supported_modes": ["all", "appx-packages", "provisioned-appx", "registry-export", "scheduled-tasks", "services", "package-managers", "dism-health"],
        "required_invocation_gates": [
            "explicit Windows host",
            "operator-provided artifact root",
            "read-only commands only",
            "no repair, remove, disable, import, uninstall, or cleanup verbs",
        ],
        "forbidden_commands": [
            "Remove-AppxPackage",
            "Remove-AppxProvisionedPackage",
            "Set-ItemProperty",
            "reg import",
            "schtasks /Change",
            "sc config",
            "dism /StartComponentCleanup",
            "winget uninstall",
            "choco uninstall",
        ],
        "commands": commands,
        "summary": {
            "command_count": len(commands),
            "requires_admin_count": sum(1 for command in commands if command["requires_admin"]),
            "mutation_command_count": 0,
        },
    }


def windows_native_artifacts_report() -> dict[str, Any]:
    contracts = [
        _artifact_contract(
            "powershell-appx-packages",
            title="Installed AppX packages",
            command=["powershell.exe", "-NoProfile", "Get-AppxPackage", "-AllUsers"],
            output_schema="cleanwin.appx-package-snapshot.v1",
            parser="powershell-object-table",
            requires_admin=True,
            protected_surfaces=["AppX package registration", "framework dependencies", "all-user package identity"],
            review_notes=["Capture package identity before any AppX plan.", "Do not remove framework or system packages."],
        ),
        _artifact_contract(
            "powershell-provisioned-appx",
            title="Provisioned AppX packages",
            command=["powershell.exe", "-NoProfile", "Get-AppxProvisionedPackage", "-Online"],
            output_schema="cleanwin.provisioned-appx-package-snapshot.v1",
            parser="powershell-object-table",
            requires_admin=True,
            protected_surfaces=["Windows image provisioning", "future user profile package registration"],
            review_notes=["Treat provisioned packages as future-user-impacting.", "Keep this read-only until AppX rollback metadata exists."],
        ),
        _artifact_contract(
            "registry-export",
            title="Registry key export",
            command=["reg.exe", "export", "<key>", "<artifact.reg>", "/y"],
            output_schema="cleanwin.registry-export-artifact.v1",
            parser="registry-export",
            requires_admin=False,
            protected_surfaces=["registry values", "policy ownership", "rollback metadata"],
            review_notes=["Registry exports are evidence and rollback inputs.", "Do not import or mutate from this report."],
        ),
        _artifact_contract(
            "scheduled-task-xml",
            title="Scheduled task XML export",
            command=["schtasks.exe", "/Query", "/TN", "<task-name>", "/XML"],
            output_schema="cleanwin.scheduled-task-xml-artifact.v1",
            parser="scheduled-task-xml-metadata",
            requires_admin=False,
            protected_surfaces=["task triggers", "task actions", "principal/run level"],
            review_notes=["Capture XML before disable/delete plans.", "Do not change task state from this report."],
        ),
        _artifact_contract(
            "scheduled-task-csv",
            title="Scheduled task verbose CSV",
            command=["schtasks.exe", "/Query", "/FO", "CSV", "/V"],
            output_schema="cleanwin.scheduled-task-csv-artifact.v1",
            parser="scheduled-task-csv",
            requires_admin=False,
            protected_surfaces=["task status", "last run result", "task action command"],
            review_notes=["Use CSV only as inventory evidence.", "Prefer XML export for rollback-capable plans."],
        ),
        _artifact_contract(
            "service-query-config",
            title="Service configuration",
            command=["sc.exe", "qc", "<service-name>"],
            output_schema="cleanwin.service-config-artifact.v1",
            parser="sc-qc",
            requires_admin=False,
            protected_surfaces=["service binary path", "start type", "dependencies"],
            review_notes=["Capture service config before disable plans.", "Driver, Microsoft, security, and update services stay protected."],
        ),
        _artifact_contract(
            "winget-list",
            title="WinGet installed package list",
            command=["winget.exe", "list"],
            output_schema="cleanwin.winget-list-artifact.v1",
            parser="winget-list",
            requires_admin=False,
            protected_surfaces=["installed package identity", "package manager source", "publisher identity"],
            review_notes=["Use package identity for uninstall/leftover correlation.", "Do not uninstall from this report."],
        ),
        _artifact_contract(
            "winget-export",
            title="WinGet package export",
            command=["winget.exe", "export", "-o", "<artifact.json>"],
            output_schema="cleanwin.winget-export-artifact.v1",
            parser="json-artifact-metadata",
            requires_admin=False,
            protected_surfaces=["package ids", "package sources"],
            review_notes=["Use export as installed package evidence.", "Do not install or uninstall from this report."],
        ),
        _artifact_contract(
            "scoop-list",
            title="Scoop package list",
            command=["scoop.cmd", "list"],
            output_schema="cleanwin.scoop-list-artifact.v1",
            parser="scoop-list",
            requires_admin=False,
            protected_surfaces=["Scoop app manifests", "shim links", "persist directories"],
            review_notes=["Use Scoop identity for app-leftover correlation.", "Do not delete persist data from this report."],
        ),
        _artifact_contract(
            "chocolatey-list",
            title="Chocolatey local package list",
            command=["choco.exe", "list", "--local-only"],
            output_schema="cleanwin.chocolatey-list-artifact.v1",
            parser="chocolatey-list",
            requires_admin=False,
            protected_surfaces=["Chocolatey package metadata", "install scripts", "lib directories"],
            review_notes=["Use Chocolatey identity for uninstall/leftover correlation.", "Do not uninstall from this report."],
        ),
        _artifact_contract(
            "dism-features",
            title="Windows optional features",
            command=["dism.exe", "/Online", "/Get-Features", "/Format:Table"],
            output_schema="cleanwin.windows-feature-snapshot.v1",
            parser="dism-feature-table",
            requires_admin=True,
            protected_surfaces=["Windows optional feature state", "component dependencies"],
            review_notes=["Use as inventory before Windows feature plans.", "Do not enable/disable features from this report."],
        ),
        _artifact_contract(
            "dism-component-store",
            title="Component store analysis",
            command=["dism.exe", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"],
            output_schema="cleanwin.dism-component-store-analysis.v1",
            parser="dism-analyze-component-store",
            requires_admin=True,
            protected_surfaces=["WinSxS", "servicing stack", "component rollback"],
            review_notes=["Analyze only; never delete WinSxS directly.", "Repair/cleanup commands require separate gates."],
        ),
    ]
    return {
        "schema": WINDOWS_NATIVE_ARTIFACTS_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "contracts": contracts,
        "summary": {
            "contract_count": len(contracts),
            "requires_admin_count": sum(1 for contract in contracts if contract["requires_admin"]),
            "execution_enabled_count": sum(1 for contract in contracts if contract["executes_by_report"]),
        },
        "collector_wrapper": windows_native_collector_wrapper_contract(),
        "execution_gate": {
            "artifact_collection_execution_enabled": False,
            "requires_explicit_windows_host": True,
            "requires_json_artifact_output": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not execute Windows native commands.",
            "This report does not mutate registry, services, scheduled tasks, packages, or Windows features.",
            "This report does not install, uninstall, repair, or clean packages.",
        ],
    }


def _split_table_line(line: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]


def parse_winget_list_output(output: str) -> dict[str, Any]:
    packages: list[dict[str, str]] = []
    for line in output.splitlines():
        if not line.strip() or line.lstrip().startswith("-") or line.lower().startswith("name "):
            continue
        parts = _split_table_line(line)
        if len(parts) >= 3:
            packages.append(
                {
                    "name": parts[0],
                    "package_id": parts[1],
                    "version": parts[2],
                    "source": parts[3] if len(parts) > 3 else "",
                }
            )
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "winget-list",
        "destructive": False,
        "executes_system_commands": False,
        "packages": packages,
        "summary": {"package_count": len(packages)},
    }


def parse_scoop_list_output(output: str) -> dict[str, Any]:
    packages: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = _split_table_line(line)
        if len(parts) >= 2 and parts[0].lower() not in {"name", "installed apps"}:
            packages.append({"name": parts[0], "version": parts[1], "source": parts[2] if len(parts) > 2 else "scoop"})
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "scoop-list",
        "destructive": False,
        "executes_system_commands": False,
        "packages": packages,
        "summary": {"package_count": len(packages)},
    }


def parse_chocolatey_list_output(output: str) -> dict[str, Any]:
    packages: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().endswith("packages installed."):
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            packages.append({"name": parts[0], "version": parts[1], "source": "chocolatey"})
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "chocolatey-list",
        "destructive": False,
        "executes_system_commands": False,
        "packages": packages,
        "summary": {"package_count": len(packages)},
    }


def parse_sc_qc_output(output: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    service_name = ""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("[SC] QueryServiceConfig SUCCESS"):
            continue
        if stripped.startswith("SERVICE_NAME:"):
            service_name = stripped.split(":", 1)[1].strip()
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            fields[key.strip().lower().replace(" ", "_")] = value.strip()
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "sc-qc",
        "destructive": False,
        "executes_system_commands": False,
        "service": {
            "name": service_name,
            "start_type": fields.get("start_type", ""),
            "binary_path_name": fields.get("binary_path_name", ""),
            "dependencies": fields.get("dependencies", ""),
            "service_start_name": fields.get("service_start_name", ""),
        },
        "summary": {"field_count": len(fields)},
    }


def parse_scheduled_tasks_csv_output(output: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(output))
    tasks = [
        {
            "task_name": row.get("TaskName", "") or row.get("Task Name", ""),
            "status": row.get("Status", ""),
            "last_run_time": row.get("Last Run Time", ""),
            "task_to_run": row.get("Task To Run", ""),
        }
        for row in reader
    ]
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "scheduled-task-csv",
        "destructive": False,
        "executes_system_commands": False,
        "tasks": tasks,
        "summary": {"task_count": len(tasks)},
    }


def parse_registry_export_metadata(output: str) -> dict[str, Any]:
    keys = [line.strip("[]") for line in output.splitlines() if line.startswith("[") and line.endswith("]")]
    value_count = sum(1 for line in output.splitlines() if line.strip().startswith('"') and "=" in line)
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "registry-export",
        "destructive": False,
        "executes_system_commands": False,
        "registry_keys": keys,
        "summary": {"key_count": len(keys), "value_count": value_count},
    }


def parse_dism_feature_table(output: str) -> dict[str, Any]:
    features: list[dict[str, str]] = []
    for line in output.splitlines():
        if "|" not in line or "Feature Name" in line or line.lstrip().startswith("-"):
            continue
        name, state = [part.strip() for part in line.split("|", 1)]
        if name:
            features.append({"name": name, "state": state})
    return {
        "schema": WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
        "parser": "dism-feature-table",
        "destructive": False,
        "executes_system_commands": False,
        "features": features,
        "summary": {"feature_count": len(features)},
    }


def windows_native_artifact_parse_sample() -> dict[str, Any]:
    return parse_winget_list_output(
        """
Name              Id                         Version    Source
---------------------------------------------------------------
PowerToys         Microsoft.PowerToys        0.82.0     winget
Visual Studio Code Microsoft.VisualStudioCode 1.90.0    winget
""".strip()
    )
