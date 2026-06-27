"""Read-only debloat and privacy telemetry reporting."""

from __future__ import annotations

import os
import platform
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DEBLOAT_PRIVACY_REPORT_SCHEMA = "cleanwin.debloat-privacy-report.v1"

_POLICY_SPECS: tuple[tuple[str, str, str, str, str, set[int], str, list[str]], ...] = (
    (
        "privacy.telemetry.allow-telemetry",
        "Windows telemetry policy",
        "HKLM",
        r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
        "AllowTelemetry",
        {0},
        "high",
        ["Review organization policy before changing telemetry settings.", "Export the policy key before any future registry mutation."],
    ),
    (
        "privacy.ad-id.disabled",
        "Advertising ID policy",
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
        "Enabled",
        {0},
        "medium",
        ["Use Windows Privacy settings where possible.", "Confirm app compatibility before changing advertising ID state."],
    ),
    (
        "privacy.consumer-features.disabled",
        "Consumer features policy",
        "HKLM",
        r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
        "DisableWindowsConsumerFeatures",
        {1},
        "medium",
        ["Review managed policy ownership.", "Export the policy key before any future registry mutation."],
    ),
    (
        "privacy.copilot.disabled",
        "Windows Copilot policy",
        "HKCU",
        r"Software\Policies\Microsoft\Windows\WindowsCopilot",
        "TurnOffWindowsCopilot",
        {1},
        "medium",
        ["Confirm Windows version support.", "Prefer Settings or policy management over direct registry edits."],
    ),
    (
        "privacy.recall.disabled",
        "Windows Recall AI data analysis policy",
        "HKCU",
        r"Software\Policies\Microsoft\Windows\WindowsAI",
        "DisableAIDataAnalysis",
        {1},
        "high",
        ["Confirm Windows edition and policy support.", "Export the WindowsAI policy key before any future mutation."],
    ),
    (
        "privacy.tailored-experiences.disabled",
        "Tailored experiences with diagnostic data",
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\Privacy",
        "TailoredExperiencesWithDiagnosticDataEnabled",
        {0},
        "medium",
        ["Prefer Windows Privacy settings where possible.", "Record current value before any policy change."],
    ),
    (
        "privacy.activity-history.publish-disabled",
        "Activity history publishing policy",
        "HKLM",
        r"SOFTWARE\Policies\Microsoft\Windows\System",
        "PublishUserActivities",
        {0},
        "medium",
        ["Review Timeline/activity history expectations.", "Export the Windows System policy key before mutation."],
    ),
    (
        "privacy.activity-history.upload-disabled",
        "Activity history upload policy",
        "HKLM",
        r"SOFTWARE\Policies\Microsoft\Windows\System",
        "UploadUserActivities",
        {0},
        "medium",
        ["Review cross-device activity history expectations.", "Export the Windows System policy key before mutation."],
    ),
    (
        "privacy.feedback-notifications.disabled",
        "Feedback notification policy",
        "HKCU",
        r"Software\Policies\Microsoft\Windows\DataCollection",
        "DoNotShowFeedbackNotifications",
        {1},
        "low",
        ["Confirm user notification preference.", "Use policy management instead of ad hoc registry edits."],
    ),
    (
        "privacy.search-cortana.disabled",
        "Cortana search policy",
        "HKLM",
        r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
        "AllowCortana",
        {0},
        "medium",
        ["Confirm Windows Search behavior expectations.", "Export Windows Search policy before mutation."],
    ),
    (
        "privacy.spotlight.disabled",
        "Windows Spotlight policy",
        "HKCU",
        r"Software\Policies\Microsoft\Windows\CloudContent",
        "DisableWindowsSpotlightFeatures",
        {1},
        "low",
        ["Review lock screen and Spotlight preference.", "Prefer policy or Settings UI for future changes."],
    ),
)

_APPX_REVIEW_TOKENS: tuple[tuple[str, str, str], ...] = (
    ("bing", "search-and-content", "Bundled Bing/content package; review user workflow before removal."),
    ("clipchamp", "consumer-media", "Consumer media package; review creative workflow before removal."),
    ("copilot", "ai-assistant", "AI assistant package; review policy and Windows feature dependencies."),
    ("feedbackhub", "diagnostics-feedback", "Feedback Hub package; review support and diagnostics needs."),
    ("gethelp", "support", "Support package; review helpdesk/support expectations."),
    ("getstarted", "onboarding", "Onboarding package; usually low value after initial setup but still needs review."),
    ("mixedreality", "mixed-reality", "Mixed Reality package; review device and headset requirements."),
    ("officehub", "office-promo", "Office hub package; review Microsoft 365 workflow."),
    ("people", "contacts", "People/contact package; review mail/contact integration."),
    ("skype", "communications", "Communications package; review user communication workflow."),
    ("solitaire", "games", "Game package; review user preference before removal."),
    ("teams", "communications", "Teams package; review work/school account dependencies."),
    ("windowscommunicationsapps", "mail-calendar", "Mail and Calendar package; review email/calendar usage."),
    ("xbox", "gaming", "Xbox package; review Game Bar, gaming, and controller dependencies."),
    ("yourphone", "phone-link", "Phone Link package; review mobile integration workflow."),
    ("zune", "media", "Legacy media package; review music/video workflow."),
)


