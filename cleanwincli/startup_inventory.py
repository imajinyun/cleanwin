"""Read-only startup, service, and scheduled task inventory."""

from __future__ import annotations

import os
import platform
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

STARTUP_SERVICE_INVENTORY_SCHEMA = "cleanwin.startup-service-inventory.v1"


def _source_status(source_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": source_id, "available": available, "reason": reason, "evidence": evidence or {}}


def _registry_run_entries(raw_registry_values: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    keys = [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
        ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
        ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
    ]
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    if raw_registry_values is not None:
        for root_name, key_path in keys:
            full_key = rf"{root_name}\{key_path}"
            values = raw_registry_values.get(full_key, {})
            sources.append(_source_status("registry-startup-fixture", available=True, reason="test-fixture", evidence={"key": full_key}))
            for name, command in values.items():
                entries.append(
                    {
                        "source": "registry-run",
                        "location": full_key,
                        "name": str(name),
                        "command": str(command),
                        "target_exists": _command_target_exists(str(command)),
                        "publisher": "",
                        "signature_status": "not-checked",
                        "risk": "medium",
                        "safe_to_execute": False,
                    }
                )
        return entries, sources
    if os.name != "nt":
        return [], [_source_status("registry-startup", available=False, reason="not-windows", evidence={"os_name": os.name})]
    try:
        import winreg as _winreg  # type: ignore[import-not-found]
    except ImportError:
        return [], [_source_status("registry-startup", available=False, reason="winreg-unavailable")]
    winreg: Any = _winreg
    hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
    for root_name, key_path in keys:
        full_key = rf"{root_name}\{key_path}"
        try:
            with winreg.OpenKey(hives[root_name], key_path, 0, winreg.KEY_READ) as registry_key:
                value_count = winreg.QueryInfoKey(registry_key)[1]
                for index in range(value_count):
                    name, value, _value_type = winreg.EnumValue(registry_key, index)
                    entries.append(
                        {
                            "source": "registry-run",
                            "location": full_key,
                            "name": str(name),
                            "command": str(value),
                            "target_exists": _command_target_exists(str(value)),
                            "publisher": "",
                            "signature_status": "not-checked",
                            "risk": "medium",
                            "safe_to_execute": False,
                        }
                    )
            sources.append(_source_status("registry-startup", available=True, reason="registry-key-read", evidence={"key": full_key}))
        except OSError as exc:
            sources.append(_source_status("registry-startup", available=False, reason="registry-key-unavailable", evidence={"key": full_key, "error": str(exc)}))
    return entries, sources


def _strip_command_target(command: str) -> str:
    value = command.strip()
    if not value:
        return ""
    if value.startswith('"'):
        end = value.find('"', 1)
        return value[1:end] if end > 1 else value.strip('"')
    return value.split()[0]


def _command_target_exists(command: str) -> bool:
    target = _strip_command_target(command)
    if not target or "%" in target:
        return False
    return Path(target).exists()


def _startup_folder_entries(env: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    roots = [
        ("user-startup-folder", Path(env["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup") if env.get("APPDATA") else None,
        ("common-startup-folder", Path(env["PROGRAMDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "StartUp") if env.get("PROGRAMDATA") else None,
    ]
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for item in roots:
        if item is None:
            continue
        source_id, root = item
        if not root.exists():
            sources.append(_source_status(source_id, available=False, reason="path-missing", evidence={"path": str(root)}))
            continue
        for child in sorted(root.iterdir(), key=lambda path: path.name.lower()):
            if child.is_file() and not child.is_symlink():
                entries.append(
                    {
                        "source": "startup-folder",
                        "location": str(root),
                        "name": child.name,
                        "path": str(child),
                        "target_exists": True,
                        "publisher": "",
                        "signature_status": "not-checked",
                        "risk": "medium",
                        "safe_to_execute": False,
                    }
                )
        sources.append(_source_status(source_id, available=True, reason="filesystem-directory", evidence={"path": str(root)}))
    return entries, sources


def _service_entries(raw_services: Iterable[Mapping[str, Any]] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if raw_services is None:
        return [], _source_status("services", available=False, reason="external-command-not-executed", evidence={"command": "Get-Service | Select Name,Status,StartType"})
    entries = [
        {
            "name": str(service.get("Name") or service.get("name") or ""),
            "display_name": str(service.get("DisplayName") or service.get("display_name") or ""),
            "status": str(service.get("Status") or service.get("status") or ""),
            "start_type": str(service.get("StartType") or service.get("start_type") or ""),
            "publisher": str(service.get("Publisher") or service.get("publisher") or ""),
            "signature_status": "not-checked",
            "risk": "high" if str(service.get("StartType") or service.get("start_type") or "").lower() == "automatic" else "medium",
            "safe_to_execute": False,
        }
        for service in raw_services
    ]
    return [entry for entry in entries if entry["name"]], _source_status("services", available=True, reason="test-fixture")


def _scheduled_task_entries(raw_tasks: Iterable[Mapping[str, Any]] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if raw_tasks is None:
        return [], _source_status("scheduled-tasks", available=False, reason="external-command-not-executed", evidence={"command": "schtasks /Query /FO CSV /V"})
    entries = [
        {
            "name": str(task.get("TaskName") or task.get("name") or ""),
            "state": str(task.get("Status") or task.get("state") or ""),
            "task_to_run": str(task.get("Task To Run") or task.get("task_to_run") or ""),
            "publisher": str(task.get("Author") or task.get("publisher") or ""),
            "target_exists": _command_target_exists(str(task.get("Task To Run") or task.get("task_to_run") or "")),
            "risk": "medium",
            "safe_to_execute": False,
        }
        for task in raw_tasks
    ]
    return [entry for entry in entries if entry["name"]], _source_status("scheduled-tasks", available=True, reason="test-fixture")


def startup_service_inventory_report(
    *,
    raw_registry_values: Mapping[str, Mapping[str, Any]] | None = None,
    raw_services: Iterable[Mapping[str, Any]] | None = None,
    raw_tasks: Iterable[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    current_env = dict(os.environ if env is None else env)
    registry_entries, registry_sources = _registry_run_entries(raw_registry_values)
    folder_entries, folder_sources = _startup_folder_entries(current_env)
    services, service_source = _service_entries(raw_services)
    tasks, task_source = _scheduled_task_entries(raw_tasks)
    sources = [*registry_sources, *folder_sources, service_source, task_source, _source_status("shell-extensions", available=False, reason="not-implemented-read-only-source")]
    return {
        "schema": STARTUP_SERVICE_INVENTORY_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "sources": sources,
        "startup_entries": [*registry_entries, *folder_entries],
        "services": services,
        "scheduled_tasks": tasks,
        "summary": {
            "startup_entry_count": len(registry_entries) + len(folder_entries),
            "service_count": len(services),
            "scheduled_task_count": len(tasks),
            "missing_target_count": sum(1 for entry in [*registry_entries, *folder_entries, *tasks] if not entry.get("target_exists")),
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
        "non_goals": [
            "This report does not disable startup entries.",
            "This report does not stop, disable, or delete services.",
            "This report does not disable or delete scheduled tasks.",
            "This report does not execute PowerShell, schtasks, sc.exe, or shell extension tools.",
        ],
    }
