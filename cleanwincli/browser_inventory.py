"""Read-only browser profile inventory and cache layer classification."""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cleanwincli.report_helpers import source_status

BROWSER_PROFILE_INVENTORY_SCHEMA = "cleanwin.browser-profile-inventory.v1"
LOCKED_STATE_SCHEMA = "cleanwin.locked-state.v1"

SENSITIVE_EXCLUSIONS = [
    "Cookies",
    "Login Data",
    "Local State",
    "Preferences",
    "Sessions",
    "Session Storage",
    "Extensions",
    "History",
    "Bookmarks",
    "Web Data",
    "key4.db",
    "logins.json",
    "cookies.sqlite",
    "places.sqlite",
]

CHROMIUM_CACHE_LAYERS = {
    "Cache": "http-cache",
    "Code Cache": "code-cache",
    "GPUCache": "gpu-cache",
    "ShaderCache": "shader-cache",
    "GrShaderCache": "shader-cache",
    "Crashpad": "crash-reports",
    "Service Worker/CacheStorage": "service-worker-cache",
}

FIREFOX_CACHE_LAYERS = {
    "cache2": "http-cache",
    "startupCache": "startup-cache",
    "shader-cache": "shader-cache",
    "crashes": "crash-reports",
}

_BROWSER_PROCESS_NAMES = {
    "chrome": {"chrome.exe", "chrome", "chrome_proxy.exe"},
    "edge": {"msedge.exe", "msedge", "microsoftedge.exe"},
    "brave": {"brave.exe", "brave"},
    "chrome-canary": {"chrome.exe", "chrome", "chrome_proxy.exe"},
    "firefox": {"firefox.exe", "firefox", "plugin-container.exe"},
}

_RELATED_APP_PROCESS_NAMES = {
    "electron.exe",
    "code.exe",
    "cursor.exe",
    "teams.exe",
    "slack.exe",
    "discord.exe",
    "idea64.exe",
    "pycharm64.exe",
    "webstorm64.exe",
}


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _dir_size(path: Path) -> int:
    if not _path_exists(path):
        return 0
    total = 0
    try:
        iterator = path.rglob("*") if path.is_dir() else iter([path])
    except OSError:
        return 0
    for child in iterator:
        try:
            if child.is_file() and not child.is_symlink():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _running_process_names(env: Mapping[str, str]) -> tuple[set[str], bool]:
    raw = env.get("CLEANWIN_RUNNING_PROCESSES") or env.get("CLEANWIN_TEST_RUNNING_PROCESSES") or ""
    if not raw:
        return set(), False
    separators = [",", ";", "\n", "\r", "\t"]
    normalized = raw
    for separator in separators:
        normalized = normalized.replace(separator, " ")
    return {item.strip().lower() for item in normalized.split(" ") if item.strip()}, True


def _process_evidence(browser: str, process_names: set[str]) -> list[dict[str, Any]]:
    expected = _BROWSER_PROCESS_NAMES.get(browser, set())
    matches = sorted(name for name in process_names if name in expected)
    related = sorted(name for name in process_names if name in _RELATED_APP_PROCESS_NAMES)
    evidence: list[dict[str, Any]] = [
        {"process_name": name, "exists": True, "indicator_type": "browser-process-running"} for name in matches
    ]
    evidence.extend({"process_name": name, "exists": True, "indicator_type": "related-electron-or-ide-process-running"} for name in related)
    return evidence