def _source_status(source_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": source_id, "available": available, "reason": reason, "evidence": evidence or {}}


def _registry_value(root_name: str, subkey_path: str, value_name: str, *, raw_values: Mapping[str, Any] | None = None) -> tuple[Any | None, dict[str, Any]]:
    key = rf"{root_name}\{subkey_path}\{value_name}"
    if raw_values is not None:
        return raw_values.get(key), _source_status("registry-fixture", available=True, reason="test-fixture", evidence={"key": key})
    if os.name != "nt":
        return None, _source_status("registry-privacy-policy", available=False, reason="not-windows", evidence={"key": key, "os_name": os.name})
    try:
        import winreg as _winreg  # type: ignore[import-not-found]
    except ImportError:
        return None, _source_status("registry-privacy-policy", available=False, reason="winreg-unavailable", evidence={"key": key})
    winreg: Any = _winreg
    hives = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}
    hive = hives.get(root_name)
    if hive is None:
        return None, _source_status("registry-privacy-policy", available=False, reason="unsupported-hive", evidence={"key": key})
    try:
        with winreg.OpenKey(hive, subkey_path, 0, winreg.KEY_READ) as registry_key:
            value, _value_type = winreg.QueryValueEx(registry_key, value_name)
            return value, _source_status("registry-privacy-policy", available=True, reason="registry-value-read", evidence={"key": key})
    except OSError as exc:
        return None, _source_status("registry-privacy-policy", available=False, reason="registry-value-unavailable", evidence={"key": key, "error": str(exc)})


def _policy_finding(
    finding_id: str,
    *,
    title: str,
    root_name: str,
    subkey_path: str,
    value_name: str,
    expected_private_values: Iterable[Any],
    observed_value: Any | None,
    risk: str,
    review_steps: list[str],
) -> dict[str, Any]:
    private_values = {str(value) for value in expected_private_values}
    observed = "" if observed_value is None else str(observed_value)
    if observed_value is None:
        state = "not-observed"
    elif observed in private_values:
        state = "privacy-hardened"
    else:
        state = "review-recommended"
    return {
        "id": finding_id,
        "title": title,
        "kind": "registry-policy",
        "risk": risk,
        "state": state,
        "registry_value": rf"{root_name}\{subkey_path}\{value_name}",
        "observed_value": observed,
        "expected_private_values": sorted(private_values),
        "change_evidence": {
            "schema": "cleanwin.registry-privacy-evidence.v1",
            "hive": root_name,
            "subkey_path": subkey_path,
            "value_name": value_name,
            "observed_value": observed,
            "expected_private_values": sorted(private_values),
            "exact_registry_value": rf"{root_name}\{subkey_path}\{value_name}",
            "required_export_command": ["reg.exe", "export", rf"{root_name}\{subkey_path}", "<export-file.reg>", "/y"],
            "rollback_metadata_required": ["hive", "subkey_path", "value_name", "previous_value", "registry_export_ref"],
        },
        "safe_to_execute": False,
        "review_steps": review_steps,
    }


