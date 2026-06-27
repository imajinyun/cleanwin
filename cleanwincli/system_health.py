"""Read-only Windows system health and repair recommendation report."""

from __future__ import annotations

import os
import platform
import re
from typing import Any

SYSTEM_HEALTH_REPORT_SCHEMA = "cleanwin.system-health-report.v1"
SYSTEM_HEALTH_EVIDENCE_SCHEMA = "cleanwin.system-health-evidence.v1"


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
        _recommendation(
            "health.component-store.dism-checkhealth",
            title="Fast component store corruption check",
            symptom="A quick read-only health indicator is needed before considering DISM repair workflows.",
            commands=[["dism.exe", "/Online", "/Cleanup-Image", "/CheckHealth"]],
            risk="low",
            prerequisites=["Run from elevated terminal", "No active Windows Update installation"],
            evidence_required=["DISM CheckHealth result", "Windows version", "pending reboot state"],
            review_steps=["Use CheckHealth before ScanHealth when only a quick corruption indicator is needed.", "Do not run RestoreHealth from this report."],
        ),
        _recommendation(
            "health.windows-update.pending-reboot-review",
            title="Review pending reboot state before cleanup",
            symptom="Component store, update cache, or driver cleanup is being considered while Windows may have pending operations.",
            commands=[
                ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"],
                ["reg", "query", r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"],
            ],
            risk="medium",
            prerequisites=["Run from elevated terminal", "Capture registry query exit codes"],
            evidence_required=["CBS RebootPending query result", "Windows Update RebootRequired query result", "recent update history"],
            review_steps=["Postpone cleanup if pending reboot keys are present.", "Capture query output before any servicing cleanup."],
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


def _parse_size_value(text: str, label: str) -> str:
    match = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text, flags=re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_yes_no_value(text: str, label: str) -> bool | str:
    value = _parse_size_value(text, label).lower()
    if value in {"yes", "true"}:
        return True
    if value in {"no", "false"}:
        return False
    return "unknown"


def parse_dism_analyze_component_store(output: str) -> dict[str, Any]:
    """Parse DISM AnalyzeComponentStore text without executing DISM."""
    cleanup_recommended = _parse_yes_no_value(output, "Component Store Cleanup Recommended")
    return {
        "schema": "cleanwin.dism-component-store-analysis.v1",
        "parser": "dism-analyze-component-store",
        "cleanup_recommended": cleanup_recommended,
        "component_store_size": _parse_size_value(output, "Windows Explorer Reported Size of Component Store"),
        "actual_component_store_size": _parse_size_value(output, "Actual Size of Component Store"),
        "shared_with_windows_size": _parse_size_value(output, "Shared with Windows"),
        "backups_and_disabled_features_size": _parse_size_value(output, "Backups and Disabled Features"),
        "cache_and_temporary_data_size": _parse_size_value(output, "Cache and Temporary Data"),
        "last_cleanup": _parse_size_value(output, "Date of Last Cleanup"),
        "safe_to_execute": False,
    }


def parse_dism_health_output(output: str, *, parser: str) -> dict[str, Any]:
    """Parse DISM CheckHealth or ScanHealth output without executing DISM."""
    normalized = output.lower()
    if "no component store corruption detected" in normalized:
        health_state = "healthy"
    elif "component store is repairable" in normalized:
        health_state = "repairable"
    elif "component store cannot be repaired" in normalized or "not repairable" in normalized:
        health_state = "not-repairable"
    else:
        health_state = "unknown"
    return {
        "schema": "cleanwin.dism-health-evidence.v1",
        "parser": parser,
        "health_state": health_state,
        "operation_completed": "the operation completed successfully" in normalized,
        "requires_repair_review": health_state in {"repairable", "not-repairable"},
        "safe_to_execute": False,
    }


def parse_pending_reboot_query(query: dict[str, Any]) -> dict[str, Any]:
    """Parse a captured reg query result for pending reboot keys."""
    exit_code = int(query.get("exit_code", 1))
    stdout = str(query.get("stdout", ""))
    stderr = str(query.get("stderr", ""))
    key_present = exit_code == 0 and bool(stdout.strip())
    return {
        "schema": "cleanwin.pending-reboot-registry-evidence.v1",
        "id": str(query.get("id", "")),
        "command": list(query.get("command", [])),
        "exit_code": exit_code,
        "key_present": key_present,
        "state": "pending-reboot" if key_present else "not-present",
        "stdout_excerpt": stdout.strip()[:240],
        "stderr_excerpt": stderr.strip()[:240],
        "safe_to_execute": False,
    }


def system_health_evidence_report(
    *,
    analyze_component_store_output: str | None = None,
    scanhealth_output: str | None = None,
    checkhealth_output: str | None = None,
    pending_reboot_queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    if analyze_component_store_output is not None:
        evidence.append(parse_dism_analyze_component_store(analyze_component_store_output))
    if scanhealth_output is not None:
        evidence.append(parse_dism_health_output(scanhealth_output, parser="dism-scanhealth"))
    if checkhealth_output is not None:
        evidence.append(parse_dism_health_output(checkhealth_output, parser="dism-checkhealth"))
    for query in pending_reboot_queries or []:
        evidence.append(parse_pending_reboot_query(query))

    return {
        "schema": SYSTEM_HEALTH_EVIDENCE_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "evidence": evidence,
        "findings": _system_health_findings(evidence),
        "summary": {
            "evidence_count": len(evidence),
            "dism_evidence_count": sum(1 for item in evidence if str(item.get("parser", "")).startswith("dism")),
            "pending_reboot_key_count": sum(1 for item in evidence if item.get("state") == "pending-reboot"),
            "cleanup_recommended_count": sum(1 for item in evidence if item.get("cleanup_recommended") is True),
            "repair_review_count": sum(1 for item in evidence if item.get("requires_repair_review") is True),
            "auto_executable_count": 0,
        },
        "execution_gate": {
            "system_repair_execution_enabled": False,
            "system_cleanup_execution_enabled": False,
            "requires_human_review": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not execute DISM or registry queries.",
            "This report does not run DISM RestoreHealth, CHKDSK repair flags, or registry mutation.",
        ],
    }


def _system_health_findings(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in evidence:
        if item.get("cleanup_recommended") is True:
            findings.append(
                {
                    "id": "finding.component-store.cleanup-recommended",
                    "source_schema": item["schema"],
                    "state": "review-recommended",
                    "risk": "medium",
                    "safe_to_execute": False,
                }
            )
        if item.get("requires_repair_review") is True:
            findings.append(
                {
                    "id": "finding.component-store.repair-review",
                    "source_schema": item["schema"],
                    "state": item.get("health_state", "unknown"),
                    "risk": "high",
                    "safe_to_execute": False,
                }
            )
        if item.get("state") == "pending-reboot":
            findings.append(
                {
                    "id": f"finding.pending-reboot.{item.get('id', 'registry-key')}",
                    "source_schema": item["schema"],
                    "state": "pending-reboot",
                    "risk": "medium",
                    "safe_to_execute": False,
                }
            )
    return findings
