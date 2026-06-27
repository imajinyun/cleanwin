"""Read-only Windows inventory baseline reporting."""

from __future__ import annotations

import os
import platform
from collections.abc import Iterable, Mapping
from typing import Any

WINDOWS_INVENTORY_SCHEMA = "cleanwin.windows-inventory.v1"


def _source_status(source_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": source_id,
        "available": available,
        "reason": reason,
        "evidence": evidence or {},
    }


def _count(items: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for _item in items)


def _inventory_section(
    section_id: str,
    *,
    title: str,
    risk: str,
    source_id: str,
    fixture_items: Iterable[Mapping[str, Any]] | None,
    external_command: list[str],
    review_guidance: list[str],
    protected_surfaces: list[str],
) -> dict[str, Any]:
    if fixture_items is None:
        items: list[dict[str, Any]] = []
        source = _source_status(
            source_id,
            available=False,
            reason="external-command-not-executed",
            evidence={"command": " ".join(external_command)},
        )
    else:
        items = [dict(item) for item in fixture_items]
        source = _source_status(source_id, available=True, reason="test-fixture")
    return {
        "id": section_id,
        "title": title,
        "risk": risk,
        "source": source,
        "items": items,
        "item_count": len(items),
        "review_guidance": review_guidance,
        "protected_surfaces": protected_surfaces,
        "executes_by_report": False,
        "auto_executable": False,
    }


