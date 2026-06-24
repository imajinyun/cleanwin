"""Read-only installed application inventory and leftover correlation."""

from __future__ import annotations

import os
import platform
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, cast

from cleanwincli.collectors import APP_LEFTOVER_RULES, app_leftover_rule_roots

INSTALLED_APP_INVENTORY_SCHEMA = "cleanwin.installed-app-inventory.v1"


def _source_status(source_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": source_id,
        "available": available,
        "reason": reason,
        "evidence": evidence or {},
    }


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _normalize_app_entry(entry: Mapping[str, Any], *, source: str) -> dict[str, Any] | None:
    display_name = str(entry.get("DisplayName") or entry.get("display_name") or "").strip()
    if not display_name:
        return None
    normalized_source = str(entry.get("source") or source)
    raw_estimated_size = entry.get("EstimatedSize") or entry.get("estimated_size_kb")
    estimated_size_kb: int | None = None
    try:
        if raw_estimated_size not in (None, ""):
            estimated_size_kb = int(cast(str, raw_estimated_size))
    except (TypeError, ValueError):
        estimated_size_kb = None
    app = {
        "source": normalized_source,
        "key_path": str(entry.get("key_path") or ""),
        "display_name": display_name,
        "display_version": str(entry.get("DisplayVersion") or entry.get("display_version") or "").strip(),
        "publisher": str(entry.get("Publisher") or entry.get("publisher") or "").strip(),
        "install_location": str(entry.get("InstallLocation") or entry.get("install_location") or "").strip(),
        "uninstall_string_present": bool(entry.get("UninstallString") or entry.get("uninstall_string")),
        "quiet_uninstall_string_present": bool(entry.get("QuietUninstallString") or entry.get("quiet_uninstall_string")),
        "estimated_size_kb": estimated_size_kb,
        "windows_installer": str(entry.get("WindowsInstaller") or entry.get("windows_installer") or "") == "1",
        "system_component": str(entry.get("SystemComponent") or entry.get("system_component") or "") == "1",
        "release_type": str(entry.get("ReleaseType") or entry.get("release_type") or "").strip(),
        "install_date": str(entry.get("InstallDate") or entry.get("install_date") or "").strip(),
    }
    app["uninstall_strategy"] = _uninstall_strategy(app)
    return app


def _uninstall_strategy(app: Mapping[str, Any]) -> dict[str, Any]:
    source = str(app.get("source") or "")
    release_type = str(app.get("release_type") or "")
    install_location = str(app.get("install_location") or "").lower()
    key_path = str(app.get("key_path") or "").lower()
    has_uninstall = bool(app.get("uninstall_string_present"))
    has_quiet = bool(app.get("quiet_uninstall_string_present"))
    windows_installer = bool(app.get("windows_installer"))
    system_component = bool(app.get("system_component"))
    if system_component:
        strategy_id = "system-component-review-only"
        confidence = "high"
        preferred = "Windows component or vendor servicing path"
        risk = "high"
    elif windows_installer:
        strategy_id = "msi-uninstall"
        confidence = "high"
        preferred = "Settings > Apps or msiexec uninstall after review"
        risk = "medium"
    elif source == "scoop":
        strategy_id = "scoop-uninstall"
        confidence = "high"
        preferred = "scoop uninstall <app>"
        risk = "low"
    elif source == "chocolatey":
        strategy_id = "chocolatey-uninstall"
        confidence = "high"
        preferred = "choco uninstall <package>"
        risk = "medium"
    elif source == "winget":
        strategy_id = "winget-uninstall"
        confidence = "high"
        preferred = "winget uninstall --id <package-id>"
        risk = "medium"
    elif source == "steam" or "steamapps" in install_location or "steam" in key_path:
        strategy_id = "steam-library-review"
        confidence = "medium"
        preferred = "Steam library uninstall workflow"
        risk = "medium"
    elif source == "portable-location" or release_type == "portable-directory":
        strategy_id = "portable-manual-review"
        confidence = "medium"
        preferred = "manual portable app removal after verifying no user data is stored in the directory"
        risk = "medium"
    elif "appx" in source or release_type.lower() in {"appx", "msix"}:
        strategy_id = "store-app-review-only"
        confidence = "medium"
        preferred = "Settings > Apps or documented AppX removal workflow after inventory snapshot"
        risk = "high"
    elif has_uninstall:
        strategy_id = "registry-uninstall-string"
        confidence = "high"
        preferred = "Settings > Apps or vendor uninstall entry"
        risk = "medium"
    else:
        strategy_id = "orphaned-entry-review"
        confidence = "low"
        preferred = "manual review; uninstall command evidence is missing"
        risk = "medium"
    return {
        "schema": "cleanwin.uninstall-strategy.v1",
        "strategy_id": strategy_id,
        "preferred": preferred,
        "confidence": confidence,
        "risk": risk,
        "uninstall_string_present": has_uninstall,
        "quiet_uninstall_string_present": has_quiet,
        "windows_installer": windows_installer,
        "system_component": system_component,
        "executes_by_report": False,
        "auto_executable": False,
        "review_steps": [
            "Review application identity, publisher, install location, and source before uninstall.",
            "Prefer Settings > Apps, vendor uninstallers, or package-manager uninstall commands.",
            "Capture installed-app inventory before and after any future uninstall workflow.",
        ],
    }