def _locked_state(profile_path: Path, *, browser: str, process_names: set[str], process_scan_performed: bool) -> dict[str, Any]:
    indicators = {
        "process-lock-file": ["SingletonLock", "lock", ".parentlock", "parent.lock", "parentlock"],
        "socket-or-cookie-lock": ["SingletonSocket", "SingletonCookie"],
        "profile-database-wal": [
            "Cookies-wal",
            "Cookies-shm",
            "History-wal",
            "History-shm",
            "Login Data-wal",
            "Login Data-shm",
            "Web Data-wal",
            "Web Data-shm",
            "places.sqlite-wal",
            "places.sqlite-shm",
            "cookies.sqlite-wal",
            "cookies.sqlite-shm",
            "favicons.sqlite-wal",
            "favicons.sqlite-shm",
        ],
    }
    evidence = []
    for indicator_type, names in indicators.items():
        for name in names:
            path = profile_path / name
            if _path_exists(path):
                evidence.append({"path": str(path), "exists": True, "indicator_type": indicator_type})
    evidence.extend(_process_evidence(browser, process_names))
    blocked_reasons = []
    if any(item["indicator_type"] == "process-lock-file" for item in evidence):
        blocked_reasons.append("profile-lock-file-present")
    if any(item["indicator_type"] == "socket-or-cookie-lock" for item in evidence):
        blocked_reasons.append("browser-singleton-lock-present")
    if any(item["indicator_type"] == "profile-database-wal" for item in evidence):
        blocked_reasons.append("profile-database-write-ahead-log-present")
    if any(item["indicator_type"] == "browser-process-running" for item in evidence):
        blocked_reasons.append("browser-process-running")
    if any(item["indicator_type"] == "related-electron-or-ide-process-running" for item in evidence):
        blocked_reasons.append("related-electron-or-ide-process-running")
    return {
        "schema": LOCKED_STATE_SCHEMA,
        "locked": bool(evidence),
        "state": "locked-or-running" if evidence else "not-observed",
        "evidence": evidence,
        "blocked_reasons": blocked_reasons,
        "method": "filesystem-and-process-indicator-scan" if process_scan_performed else "filesystem-lock-indicator-scan",
        "process_scan_performed": process_scan_performed,
        "process_scan_source": "provided-process-list" if process_scan_performed else "not-performed",
        "safe_to_execute": False,
    }


def _layer_lock_state(profile_lock: dict[str, Any], layer_path: Path) -> dict[str, Any]:
    layer_indicators = []
    for suffix in ("LOCK", "LOCKFILE", ".lock", "lock"):
        path = layer_path / suffix
        if _path_exists(path):
            layer_indicators.append({"path": str(path), "exists": True, "indicator_type": "cache-layer-lock"})
    blocked_reasons = list(profile_lock.get("blocked_reasons", []))
    if layer_indicators:
        blocked_reasons.append("cache-layer-lock-present")
    return {
        "schema": LOCKED_STATE_SCHEMA,
        "locked": bool(profile_lock.get("locked")) or bool(layer_indicators),
        "state": "locked-or-running" if profile_lock.get("locked") or layer_indicators else "not-observed",
        "evidence": [*profile_lock.get("evidence", []), *layer_indicators],
        "blocked_reasons": sorted(set(blocked_reasons)),
        "method": "profile-and-cache-layer-lock-indicator-scan",
        "process_scan_performed": bool(profile_lock.get("process_scan_performed")),
        "process_scan_source": profile_lock.get("process_scan_source", "not-performed"),
        "safe_to_execute": False,
    }


def _cache_layers(profile_path: Path, layer_map: Mapping[str, str], profile_lock: dict[str, Any]) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for relative_path, layer_type in layer_map.items():
        path = profile_path.joinpath(*relative_path.split("/"))
        exists = _path_exists(path)
        layer_lock = _layer_lock_state(profile_lock, path)
        layers.append(
            {
                "name": relative_path,
                "type": layer_type,
                "path": str(path),
                "exists": exists,
                "size_bytes": _dir_size(path) if exists else 0,
                "promotable": layer_type in {"http-cache", "code-cache", "gpu-cache", "shader-cache"},
                "locked_state": layer_lock,
                "blocked_reasons": layer_lock["blocked_reasons"],
                "safe_to_execute": False,
            }
        )
    return layers


def _chromium_profile_names(root: Path) -> list[str]:
    names = ["Default"]
    if _path_exists(root):
        try:
            names.extend(path.name for path in root.iterdir() if path.is_dir() and path.name.startswith("Profile "))
        except OSError:
            pass  # Unreadable profile directory: fall back to Default only
    return sorted(set(names), key=str.lower)


