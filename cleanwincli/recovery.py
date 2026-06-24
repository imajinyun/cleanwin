"""Recovery readiness reporting for future system-level CleanWin actions."""

from __future__ import annotations

import os
import platform
from typing import Any

RECOVERY_READINESS_SCHEMA = "cleanwin.recovery-readiness.v1"


def _snapshot_spec(
    snapshot_id: str,
    *,
    purpose: str,
    command: list[str],
    output_schema: str,
    required_before: list[str],
    rollback_use: str,
) -> dict[str, Any]:
    return {
        "id": snapshot_id,
        "purpose": purpose,
        "command": command,
        "output_schema": output_schema,
        "required_before": required_before,
        "rollback_use": rollback_use,
        "executed_by_report": False,
    }


def _capability(capability_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": capability_id,
        "available": available,
        "reason": reason,
        "evidence": evidence or {},
    }


def recovery_readiness_report() -> dict[str, Any]:
    is_windows = os.name == "nt"
    windows_reason = "windows-host" if is_windows else "not-windows"
    snapshot_specs = [
        _snapshot_spec(
            "system-restore-point",
            purpose="Create an OS rollback point before service, task, policy, AppX, or Windows cleanup changes.",
            command=[
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "Checkpoint-Computer",
                "-Description",
                "CleanWin pre-change restore point",
                "-RestorePointType",
                "MODIFY_SETTINGS",
            ],
            output_schema="cleanwin.snapshot.system-restore-point.v1",
            required_before=["windows-cleanup", "debloat", "startup-disable", "service-change", "scheduled-task-change", "registry-change"],
            rollback_use="Use Windows System Restore if a system-level change breaks Windows behavior.",
        ),
        _snapshot_spec(
            "registry-export",
            purpose="Export exact registry keys before any future registry mutation.",
            command=["reg", "export", "<registry-key>", "<snapshot-file.reg>", "/y"],
            output_schema="cleanwin.snapshot.registry-export.v1",
            required_before=["registry-change", "startup-disable", "policy-change"],
            rollback_use="Import the .reg file after review to restore previous key state.",
        ),
        _snapshot_spec(
            "service-state",
            purpose="Capture service startup type and running state before service changes.",
            command=["powershell", "-NoProfile", "Get-Service | Select-Object Name,Status,StartType | ConvertTo-Json"],
            output_schema="cleanwin.snapshot.service-state.v1",
            required_before=["service-change", "debloat"],
            rollback_use="Restore previous service startup type and state from captured JSON.",
        ),
        _snapshot_spec(
            "scheduled-task-state",
            purpose="Capture scheduled task state before disabling or deleting tasks.",
            command=["schtasks", "/Query", "/FO", "CSV", "/V"],
            output_schema="cleanwin.snapshot.scheduled-task-state.v1",
            required_before=["scheduled-task-change", "debloat"],
            rollback_use="Re-enable or recreate scheduled tasks from captured metadata.",
        ),
        _snapshot_spec(
            "appx-inventory",
            purpose="Capture AppX package identity before debloat or package removal workflows.",
            command=["powershell", "-NoProfile", "Get-AppxPackage -AllUsers | ConvertTo-Json"],
            output_schema="cleanwin.snapshot.appx-inventory.v1",
            required_before=["appx-remove", "debloat"],
            rollback_use="Use package identity to reinstall or provision removed AppX packages where supported.",
        ),
        _snapshot_spec(
            "installed-app-inventory",
            purpose="Capture installed application identity before uninstall-leftover correlation or batch uninstall workflows.",
            command=["powershell", "-NoProfile", "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | ConvertTo-Json"],
            output_schema="cleanwin.snapshot.installed-app-inventory.v1",
            required_before=["uninstall-leftover-cleanup", "batch-uninstall"],
            rollback_use="Compare pre/post application inventory and restore via vendor installers when needed.",
        ),
    ]
    capabilities = [
        _capability(
            "system_restore_point_supported",
            available=is_windows,
            reason=windows_reason,
            evidence={"os_name": os.name, "platform": platform.platform()},
        ),
        _capability(
            "registry_export_supported",
            available=is_windows,
            reason=windows_reason,
            evidence={"command": "reg export"},
        ),
        _capability(
            "service_snapshot_supported",
            available=is_windows,
            reason=windows_reason,
            evidence={"command": "Get-Service"},
        ),
        _capability(
            "scheduled_task_snapshot_supported",
            available=is_windows,
            reason=windows_reason,
            evidence={"command": "schtasks /Query"},
        ),
        _capability(
            "appx_inventory_supported",
            available=is_windows,
            reason=windows_reason,
            evidence={"command": "Get-AppxPackage"},
        ),
    ]
    return {
        "schema": RECOVERY_READINESS_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": is_windows},
        "ready_for_recovery_planning": True,
        "ready_for_system_execution": False,
        "capabilities": capabilities,
        "snapshot_specs": snapshot_specs,
        "execution_gate": {
            "requires_recovery_snapshot": True,
            "requires_restore_point_for_system_changes": True,
            "requires_registry_export_for_registry_changes": True,
            "requires_snapshot_reference_in_plan": True,
            "system_execution_enabled": False,
        },
        "non_goals": [
            "This report does not create restore points.",
            "This report does not export registry keys.",
            "This report does not change services, scheduled tasks, AppX packages, or policies.",
        ],
    }
