"""Read-only Windows inventory baseline reporting."""

from __future__ import annotations

import os
import platform
from collections.abc import Iterable, Mapping
from typing import Any

WINDOWS_INVENTORY_SCHEMA = "cleanwin.windows-inventory.v1"
COLLECTION_PLAN_SCHEMA = "cleanwin.windows-inventory-collection-plan.v1"
APPX_CLASSIFICATION_SCHEMA = "cleanwin.appx-package-classification.v1"
APPX_PACKAGE_SNAPSHOT_SCHEMA = "cleanwin.appx-package-snapshot.v1"
PROVISIONED_APPX_PACKAGE_SNAPSHOT_SCHEMA = "cleanwin.provisioned-appx-package-snapshot.v1"

_APPX_FRAMEWORK_TOKENS = (
    "vclibs",
    "net.native",
    "ui.xaml",
    "windowsappruntime",
    "framework",
)
_APPX_SYSTEM_TOKENS = (
    "shellexperiencehost",
    "startmenuexperiencehost",
    "sechealthui",
    "windowsstore",
    "storepurchaseapp",
    "desktopappinstaller",
    "windowscalculator",
    "windowsnotepad",
)
_APPX_CONSUMER_TOKENS = (
    "bing",
    "clipchamp",
    "copilot",
    "feedbackhub",
    "gethelp",
    "getstarted",
    "mixedreality",
    "officehub",
    "people",
    "skype",
    "solitaire",
    "teams",
    "windowscommunicationsapps",
    "xbox",
    "yourphone",
    "zune",
)
_APPX_OEM_TOKENS = (
    "acer",
    "asus",
    "dell",
    "hp",
    "lenovo",
    "msi",
)


def _source_status(source_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": source_id,
        "available": available,
        "reason": reason,
        "evidence": evidence or {},
    }


def _count(items: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for _item in items)