def _chromium_profiles(browser: str, owner: str, root: Path, *, process_names: set[str], process_scan_performed: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profiles = []
    for profile_name in _chromium_profile_names(root):
        profile_path = root / profile_name
        if not _path_exists(profile_path):
            continue
        profile_lock = _locked_state(profile_path, browser=browser, process_names=process_names, process_scan_performed=process_scan_performed)
        profiles.append(
            {
                "browser": browser,
                "owner": owner,
                "engine": "chromium",
                "profile_name": profile_name,
                "profile_path": str(profile_path),
                "profile_exists": True,
                "locked_profile": profile_lock,
                "cache_layers": _cache_layers(profile_path, CHROMIUM_CACHE_LAYERS, profile_lock),
                "sensitive_exclusions": SENSITIVE_EXCLUSIONS,
                "safe_to_execute": False,
            }
        )
    source = source_status(browser.lower(), available=_path_exists(root), reason="profile-root-scan", evidence={"root": str(root)})
    return profiles, source


def _firefox_profiles(root: Path, *, process_names: set[str], process_scan_performed: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profiles = []
    profile_roots: list[Path] = []
    if _path_exists(root):
        try:
            profile_roots = [path for path in root.iterdir() if path.is_dir()]
        except OSError:
            profile_roots = []
    for profile_path in sorted(profile_roots, key=lambda item: item.name.lower()):
        profile_lock = _locked_state(profile_path, browser="firefox", process_names=process_names, process_scan_performed=process_scan_performed)
        profiles.append(
            {
                "browser": "firefox",
                "owner": "Mozilla Firefox",
                "engine": "firefox",
                "profile_name": profile_path.name,
                "profile_path": str(profile_path),
                "profile_exists": True,
                "locked_profile": profile_lock,
                "cache_layers": _cache_layers(profile_path, FIREFOX_CACHE_LAYERS, profile_lock),
                "sensitive_exclusions": SENSITIVE_EXCLUSIONS,
                "safe_to_execute": False,
            }
        )
    return profiles, source_status("firefox", available=_path_exists(root), reason="profile-root-scan", evidence={"root": str(root)})


def browser_profile_inventory_report(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    current_env = dict(os.environ if env is None else env)
    local_app_data = current_env.get("LOCALAPPDATA")
    roaming_app_data = current_env.get("APPDATA")
    user_profile = current_env.get("USERPROFILE") or current_env.get("HOME")
    process_names, process_scan_performed = _running_process_names(current_env)

    chromium_roots: list[tuple[str, str, Path]] = []
    if local_app_data:
        local = Path(local_app_data)
        chromium_roots.extend(
            [
                ("chrome", "Google Chrome", local / "Google" / "Chrome" / "User Data"),
                ("edge", "Microsoft Edge", local / "Microsoft" / "Edge" / "User Data"),
                ("brave", "Brave", local / "BraveSoftware" / "Brave-Browser" / "User Data"),
            ]
        )
    if user_profile:
        chromium_roots.append(("chrome-canary", "Google Chrome Canary", Path(user_profile) / "AppData" / "Local" / "Google" / "Chrome SxS" / "User Data"))

    profiles: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for browser, owner, root in chromium_roots:
        browser_profiles, source = _chromium_profiles(browser, owner, root, process_names=process_names, process_scan_performed=process_scan_performed)
        profiles.extend(browser_profiles)
        sources.append(source)

    if roaming_app_data:
        firefox_profiles, source = _firefox_profiles(Path(roaming_app_data) / "Mozilla" / "Firefox" / "Profiles", process_names=process_names, process_scan_performed=process_scan_performed)
        profiles.extend(firefox_profiles)
        sources.append(source)
    else:
        sources.append(source_status("firefox", available=False, reason="appdata-env-missing"))

    cache_layers = [layer for profile in profiles for layer in profile["cache_layers"]]
    locked_layers = [layer for layer in cache_layers if layer["locked_state"]["locked"]]
    return {
        "schema": BROWSER_PROFILE_INVENTORY_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"},
        "sources": sources,
        "profiles": profiles,
        "summary": {
            "profile_count": len(profiles),
            "locked_profile_count": sum(1 for profile in profiles if profile["locked_profile"]["locked"]),
            "locked_cache_layer_count": len(locked_layers),
            "cache_layer_count": len(cache_layers),
            "existing_cache_layer_count": sum(1 for layer in cache_layers if layer["exists"]),
            "promotable_cache_layer_count": sum(1 for layer in cache_layers if layer["promotable"]),
            "bytes_reported": sum(int(layer["size_bytes"]) for layer in cache_layers),
            "process_scan_performed": process_scan_performed,
            "running_process_indicator_count": sum(
                1 for profile in profiles for item in profile["locked_profile"]["evidence"] if str(item.get("indicator_type", "")).endswith("process-running")
            ),
        },
        "execution_gate": {
            "system_execution_enabled": False,
            "cache_execution_enabled": False,
            "requires_locked_profile_check": True,
            "requires_sensitive_exclusions": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not delete browser cache files.",
            "This report never promotes cookies, passwords, sessions, extensions, history, bookmarks, or profile databases.",
            "This report does not execute browser, PowerShell, or operating-system commands.",
        ],
    }