def _appx_inventory_source(raw_appx_packages: Iterable[Mapping[str, Any]] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if raw_appx_packages is None:
        return [], _source_status("appx-packages", available=False, reason="external-command-not-executed", evidence={"command": "Get-AppxPackage -AllUsers"})
    packages = [
        {
            "name": str(package.get("Name") or package.get("name") or ""),
            "package_family_name": str(package.get("PackageFamilyName") or package.get("package_family_name") or ""),
            "publisher": str(package.get("Publisher") or package.get("publisher") or ""),
            "version": str(package.get("Version") or package.get("version") or ""),
            "install_location": str(package.get("InstallLocation") or package.get("install_location") or ""),
        }
        for package in raw_appx_packages
    ]
    return [package for package in packages if package["name"]], _source_status("appx-packages", available=True, reason="test-fixture")


def _appx_review_metadata(package_name: str) -> dict[str, str] | None:
    normalized = package_name.lower()
    for token, category, rationale in _APPX_REVIEW_TOKENS:
        if token in normalized:
            return {"matched_token": token, "category": category, "rationale": rationale}
    return None


def _oem_locations(env: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = [
        ("programdata-oem", Path(env["PROGRAMDATA"]) / "OEM") if env.get("PROGRAMDATA") else None,
        ("programfiles-oem", Path(env["PROGRAMFILES"]) / "OEM") if env.get("PROGRAMFILES") else None,
        ("programfiles-supportassist", Path(env["PROGRAMFILES"]) / "Dell" / "SupportAssistAgent") if env.get("PROGRAMFILES") else None,
        ("programfiles-hp", Path(env["PROGRAMFILES"]) / "HP") if env.get("PROGRAMFILES") else None,
        ("programfiles-lenovo", Path(env["PROGRAMFILES"]) / "Lenovo") if env.get("PROGRAMFILES") else None,
    ]
    findings: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for item in candidates:
        if item is None:
            continue
        source_id, path = item
        exists = path.exists()
        sources.append(_source_status(source_id, available=exists, reason="path-present" if exists else "path-missing", evidence={"path": str(path)}))
        if exists:
            findings.append(
                {
                    "id": f"oem-location.{source_id}",
                    "title": f"OEM support location present: {path.name}",
                    "kind": "oem-app-location",
                    "risk": "medium",
                    "state": "review-recommended",
                    "path": str(path),
                    "safe_to_execute": False,
                    "review_steps": ["Review publisher and installed app identity.", "Prefer Settings > Apps or vendor uninstallers.", "Do not delete OEM support directories directly."],
                }
            )
    return findings, sources


def debloat_privacy_report(
    *,
    raw_registry_values: Mapping[str, Any] | None = None,
    raw_appx_packages: Iterable[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    current_env = dict(os.environ if env is None else env)
    sources: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for spec in _POLICY_SPECS:
        finding_id, title, root_name, subkey_path, value_name, private_values, risk, review_steps = spec
        value, source = _registry_value(root_name, subkey_path, value_name, raw_values=raw_registry_values)
        sources.append(source)
        findings.append(
            _policy_finding(
                finding_id,
                title=title,
                root_name=root_name,
                subkey_path=subkey_path,
                value_name=value_name,
                expected_private_values=private_values,
                observed_value=value,
                risk=risk,
                review_steps=review_steps,
            )
        )
    appx_packages, appx_source = _appx_inventory_source(raw_appx_packages)
    sources.append(appx_source)
    appx_review: list[tuple[dict[str, Any], dict[str, str]]] = []
    for package in appx_packages:
        metadata = _appx_review_metadata(package["name"])
        if metadata is not None:
            appx_review.append((package, metadata))
    for package, metadata in appx_review:
        findings.append(
            {
                "id": f"appx.review.{package['name']}",
                "title": f"AppX package requires debloat review: {package['name']}",
                "kind": "appx-package",
                "risk": "medium",
                "state": "review-recommended",
                "package": package,
                "review_category": metadata["category"],
                "matched_token": metadata["matched_token"],
                "review_rationale": metadata["rationale"],
                "safe_to_execute": False,
                "review_steps": ["Confirm the package is not required by the user.", "Create recovery evidence before any future AppX removal.", "Prefer documented Windows package management workflows."],
            }
        )
    oem_findings, oem_sources = _oem_locations(current_env)
    sources.extend(oem_sources)
    findings.extend(oem_findings)
    return {
        "schema": DEBLOAT_PRIVACY_REPORT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "sources": sources,
        "findings": findings,
        "summary": {
            "finding_count": len(findings),
            "registry_policy_count": len(_POLICY_SPECS),
            "review_recommended_count": sum(1 for finding in findings if finding["state"] == "review-recommended"),
            "privacy_hardened_count": sum(1 for finding in findings if finding["state"] == "privacy-hardened"),
            "appx_review_count": len(appx_review),
            "oem_location_count": len(oem_findings),
        },
        "execution_gate": {
            "system_execution_enabled": False,
            "requires_restore_point": True,
            "requires_registry_export": True,
            "requires_appx_inventory_snapshot": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not remove AppX packages.",
            "This report does not change privacy, telemetry, Copilot, Recall, or consumer feature policy keys.",
            "This report does not delete OEM application directories.",
            "This report does not execute PowerShell, DISM, winget, or vendor uninstallers.",
        ],
    }