def windows_inventory_report(
    *,
    installed_apps: Iterable[Mapping[str, Any]] | None = None,
    appx_packages: Iterable[Mapping[str, Any]] | None = None,
    provisioned_appx_packages: Iterable[Mapping[str, Any]] | None = None,
    windows_features: Iterable[Mapping[str, Any]] | None = None,
    update_cache: Iterable[Mapping[str, Any]] | None = None,
    delivery_optimization: Iterable[Mapping[str, Any]] | None = None,
    defender_state: Iterable[Mapping[str, Any]] | None = None,
    restore_points: Iterable[Mapping[str, Any]] | None = None,
    recycle_bin: Iterable[Mapping[str, Any]] | None = None,
    installer_cache: Iterable[Mapping[str, Any]] | None = None,
    component_store: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    sections = [
        _inventory_section(
            "installed-apps",
            title="Installed applications",
            risk="medium",
            source_id="installed-apps",
            fixture_items=installed_apps,
            external_command=["registry uninstall keys", "winget list"],
            review_guidance=["Correlate installed identity before treating app-leftovers paths as orphaned."],
            protected_surfaces=["uninstall strings", "install locations", "publisher identity"],
        ),
        _inventory_section(
            "appx-packages",
            title="Installed AppX/MSIX packages",
            risk="high",
            source_id="appx-packages",
            fixture_items=appx_packages,
            external_command=["powershell.exe", "Get-AppxPackage", "-AllUsers"],
            review_guidance=["Classify Microsoft, OEM, framework, and user apps before any future debloat plan."],
            protected_surfaces=["package identity", "per-user registration", "framework packages"],
        ),
        _inventory_section(
            "provisioned-appx-packages",
            title="Provisioned AppX/MSIX packages",
            risk="high",
            source_id="provisioned-appx-packages",
            fixture_items=provisioned_appx_packages,
            external_command=["powershell.exe", "Get-AppxProvisionedPackage", "-Online"],
            review_guidance=["Treat provisioned packages as OS image state requiring explicit rollback evidence."],
            protected_surfaces=["Windows image provisioning", "OEM provisioning", "Store dependencies"],
        ),
        _inventory_section(
            "windows-features",
            title="Windows optional features",
            risk="high",
            source_id="windows-features",
            fixture_items=windows_features,
            external_command=["dism.exe", "/Online", "/Get-Features", "/Format:Table"],
            review_guidance=["Do not enable or disable features from inventory; route changes through recovery gates."],
            protected_surfaces=["Hyper-V", "WSL", ".NET Framework", "IIS", "servicing stack"],
        ),
        _inventory_section(
            "windows-update-cache",
            title="Windows Update cache",
            risk="medium",
            source_id="windows-update-cache",
            fixture_items=update_cache,
            external_command=["powershell.exe", "inspect SoftwareDistribution cache state"],
            review_guidance=["Prefer Storage Settings or documented Windows Update repair workflows."],
            protected_surfaces=[r"C:\Windows\SoftwareDistribution", "pending updates", "pending reboot state"],
        ),
        _inventory_section(
            "delivery-optimization",
            title="Delivery Optimization cache",
            risk="medium",
            source_id="delivery-optimization",
            fixture_items=delivery_optimization,
            external_command=["powershell.exe", "Get-DeliveryOptimizationStatus"],
            review_guidance=["Prefer Windows Settings for cleanup and avoid service or file mutation from inventory."],
            protected_surfaces=[r"C:\ProgramData\Microsoft\Windows\DeliveryOptimization", "service state"],
        ),
        _inventory_section(
            "defender-state",
            title="Microsoft Defender state",
            risk="high",
            source_id="defender-state",
            fixture_items=defender_state,
            external_command=["powershell.exe", "Get-MpComputerStatus"],
            review_guidance=["Do not delete Defender platform, signatures, quarantine, or history from inventory."],
            protected_surfaces=["Defender platform", "signature database", "quarantine", "protection state"],
        ),
        _inventory_section(
            "restore-points",
            title="System restore points",
            risk="high",
            source_id="restore-points",
            fixture_items=restore_points,
            external_command=["powershell.exe", "Get-ComputerRestorePoint"],
            review_guidance=["Use restore points as rollback evidence before high-risk Windows changes."],
            protected_surfaces=["system protection", "rollback points", "shadow copy state"],
        ),
        _inventory_section(
            "recycle-bin",
            title="Recycle Bin state",
            risk="low",
            source_id="recycle-bin",
            fixture_items=recycle_bin,
            external_command=["powershell.exe", "inspect recycle bin shell namespace"],
            review_guidance=["Use this only to understand reclaim potential; do not empty recycle bins automatically."],
            protected_surfaces=["per-user recycle bins", "recoverable deleted files"],
        ),
        _inventory_section(
            "installer-cache",
            title="Windows Installer cache",
            risk="high",
            source_id="installer-cache",
            fixture_items=installer_cache,
            external_command=["powershell.exe", "inspect Windows Installer cache metadata"],
            review_guidance=["Never delete Installer cache directly; broken MSI repair/uninstall is a common failure mode."],
            protected_surfaces=[r"C:\Windows\Installer", "MSI repair cache", "patch cache"],
        ),
        _inventory_section(
            "component-store",
            title="Windows component store",
            risk="high",
            source_id="component-store",
            fixture_items=component_store,
            external_command=["dism.exe", "/Online", "/Cleanup-Image", "/AnalyzeComponentStore"],
            review_guidance=["Use DISM or Storage Settings only; never delete WinSxS directly."],
            protected_surfaces=[r"C:\Windows\WinSxS", "servicing stack", "component rollback"],
        ),
    ]
    available_sections = [section for section in sections if section["source"]["available"]]
    high_risk_sections = [section for section in sections if section["risk"] == "high"]
    return {
        "schema": WINDOWS_INVENTORY_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "sections": sections,
        "summary": {
            "section_count": len(sections),
            "available_section_count": len(available_sections),
            "high_risk_section_count": len(high_risk_sections),
            "total_item_count": sum(int(section["item_count"]) for section in sections),
            "appx_package_count": _count(appx_packages or []),
            "provisioned_appx_package_count": _count(provisioned_appx_packages or []),
            "windows_feature_count": _count(windows_features or []),
            "executes_system_command_count": 0,
        },
        "promotion_gate": {
            "execution_enabled": False,
            "requires_recovery_readiness": True,
            "requires_official_command_plan": True,
            "requires_human_review": True,
            "requires_matching_dry_run_token": True,
        },
        "non_goals": [
            "This report does not uninstall applications or remove AppX packages.",
            "This report does not enable, disable, repair, or mutate Windows features, services, updates, Defender, or restore points.",
            "This report does not empty Recycle Bin, delete Installer cache, or delete WinSxS/component store files.",
            "This report does not execute PowerShell, DISM, winget, or Windows Settings commands.",
        ],
    }