def _appx_text(item: Mapping[str, Any]) -> str:
    values = [
        item.get("Name"),
        item.get("name"),
        item.get("PackageFullName"),
        item.get("package_full_name"),
        item.get("PackageFamilyName"),
        item.get("package_family_name"),
        item.get("Publisher"),
        item.get("publisher"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _matched_tokens(text: str, tokens: tuple[str, ...]) -> list[str]:
    return [token for token in tokens if token in text]


def _classify_appx_package(item: Mapping[str, Any], *, provisioned: bool) -> dict[str, Any]:
    text = _appx_text(item)
    framework_matches = _matched_tokens(text, _APPX_FRAMEWORK_TOKENS)
    system_matches = _matched_tokens(text, _APPX_SYSTEM_TOKENS)
    consumer_matches = _matched_tokens(text, _APPX_CONSUMER_TOKENS)
    oem_matches = _matched_tokens(text, _APPX_OEM_TOKENS)
    raw_is_framework = str(item.get("IsFramework") or item.get("is_framework") or "").lower() == "true"
    if raw_is_framework or framework_matches:
        category = "framework"
        confidence = "high"
        protected = True
        review_action = "protect"
        rationale = "Framework packages can be dependencies for other AppX/MSIX packages and must not be removed from inventory."
        matched = framework_matches or ["is_framework"]
    elif system_matches:
        category = "system"
        confidence = "high"
        protected = True
        review_action = "protect"
        rationale = "System AppX packages are Windows-owned or Store/installer dependencies and require explicit OS evidence before any future change."
        matched = system_matches
    elif oem_matches:
        category = "oem"
        confidence = "medium"
        protected = False
        review_action = "manual-review"
        rationale = "OEM packages may support firmware, drivers, warranty, or device-specific tools and need vendor review."
        matched = oem_matches
    elif consumer_matches:
        category = "consumer-app"
        confidence = "medium"
        protected = False
        review_action = "manual-review"
        rationale = "Consumer bundled apps may be removable for some users but require workflow, dependency, and recovery review first."
        matched = consumer_matches
    else:
        category = "unknown"
        confidence = "low"
        protected = True
        review_action = "inventory-only"
        rationale = "Package role is not known to CleanWin; keep it protected until explicit classification evidence exists."
        matched = []
    return {
        "schema": APPX_CLASSIFICATION_SCHEMA,
        "category": category,
        "confidence": confidence,
        "matched_tokens": matched,
        "package_family_name": item.get("PackageFamilyName") or item.get("package_family_name") or "",
        "publisher": item.get("Publisher") or item.get("publisher") or "",
        "non_removable": str(item.get("NonRemovable") or item.get("non_removable") or "").lower() == "true",
        "dependency": raw_is_framework or bool(framework_matches),
        "protected_by_default": protected,
        "review_action": review_action,
        "rationale": rationale,
        "provisioned_state": provisioned,
        "future_user_profile_impact": provisioned,
        "promotion_gate_id": "windows-inventory-to-appx-change",
        "safe_to_execute": False,
    }


def _with_appx_classification(items: Iterable[Mapping[str, Any]], *, provisioned: bool) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        payload = dict(item)
        payload["cleanwin_classification"] = _classify_appx_package(payload, provisioned=provisioned)
        enriched.append(payload)
    return enriched


def appx_snapshot_artifact_contract(*, provisioned: bool) -> dict[str, Any]:
    """Return the read-only artifact contract for captured AppX evidence."""
    if provisioned:
        return {
            "schema": PROVISIONED_APPX_PACKAGE_SNAPSHOT_SCHEMA,
            "artifact_kind": "provisioned-appx-package-snapshot",
            "producer_command": ["powershell.exe", "Get-AppxProvisionedPackage", "-Online"],
            "identity_fields": ["PackageName", "DisplayName", "PackageFamilyName", "PublisherId"],
            "required_fields": ["PackageName", "DisplayName", "PackageFamilyName", "PublisherId", "Architecture", "Version"],
            "optional_fields": ["InstallLocation", "Regions", "ResourceId", "CustomDataPath", "LicensePath"],
            "classification_inputs": ["DisplayName", "PackageName", "PackageFamilyName", "PublisherId"],
            "rollback_reference_fields": ["PackageName", "DisplayName", "PackageFamilyName", "InstallLocation", "snapshot_artifact_ref"],
            "future_user_profile_impact": True,
            "scope": "windows-image-provisioning",
            "executes_by_report": False,
            "safe_to_execute": False,
            "golden_fixture_required": True,
        }
    return {
        "schema": APPX_PACKAGE_SNAPSHOT_SCHEMA,
        "artifact_kind": "appx-package-snapshot",
        "producer_command": ["powershell.exe", "Get-AppxPackage", "-AllUsers"],
        "identity_fields": ["Name", "PackageFullName", "PackageFamilyName", "Publisher"],
        "required_fields": ["Name", "PackageFullName", "PackageFamilyName", "Publisher", "Architecture", "Version", "InstallLocation"],
        "optional_fields": ["IsFramework", "NonRemovable", "Dependencies", "SignatureKind", "Status"],
        "classification_inputs": ["Name", "PackageFullName", "PackageFamilyName", "Publisher", "IsFramework", "NonRemovable"],
        "rollback_reference_fields": ["Name", "PackageFullName", "PackageFamilyName", "InstallLocation", "snapshot_artifact_ref"],
        "future_user_profile_impact": False,
        "scope": "all-users-installed-registration",
        "executes_by_report": False,
        "safe_to_execute": False,
        "golden_fixture_required": True,
    }


def _inventory_section(
    section_id: str,
    *,
    title: str,
    risk: str,
    source_id: str,
    fixture_items: Iterable[Mapping[str, Any]] | None,
    external_command: list[str],
    collection_method: str,
    requires_admin: bool,
    expected_artifact_schema: str,
    promotion_gate_id: str,
    review_guidance: list[str],
    protected_surfaces: list[str],
    enriched_items: list[dict[str, Any]] | None = None,
    artifact_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    collection_plan = {
        "schema": COLLECTION_PLAN_SCHEMA,
        "method": collection_method,
        "command": external_command,
        "command_display": " ".join(external_command),
        "windows_only": True,
        "requires_admin": requires_admin,
        "executes_by_report": False,
        "default_state": "not-executed",
        "expected_artifact_schema": expected_artifact_schema,
        "promotion_gate_id": promotion_gate_id,
        "failure_modes": [
            "not-windows",
            "requires-admin",
            "command-unavailable",
            "policy-restricted",
            "external-command-not-executed",
        ],
    }
    if artifact_contract is not None:
        collection_plan["artifact_contract"] = artifact_contract
    if fixture_items is None:
        items: list[dict[str, Any]] = []
        source = _source_status(
            source_id,
            available=False,
            reason="external-command-not-executed",
            evidence={
                "command": " ".join(external_command),
                "command_argv": external_command,
                "collection_method": collection_method,
                "requires_admin": requires_admin,
                "windows_only": True,
                "executes_by_report": False,
                "expected_artifact_schema": expected_artifact_schema,
            },
        )
    else:
        items = [dict(item) for item in fixture_items]
        if enriched_items is not None:
            items = enriched_items
        source = _source_status(
            source_id,
            available=True,
            reason="test-fixture",
            evidence={
                "fixture_item_count": len(items),
                "collection_method": collection_method,
                "executes_by_report": False,
                "expected_artifact_schema": expected_artifact_schema,
            },
        )
    return {
        "id": section_id,
        "title": title,
        "risk": risk,
        "source": source,
        "collection_plan": collection_plan,
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
    enriched_appx_packages = _with_appx_classification(appx_packages or [], provisioned=False) if appx_packages is not None else None
    enriched_provisioned_appx_packages = (
        _with_appx_classification(provisioned_appx_packages or [], provisioned=True) if provisioned_appx_packages is not None else None
    )
    sections = [
        _inventory_section(
            "installed-apps",
            title="Installed applications",
            risk="medium",
            source_id="installed-apps",
            fixture_items=installed_apps,
            external_command=["registry uninstall keys", "winget list"],
            collection_method="registry-uninstall-and-winget-inventory",
            requires_admin=False,
            expected_artifact_schema="cleanwin.installed-app-inventory.v1",
            promotion_gate_id="windows-inventory-to-installer-cache-cleanup",
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
            collection_method="powershell-appx-package-inventory",
            requires_admin=True,
            expected_artifact_schema=APPX_PACKAGE_SNAPSHOT_SCHEMA,
            promotion_gate_id="windows-inventory-to-appx-change",
            review_guidance=["Classify Microsoft, OEM, framework, and user apps before any future debloat plan."],
            protected_surfaces=["package identity", "per-user registration", "framework packages"],
            enriched_items=enriched_appx_packages,
            artifact_contract=appx_snapshot_artifact_contract(provisioned=False),
        ),
        _inventory_section(
            "provisioned-appx-packages",
            title="Provisioned AppX/MSIX packages",
            risk="high",
            source_id="provisioned-appx-packages",
            fixture_items=provisioned_appx_packages,
            external_command=["powershell.exe", "Get-AppxProvisionedPackage", "-Online"],
            collection_method="powershell-provisioned-appx-inventory",
            requires_admin=True,
            expected_artifact_schema=PROVISIONED_APPX_PACKAGE_SNAPSHOT_SCHEMA,
            promotion_gate_id="windows-inventory-to-appx-change",
            review_guidance=["Treat provisioned packages as OS image state requiring explicit rollback evidence."],
            protected_surfaces=["Windows image provisioning", "OEM provisioning", "Store dependencies"],
            enriched_items=enriched_provisioned_appx_packages,
            artifact_contract=appx_snapshot_artifact_contract(provisioned=True),
        ),
        _inventory_section(
            "windows-features",
            title="Windows optional features",
            risk="high",
            source_id="windows-features",
            fixture_items=windows_features,
            external_command=["dism.exe", "/Online", "/Get-Features", "/Format:Table"],
            collection_method="dism-feature-inventory",
            requires_admin=True,
            expected_artifact_schema="cleanwin.windows-feature-snapshot.v1",
            promotion_gate_id="windows-inventory-to-feature-change",
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
            collection_method="windows-update-cache-inventory",
            requires_admin=True,
            expected_artifact_schema="cleanwin.windows-update-cache-snapshot.v1",
            promotion_gate_id="official-command-to-executable-action",
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
            collection_method="delivery-optimization-status-inventory",
            requires_admin=False,
            expected_artifact_schema="cleanwin.delivery-optimization-snapshot.v1",
            promotion_gate_id="official-command-to-executable-action",
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
            collection_method="defender-status-inventory",
            requires_admin=False,
            expected_artifact_schema="cleanwin.defender-state-snapshot.v1",
            promotion_gate_id="official-command-to-executable-action",
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
            collection_method="system-restore-point-inventory",
            requires_admin=True,
            expected_artifact_schema="cleanwin.restore-point-snapshot.v1",
            promotion_gate_id="windows-inventory-to-component-store-cleanup",
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
            collection_method="recycle-bin-shell-namespace-inventory",
            requires_admin=False,
            expected_artifact_schema="cleanwin.recycle-bin-inventory-snapshot.v1",
            promotion_gate_id="windows-inventory-to-recycle-bin-empty",
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
            collection_method="windows-installer-cache-inventory",
            requires_admin=True,
            expected_artifact_schema="cleanwin.installer-cache-snapshot.v1",
            promotion_gate_id="windows-inventory-to-installer-cache-cleanup",
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
            collection_method="dism-component-store-analysis",
            requires_admin=True,
            expected_artifact_schema="cleanwin.component-store-analysis.v1",
            promotion_gate_id="windows-inventory-to-component-store-cleanup",
            review_guidance=["Use DISM or Storage Settings only; never delete WinSxS directly."],
            protected_surfaces=[r"C:\Windows\WinSxS", "servicing stack", "component rollback"],
        ),
    ]
    available_sections = [section for section in sections if section["source"]["available"]]
    high_risk_sections = [section for section in sections if section["risk"] == "high"]
    appx_classifications = [
        item["cleanwin_classification"]
        for item in [*(enriched_appx_packages or []), *(enriched_provisioned_appx_packages or [])]
        if "cleanwin_classification" in item
    ]
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
            "requires_admin_collection_count": sum(1 for section in sections if section["collection_plan"]["requires_admin"]),
            "collection_plan_count": len(sections),
            "appx_classification_count": len(appx_classifications),
            "appx_protected_by_default_count": sum(1 for item in appx_classifications if item["protected_by_default"]),
            "appx_manual_review_count": sum(1 for item in appx_classifications if item["review_action"] == "manual-review"),
            "provisioned_appx_future_user_impact_count": sum(1 for item in appx_classifications if item["future_user_profile_impact"]),
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
