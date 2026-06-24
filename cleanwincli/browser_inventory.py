"""Read-only browser profile inventory and cache layer classification."""

from __future__ import annotations

import os
import platform
from collections.abc import Mapping
from pathlib import Path
from typing import Any

BROWSER_PROFILE_INVENTORY_SCHEMA = "cleanwin.browser-profile-inventory.v1"

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


def _source_status(source_id: str, *, available: bool, reason: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": source_id, "available": available, "reason": reason, "evidence": evidence or {}}


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


def _locked_state(profile_path: Path) -> dict[str, Any]:
    lock_files = ["SingletonLock", "lock", ".parentlock", "parent.lock"]
    evidence = []
    for name in lock_files:
        path = profile_path / name
        if _path_exists(path):
            evidence.append({"path": str(path), "exists": True})
    return {
        "locked": bool(evidence),
        "state": "locked-or-running" if evidence else "not-observed",
        "evidence": evidence,
        "method": "lock-file-presence",
    }


def _cache_layers(profile_path: Path, layer_map: Mapping[str, str]) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for relative_path, layer_type in layer_map.items():
        path = profile_path.joinpath(*relative_path.split("/"))
        exists = _path_exists(path)
        layers.append(
            {
                "name": relative_path,
                "type": layer_type,
                "path": str(path),
                "exists": exists,
                "size_bytes": _dir_size(path) if exists else 0,
                "promotable": layer_type in {"http-cache", "code-cache", "gpu-cache", "shader-cache"},
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
            pass
    return sorted(set(names), key=str.lower)


def _chromium_profiles(browser: str, owner: str, root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profiles = []
    for profile_name in _chromium_profile_names(root):
        profile_path = root / profile_name
        if not _path_exists(profile_path):
            continue
        profiles.append(
            {
                "browser": browser,
                "owner": owner,
                "engine": "chromium",
                "profile_name": profile_name,
                "profile_path": str(profile_path),
                "profile_exists": True,
                "locked_profile": _locked_state(profile_path),
                "cache_layers": _cache_layers(profile_path, CHROMIUM_CACHE_LAYERS),
                "sensitive_exclusions": SENSITIVE_EXCLUSIONS,
                "safe_to_execute": False,
            }
        )
    source = _source_status(browser.lower(), available=_path_exists(root), reason="profile-root-scan", evidence={"root": str(root)})
    return profiles, source


def _firefox_profiles(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profiles = []
    profile_roots: list[Path] = []
    if _path_exists(root):
        try:
            profile_roots = [path for path in root.iterdir() if path.is_dir()]
        except OSError:
            profile_roots = []
    for profile_path in sorted(profile_roots, key=lambda item: item.name.lower()):
        profiles.append(
            {
                "browser": "firefox",
                "owner": "Mozilla Firefox",
                "engine": "firefox",
                "profile_name": profile_path.name,
                "profile_path": str(profile_path),
                "profile_exists": True,
                "locked_profile": _locked_state(profile_path),
                "cache_layers": _cache_layers(profile_path, FIREFOX_CACHE_LAYERS),
                "sensitive_exclusions": SENSITIVE_EXCLUSIONS,
                "safe_to_execute": False,
            }
        )
    return profiles, _source_status("firefox", available=_path_exists(root), reason="profile-root-scan", evidence={"root": str(root)})


def browser_profile_inventory_report(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    current_env = dict(os.environ if env is None else env)
    local_app_data = current_env.get("LOCALAPPDATA")
    roaming_app_data = current_env.get("APPDATA")
    user_profile = current_env.get("USERPROFILE") or current_env.get("HOME")

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
        browser_profiles, source = _chromium_profiles(browser, owner, root)
        profiles.extend(browser_profiles)
        sources.append(source)

    if roaming_app_data:
        firefox_profiles, source = _firefox_profiles(Path(roaming_app_data) / "Mozilla" / "Firefox" / "Profiles")
        profiles.extend(firefox_profiles)
        sources.append(source)
    else:
        sources.append(_source_status("firefox", available=False, reason="appdata-env-missing"))

    cache_layers = [layer for profile in profiles for layer in profile["cache_layers"]]
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
            "cache_layer_count": len(cache_layers),
            "existing_cache_layer_count": sum(1 for layer in cache_layers if layer["exists"]),
            "promotable_cache_layer_count": sum(1 for layer in cache_layers if layer["promotable"]),
            "bytes_reported": sum(int(layer["size_bytes"]) for layer in cache_layers),
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