def _env_root(env: Mapping[str, str], key: str) -> Path | None:
    value = env.get(key)
    return Path(value) if value else None


def _windows_default_root(value: str) -> Path | None:
    return Path(value) if os.name == "nt" else None


def _registry_uninstall_entries() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if os.name != "nt":
        return [], [
            _source_status(
                "registry-uninstall",
                available=False,
                reason="not-windows",
                evidence={"os_name": os.name},
            )
        ]
    try:
        import winreg as _winreg  # type: ignore[import-not-found]
    except ImportError:
        return [], [_source_status("registry-uninstall", available=False, reason="winreg-unavailable")]
    winreg: Any = _winreg

    roots = [
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ("HKCU", winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    entries: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for root_name, hive, subkey_path in roots:
        source_id = f"registry-uninstall-{root_name.lower()}-{_normalize_token(subkey_path)[-12:]}"
        try:
            with winreg.OpenKey(hive, subkey_path, 0, winreg.KEY_READ) as root_key:
                subkey_count = winreg.QueryInfoKey(root_key)[0]
                for index in range(subkey_count):
                    subkey_name = winreg.EnumKey(root_key, index)
                    with winreg.OpenKey(root_key, subkey_name, 0, winreg.KEY_READ) as app_key:
                        value_count = winreg.QueryInfoKey(app_key)[1]
                        values: dict[str, Any] = {
                            "key_path": rf"{root_name}\{subkey_path}\{subkey_name}",
                        }
                        for value_index in range(value_count):
                            name, value, _value_type = winreg.EnumValue(app_key, value_index)
                            values[str(name)] = value
                        entries.append(values)
            sources.append(_source_status(source_id, available=True, reason="registry-key-read", evidence={"key": rf"{root_name}\{subkey_path}"}))
        except OSError as exc:
            sources.append(_source_status(source_id, available=False, reason="registry-key-unavailable", evidence={"key": rf"{root_name}\{subkey_path}", "error": str(exc)}))
    return entries, sources


def _scoop_apps(env: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_roots = [_env_root(env, "USERPROFILE") or _env_root(env, "HOME"), _env_root(env, "PROGRAMDATA") or _windows_default_root(r"C:\ProgramData")]
    roots = [root.joinpath("scoop", "apps") for root in base_roots if root is not None]
    apps: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            sources.append(_source_status("scoop-apps", available=False, reason="path-missing", evidence={"path": str(root)}))
            continue
        for child in sorted(item for item in root.iterdir() if item.is_dir()):
            app = {
                "source": "scoop",
                "key_path": str(child),
                "display_name": child.name,
                "display_version": "",
                "publisher": "Scoop",
                "install_location": str(child),
                "uninstall_string_present": False,
                "quiet_uninstall_string_present": False,
                "estimated_size_kb": None,
                "windows_installer": False,
                "system_component": False,
                "release_type": "scoop-package",
                "install_date": "",
            }
            app["uninstall_strategy"] = _uninstall_strategy(app)
            apps.append(app)
        sources.append(_source_status("scoop-apps", available=True, reason="filesystem-manifest", evidence={"path": str(root)}))
    return apps, sources


def _chocolatey_apps(env: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_root = _env_root(env, "PROGRAMDATA") or _windows_default_root(r"C:\ProgramData")
    if base_root is None:
        return [], [_source_status("chocolatey-lib", available=False, reason="path-root-unavailable")]
    root = base_root.joinpath("chocolatey", "lib")
    if not root.exists():
        return [], [_source_status("chocolatey-lib", available=False, reason="path-missing", evidence={"path": str(root)})]
    apps: list[dict[str, Any]] = []
    for package_dir in sorted(item for item in root.iterdir() if item.is_dir()):
        display_name = package_dir.name
        version = ""
        nuspecs = sorted(package_dir.glob("*.nuspec"))
        if nuspecs:
            try:
                metadata = ET.parse(nuspecs[0]).getroot().find(".//{*}metadata")
                if metadata is not None:
                    package_id = metadata.findtext("{*}id") or metadata.findtext("id")
                    package_version = metadata.findtext("{*}version") or metadata.findtext("version")
                    display_name = package_id or display_name
                    version = package_version or ""
            except ET.ParseError:
                pass
        app = {
            "source": "chocolatey",
            "key_path": str(package_dir),
            "display_name": display_name,
            "display_version": version,
            "publisher": "Chocolatey",
            "install_location": str(package_dir),
            "uninstall_string_present": False,
            "quiet_uninstall_string_present": False,
            "estimated_size_kb": None,
            "windows_installer": False,
            "system_component": False,
            "release_type": "chocolatey-package",
            "install_date": "",
        }
        app["uninstall_strategy"] = _uninstall_strategy(app)
        apps.append(app)
    return apps, [_source_status("chocolatey-lib", available=True, reason="filesystem-manifest", evidence={"path": str(root)})]


def _portable_locations(env: Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    profile = _env_root(env, "USERPROFILE") or _env_root(env, "HOME")
    base_roots = [
        (_env_root(env, "LOCALAPPDATA"), "Programs"),
        (profile, "Apps"),
        (profile, "PortableApps"),
    ]
    roots = [root.joinpath(suffix) for root, suffix in base_roots if root is not None]
    apps: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            sources.append(_source_status("portable-apps", available=False, reason="path-missing", evidence={"path": str(root)}))
            continue
        for child in sorted(item for item in root.iterdir() if item.is_dir()):
            app = {
                "source": "portable-location",
                "key_path": str(child),
                "display_name": child.name,
                "display_version": "",
                "publisher": "",
                "install_location": str(child),
                "uninstall_string_present": False,
                "quiet_uninstall_string_present": False,
                "estimated_size_kb": None,
                "windows_installer": False,
                "system_component": False,
                "release_type": "portable-directory",
                "install_date": "",
            }
            app["uninstall_strategy"] = _uninstall_strategy(app)
            apps.append(app)
        sources.append(_source_status("portable-apps", available=True, reason="filesystem-directory", evidence={"path": str(root)}))
    return apps, sources


def _app_matches_owner(app: Mapping[str, Any], owner: str) -> bool:
    owner_token = _normalize_token(owner)
    haystack = _normalize_token(f"{app.get('display_name', '')} {app.get('publisher', '')}")
    return bool(owner_token and owner_token in haystack)


def _leftover_correlations(apps: list[dict[str, Any]], env: Mapping[str, str]) -> list[dict[str, Any]]:
    existing_leftover_roots = {str(rule["rule_id"]): str(root) for rule, root in app_leftover_rule_roots(dict(env))}
    correlations: list[dict[str, Any]] = []
    for rule in APP_LEFTOVER_RULES:
        rule_id = str(rule["rule_id"])
        owner = str(rule["owner"])
        matches = [app for app in apps if _app_matches_owner(app, owner)]
        leftover_path = existing_leftover_roots.get(rule_id)
        if not matches and not leftover_path:
            continue
        if matches:
            state = "installed-application-present"
            recommendation = "skip-leftover-cleanup-until-uninstalled"
        else:
            state = "potential-uninstall-leftover"
            recommendation = "manual-review-before-cleanup-plan"
        correlations.append(
            {
                "rule_id": rule_id,
                "owner": owner,
                "state": state,
                "recommendation": recommendation,
                "leftover_path": leftover_path or "",
                "matched_applications": [
                    {
                        "display_name": app["display_name"],
                        "publisher": app["publisher"],
                        "source": app["source"],
                    }
                    for app in matches
                ],
            }
        )
    return correlations


def installed_app_inventory_report(
    *,
    raw_registry_entries: Iterable[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    current_env = dict(os.environ if env is None else env)
    if raw_registry_entries is None:
        registry_entries, sources = _registry_uninstall_entries()
    else:
        registry_entries = [dict(entry) for entry in raw_registry_entries]
        sources = [_source_status("registry-uninstall-injected", available=True, reason="test-fixture")]

    registry_apps = [
        app
        for app in (_normalize_app_entry(entry, source="registry-uninstall") for entry in registry_entries)
        if app is not None
    ]
    scoop_apps, scoop_sources = _scoop_apps(current_env)
    chocolatey_apps, chocolatey_sources = _chocolatey_apps(current_env)
    portable_apps, portable_sources = _portable_locations(current_env)
    applications = sorted(
        [*registry_apps, *scoop_apps, *chocolatey_apps, *portable_apps],
        key=lambda app: (str(app["display_name"]).lower(), str(app["source"]).lower(), str(app["key_path"]).lower()),
    )
    correlations = _leftover_correlations(applications, current_env)
    strategy_counts: dict[str, int] = {}
    for app in applications:
        strategy = app.get("uninstall_strategy", {})
        if isinstance(strategy, dict):
            strategy_id = str(strategy.get("strategy_id") or "unknown")
            strategy_counts[strategy_id] = strategy_counts.get(strategy_id, 0) + 1
    return {
        "schema": INSTALLED_APP_INVENTORY_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "sources": [
            *sources,
            *scoop_sources,
            *chocolatey_sources,
            *portable_sources,
            _source_status("winget", available=False, reason="external-command-not-executed", evidence={"command": "winget list"}),
            _source_status("appx", available=False, reason="external-command-not-executed", evidence={"command": "Get-AppxPackage -AllUsers"}),
        ],
        "applications": applications,
        "leftover_correlations": correlations,
        "summary": {
            "application_count": len(applications),
            "registry_application_count": len(registry_apps),
            "leftover_correlation_count": len(correlations),
            "potential_uninstall_leftover_count": sum(1 for item in correlations if item["state"] == "potential-uninstall-leftover"),
            "installed_application_present_count": sum(1 for item in correlations if item["state"] == "installed-application-present"),
            "uninstall_strategy_counts": dict(sorted(strategy_counts.items())),
            "manual_review_strategy_count": sum(
                1
                for app in applications
                if str(app.get("uninstall_strategy", {}).get("strategy_id", "")).endswith("review")
                or "review" in str(app.get("uninstall_strategy", {}).get("strategy_id", ""))
            ),
        },
        "non_goals": [
            "This report does not uninstall applications.",
            "This report does not delete leftover paths.",
            "This report does not delete or modify registry keys.",
            "This report does not execute package manager or PowerShell commands.",
        ],
    }
