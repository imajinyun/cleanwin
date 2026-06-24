"""Read-only Windows system health and repair recommendation report."""

from __future__ import annotations

import os
import platform
from typing import Any

SYSTEM_HEALTH_REPORT_SCHEMA = "cleanwin.system-health-report.v1"


def _recommendation(
    recommendation_id: str,
    *,
    title: str,
    symptom: str,
    commands: list[list[str]],
    risk: str,
    prerequisites: list[str],
    evidence_required: list[str],
    review_steps: list[str],
) -> dict[str, Any]:
    return {
        "id": recommendation_id,
        "title": title,
        "symptom": symptom,
        "commands": commands,
        "risk": risk,
        "prerequisites": prerequisites,
        "evidence_required": evidence_required,
        "review_steps": review_steps,
        "executes_by_report": False,
        "auto_executable": False,
        "safe_to_execute": False,
    }


def system_health_report() -> dict[str, Any]:
    recommendations = [
        _recommendation(
            "health.component-store.dism-scanhealth",
            title="Check Windows component store health",
            symptom="Windows updates, optional features, or servicing operations fail.",
            commands=[["dism.exe", "/Online", "/Cleanup-Image", "/ScanHealth"]],
            risk="medium",
            prerequisites=["Run from elevated terminal", "No active Windows Update installation"],
            evidence_required=["DISM log excerpt", "Windows version", "pending reboot state"],
            review_steps=["Run scan commands before any repair command.", "Keep DISM logs for later diagnosis."],
        ),
        _recommendation(
            "health.system-files.sfc-scannow",
            title="Verify protected system files",
            symptom="Windows shell, system DLLs, or built-in components behave inconsistently.",
            commands=[["sfc.exe", "/scannow"]],
            risk="medium",
            prerequisites=["Run from elevated terminal", "Close active installers"],
            evidence_required=["SFC result text", "CBS.log reference"],
            review_steps=["Run after or alongside DISM health checks.", "Do not delete CBS or servicing logs before review."],
        ),
        _recommendation(
            "health.disk.chkdsk-scan",
            title="Check file system health",
            symptom="Disk errors, corrupted files, or unexpected cleanup failures are suspected.",
            commands=[["chkdsk.exe", "C:", "/scan"]],
            risk="medium",
            prerequisites=["Confirm target drive", "Avoid repair flags until backup state is known"],
            evidence_required=["Drive letter", "CHKDSK scan output", "backup state"],
            review_steps=["Use scan-only first.", "Avoid /f or /r repair flags without backup and downtime planning."],
        ),
        _recommendation(
            "health.windows-update.troubleshooter",
            title="Review Windows Update repair path",
            symptom="Update cache cleanup or component cleanup is being considered because updates fail.",
            commands=[["ms-settings:troubleshoot"], ["ms-settings:windowsupdate"]],
            risk="low",
            prerequisites=["Interactive user review"],
            evidence_required=["Windows Update error code", "update history screenshot or export"],
            review_steps=["Use Settings troubleshooters before direct cache deletion.", "Record update error codes."],
        ),
    ]
    return {
        "schema": SYSTEM_HEALTH_REPORT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "recommendations": recommendations,
        "summary": {
            "recommendation_count": len(recommendations),
            "auto_executable_count": sum(1 for item in recommendations if item["auto_executable"]),
            "elevated_recommendation_count": sum(1 for item in recommendations if "Run from elevated terminal" in item["prerequisites"]),
        },
        "execution_gate": {
            "system_repair_execution_enabled": False,
            "requires_human_review": True,
            "requires_admin_for_repair_tools": True,
            "requires_log_capture": True,
            "requires_backup_before_repair_flags": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not execute DISM, SFC, CHKDSK, troubleshooters, or Settings URI handlers.",
            "This report does not repair Windows components or disks.",
            "This report does not delete servicing, CBS, DISM, or Windows Update logs.",
        ],
    }
