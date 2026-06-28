"""Conservative CleanWin candidate collectors."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cleanwincli.identity import capture_filesystem_identity
from cleanwincli.models import Candidate, Finding
from cleanwincli.protection import validate_filesystem_candidate
from cleanwincli.protection_data import DEFAULT_SAFE_CATEGORIES, READ_ONLY_CATEGORIES
from cleanwincli.rule_catalog import browser_profile_cache_rules, catalog_rules

DEV_CACHE_RULES = cast(tuple[dict[str, str], ...], catalog_rules("dev_cache_rules"))
PACKAGE_CACHE_RULES = cast(tuple[dict[str, str], ...], catalog_rules("package_cache_rules"))
BROWSER_CACHE_RULES = cast(tuple[dict[str, str], ...], catalog_rules("browser_cache_rules"))
BROWSER_PROFILE_CACHE_RULES = browser_profile_cache_rules()
APP_LEFTOVER_RULES = cast(tuple[dict[str, object], ...], catalog_rules("app_leftover_rules"))


def parse_categories(value: str | None) -> list[str]:
    if not value:
        return sorted(DEFAULT_SAFE_CATEGORIES)
    categories = [item.strip() for item in value.split(",") if item.strip()]
    return categories or sorted(DEFAULT_SAFE_CATEGORIES)


def parse_rule_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _matches_rule_filter(rule_id: str | None, allowed_rule_ids: set[str]) -> bool:
    if not allowed_rule_ids:
        return True
    return bool(rule_id and rule_id in allowed_rule_ids)


def _path_evidence(paths: list[str]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for raw_path in paths:
        item: dict[str, object] = {"path": raw_path}
        lowered = raw_path.lower()
        if lowered.startswith(("hkcu\\", "hklm\\", "hkcr\\", "hku\\", "hkcc\\")):
            item.update({"kind": "registry-key", "exists": None, "scanned": False})
            evidence.append(item)
            continue
        if "%" in raw_path:
            item.update({"kind": "unexpanded-path", "exists": None, "scanned": False})
            evidence.append(item)
            continue
        path = Path(raw_path)
        exists = path.exists()
        item["exists"] = exists
        item["scanned"] = True
        if not exists:
            item["kind"] = "missing"
            evidence.append(item)
            continue
        if path.is_symlink():
            item["kind"] = "symlink"
            evidence.append(item)
            continue
        if path.is_file():
            item["kind"] = "file"
            try:
                item["size_bytes"] = path.stat().st_size
            except OSError:
                item["size_bytes"] = None
            evidence.append(item)
            continue
        if path.is_dir():
            item["kind"] = "directory"
            try:
                item["child_count"] = sum(1 for _ in path.iterdir())
            except OSError:
                item["child_count"] = None
            evidence.append(item)
            continue
        item["kind"] = "other"
        evidence.append(item)
    return evidence


def _review_details(*, suggested_paths: list[str], risk_notes: list[str], manual_review_steps: list[str]) -> dict[str, object]:
    path_evidence = _path_evidence(suggested_paths)
    return {
        "suggested_paths": suggested_paths,
        "path_evidence": path_evidence,
        "evidence_summary": {
            "path_count": len(path_evidence),
            "existing_path_count": sum(1 for item in path_evidence if item.get("exists") is True),
            "scanned_path_count": sum(1 for item in path_evidence if item.get("scanned") is True),
        },
        "risk_notes": risk_notes,
        "manual_review_steps": manual_review_steps,
    }


def file_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        try:
            if child.is_file() and not child.is_symlink():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except OSError:
        return None


def older_than_days(path: Path, days: int) -> bool:
    if days <= 0:
        return True
    try:
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    except OSError:
        return False
    return age >= days * 86400


def iter_children(root: Path, *, older_than: int, max_items: int) -> Iterable[Path]:
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return []
    found: list[Path] = []
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []
    for child in children:
        if len(found) >= max_items:
            break
        if child.is_symlink() or not older_than_days(child, older_than):
            continue
        found.append(child)
    return found


def candidate_for(
    path: Path,
    *,
    category: str,
    reason: str,
    rule_id: str | None = None,
    cache_owner: str | None = None,
    official_cleanup_command: str | None = None,
    safe_to_delete_rationale: str | None = None,
    cache_layer: str | None = None,
    cache_layer_family: str | None = None,
) -> Candidate | None:
    if not path.exists():
        return None
    try:
        validate_filesystem_candidate(path)
    except RuntimeError:
        return None
    return Candidate(
        path=str(path),
        category=category,
        size_bytes=file_size(path),
        reason=reason,
        safe_to_delete=True,
        risk="low",
        modified_at=iso_mtime(path),
        identity=capture_filesystem_identity(path),
        rule_id=rule_id,
        cache_owner=cache_owner,
        official_cleanup_command=official_cleanup_command,
        safe_to_delete_rationale=safe_to_delete_rationale,
        cache_layer=cache_layer,
        cache_layer_family=cache_layer_family,
    )


def temp_roots(env: dict[str, str]) -> list[Path]:
    roots: list[Path] = []
    for key in ("TEMP", "TMP"):
        value = env.get(key)
        if value:
            roots.append(Path(value))
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "Temp")
    return dedupe_paths(roots)


def _default_rule_path(rule: dict[str, str], *, local_app_data: str | None, user_profile: str | None) -> Path | None:
    default = rule["default"]
    if default.startswith("local:"):
        if not local_app_data:
            return None
        return Path(local_app_data).joinpath(*default.removeprefix("local:").split("/"))
    if default.startswith("home:"):
        if not user_profile:
            return None
        return Path(user_profile).joinpath(*default.removeprefix("home:").split("/"))
    return None


def dev_cache_roots(env: dict[str, str]) -> list[Path]:
    roots: list[Path] = []
    local_app_data = env.get("LOCALAPPDATA")
    user_profile = env.get("USERPROFILE") or env.get("HOME")
    for rule in DEV_CACHE_RULES:
        value = env.get(rule["env_key"])
        if value:
            path = Path(value)
            if rule["rule_id"] == "dev-cache.cargo.registry":
                path = path / "registry" / "cache"
            if rule["rule_id"] == "dev-cache.gradle.caches":
                path = path / "caches"
            roots.append(path)
        default_path = _default_rule_path(rule, local_app_data=local_app_data, user_profile=user_profile)
        if default_path is not None:
            roots.append(default_path)
    return dedupe_paths(roots)


def dev_cache_rule_roots(env: dict[str, str]) -> list[tuple[dict[str, str], Path]]:
    local_app_data = env.get("LOCALAPPDATA")
    user_profile = env.get("USERPROFILE") or env.get("HOME")
    roots: list[tuple[dict[str, str], Path]] = []
    for rule in DEV_CACHE_RULES:
        value = env.get(rule["env_key"])
        paths: list[Path] = []
        if value:
            path = Path(value)
            if rule["rule_id"] == "dev-cache.cargo.registry":
                path = path / "registry" / "cache"
            if rule["rule_id"] == "dev-cache.gradle.caches":
                path = path / "caches"
            paths.append(path)
        default_path = _default_rule_path(rule, local_app_data=local_app_data, user_profile=user_profile)
        if default_path is not None:
            paths.append(default_path)
        for path in dedupe_paths(paths):
            roots.append((rule, path))
    seen: set[str] = set()
    deduped: list[tuple[dict[str, str], Path]] = []
    for rule, path in roots:
        key = str(path.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((rule, path))
    return deduped


def _default_prefixed_rule_path(
    default: str,
    *,
    local_app_data: str | None,
    user_profile: str | None,
    program_data: str | None,
    roaming_app_data: str | None = None,
    program_files: str | None = None,
    program_files_x86: str | None = None,
) -> Path | None:
    if default.startswith("local:"):
        if not local_app_data:
            return None
        return Path(local_app_data).joinpath(*default.removeprefix("local:").split("/"))
    if default.startswith("home:"):
        if not user_profile:
            return None
        return Path(user_profile).joinpath(*default.removeprefix("home:").split("/"))
    if default.startswith("programdata:"):
        if not program_data:
            return None
        return Path(program_data).joinpath(*default.removeprefix("programdata:").split("/"))
    if default.startswith("roaming:"):
        if not roaming_app_data:
            return None
        return Path(roaming_app_data).joinpath(*default.removeprefix("roaming:").split("/"))
    if default.startswith("programfiles:"):
        if not program_files:
            return None
        return Path(program_files).joinpath(*default.removeprefix("programfiles:").split("/"))
    if default.startswith("programfilesx86:"):
        if not program_files_x86:
            return None
        return Path(program_files_x86).joinpath(*default.removeprefix("programfilesx86:").split("/"))
    return None


def generic_rule_roots(rules: tuple[dict[str, str], ...], env: dict[str, str]) -> list[tuple[dict[str, str], Path]]:
    local_app_data = env.get("LOCALAPPDATA")
    user_profile = env.get("USERPROFILE") or env.get("HOME")
    program_data = env.get("PROGRAMDATA") or r"C:\ProgramData"
    roots: list[tuple[dict[str, str], Path]] = []
    for rule in rules:
        path = _default_prefixed_rule_path(
            rule["default"],
            local_app_data=local_app_data,
            user_profile=user_profile,
            program_data=program_data,
        )
        if path is not None:
            roots.append((rule, path))
    seen: set[str] = set()
    deduped: list[tuple[dict[str, str], Path]] = []
    for rule, path in roots:
        key = str(path.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((rule, path))
    return deduped


def _expand_existing_wildcard_path(path: Path) -> list[Path]:
    parts = path.parts
    wildcard_index = next((index for index, part in enumerate(parts) if any(char in part for char in "*?[]")), None)
    if wildcard_index is None:
        return [path]
    prefix = Path(parts[0]).joinpath(*parts[1:wildcard_index]) if wildcard_index else Path("*")
    pattern = parts[wildcard_index].lower()
    suffix = parts[wildcard_index + 1 :]
    if not prefix.exists() or not prefix.is_dir() or prefix.is_symlink():
        return []
    expanded: list[Path] = []
    try:
        children = sorted(prefix.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []
    for child in children:
        if child.is_symlink() or not fnmatch.fnmatchcase(child.name.lower(), pattern):
            continue
        candidate = child.joinpath(*suffix)
        expanded.extend(_expand_existing_wildcard_path(candidate))
    return expanded


def _rule_specificity(rule: dict[str, object]) -> tuple[int, int, int]:
    default = str(rule.get("default") or "")
    segment_count = len([segment for segment in default.split("/", maxsplit=-1) if segment])
    wildcard_count = sum(default.count(char) for char in "*?[]")
    literal_count = sum(1 for char in default if char not in "*?[]")
    return (segment_count, -wildcard_count, literal_count)


def _active_marker_exists(marker: str, *, env: dict[str, str]) -> bool:
    local_app_data = env.get("LOCALAPPDATA")
    roaming_app_data = env.get("APPDATA")
    user_profile = env.get("USERPROFILE") or env.get("HOME")
    program_data = env.get("PROGRAMDATA") or r"C:\ProgramData"
    program_files = env.get("PROGRAMFILES") or r"C:\Program Files"
    program_files_x86 = env.get("PROGRAMFILES(X86)") or env.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    path = _default_prefixed_rule_path(
        marker,
        local_app_data=local_app_data,
        user_profile=user_profile,
        program_data=program_data,
        roaming_app_data=roaming_app_data,
        program_files=program_files,
        program_files_x86=program_files_x86,
    )
    if path is None:
        return False
    return any(candidate.exists() for candidate in _expand_existing_wildcard_path(path))


def app_leftover_rule_roots(env: dict[str, str]) -> list[tuple[dict[str, object], Path]]:
    local_app_data = env.get("LOCALAPPDATA")
    roaming_app_data = env.get("APPDATA")
    user_profile = env.get("USERPROFILE") or env.get("HOME")
    program_data = env.get("PROGRAMDATA") or r"C:\ProgramData"
    program_files = env.get("PROGRAMFILES") or r"C:\Program Files"
    program_files_x86 = env.get("PROGRAMFILES(X86)") or env.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"
    roots: list[tuple[dict[str, object], Path]] = []
    for rule in APP_LEFTOVER_RULES:
        raw_markers = rule.get("active_markers", ())
        markers = tuple(str(marker) for marker in raw_markers) if isinstance(raw_markers, Iterable) else ()
        if any(_active_marker_exists(marker, env=env) for marker in markers):
            continue
        default = str(rule["default"])
        path = _default_prefixed_rule_path(
            default,
            local_app_data=local_app_data,
            user_profile=user_profile,
            program_data=program_data,
            roaming_app_data=roaming_app_data,
            program_files=program_files,
            program_files_x86=program_files_x86,
        )
        if path is None:
            continue
        for expanded in _expand_existing_wildcard_path(path):
            roots.append((rule, expanded))
    best_by_path: dict[str, tuple[dict[str, object], Path]] = {}
    for rule, path in roots:
        key = str(path.resolve(strict=False)).lower()
        existing = best_by_path.get(key)
        if existing is None or _rule_specificity(rule) > _rule_specificity(existing[0]):
            best_by_path[key] = (rule, path)
    return sorted(best_by_path.values(), key=lambda item: (str(item[1]).lower(), str(item[0].get("rule_id") or "")))


def browser_profile_cache_roots(env: dict[str, str]) -> list[tuple[dict[str, str], Path]]:
    local_app_data = env.get("LOCALAPPDATA")
    roaming_app_data = env.get("APPDATA")
    roots: list[tuple[dict[str, str], Path]] = []
    browser_roots: list[tuple[Path, str]] = []
    if local_app_data:
        browser_roots.extend(
            [
                (Path(local_app_data) / "Google" / "Chrome" / "User Data", "chrome"),
                (Path(local_app_data) / "Microsoft" / "Edge" / "User Data", "edge"),
                (Path(local_app_data) / "BraveSoftware" / "Brave-Browser" / "User Data", "brave"),
            ]
        )
    for user_data_root, browser_key in browser_roots:
        if not user_data_root.exists() or not user_data_root.is_dir() or user_data_root.is_symlink():
            continue
        try:
            profiles = sorted(user_data_root.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        chromium_layers = (
            ("Cache", "cache"),
            ("Code Cache", "code-cache"),
            ("GPUCache", "gpu-cache"),
            ("ShaderCache", "shader-cache"),
            ("GrShaderCache", "shader-cache"),
            ("Service Worker/CacheStorage", "service-worker-cache"),
            ("Crashpad/reports", "crashpad-reports"),
        )
        for profile in profiles:
            if not profile.is_dir() or profile.is_symlink():
                continue
            for leaf, suffix in chromium_layers:
                cache_path = profile / leaf
                if cache_path.exists() and cache_path.is_dir() and not cache_path.is_symlink():
                    roots.append((BROWSER_PROFILE_CACHE_RULES[f"{browser_key}-{suffix}"], cache_path))
    firefox_profile_roots: list[Path] = []
    if local_app_data:
        firefox_profile_roots.append(Path(local_app_data) / "Mozilla" / "Firefox" / "Profiles")
    if roaming_app_data:
        firefox_profile_roots.append(Path(roaming_app_data) / "Mozilla" / "Firefox" / "Profiles")
    for profiles_root in firefox_profile_roots:
        if not profiles_root.exists() or not profiles_root.is_dir() or profiles_root.is_symlink():
            continue
        try:
            profiles = sorted(profiles_root.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for profile in profiles:
            firefox_layers = (
                ("cache2", "firefox-cache2"),
                ("startupCache", "firefox-startup-cache"),
                ("shader-cache", "firefox-shader-cache"),
                ("crashes", "firefox-crashes"),
            )
            for leaf, rule_key in firefox_layers:
                cache_path = profile / leaf
                if cache_path.exists() and cache_path.is_dir() and not cache_path.is_symlink():
                    roots.append((BROWSER_PROFILE_CACHE_RULES[rule_key], cache_path))
    seen: set[str] = set()
    deduped: list[tuple[dict[str, str], Path]] = []
    for rule, path in roots:
        key = str(path.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((rule, path))
    return deduped


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    deduped: list[Path] = []
    for path in paths:
        key = str(path.resolve(strict=False)).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def collect_candidates(
    categories: list[str],
    *,
    env: dict[str, str] | None = None,
    older_than_days_value: int = 7,
    max_items: int = 100,
    rule_ids: list[str] | None = None,
) -> list[Candidate]:
    env = env or dict(os.environ)
    candidates: list[Candidate] = []
    per_root_limit = max(1, max_items)
    allowed_rule_ids = {item for item in (rule_ids or []) if item}
    if "temp" in categories:
        for root in temp_roots(env):
            for path in iter_children(root, older_than=older_than_days_value, max_items=per_root_limit):
                candidate = candidate_for(
                    path,
                    category="temp",
                    reason=f"Older than {older_than_days_value} days under temp root {root}",
                    safe_to_delete_rationale="Temporary files under the configured temp root are expected to be regenerated by applications.",
                )
                if candidate:
                    candidates.append(candidate)
                if len(candidates) >= max_items:
                    return candidates
    if "dev-cache" in categories:
        for rule, root in dev_cache_rule_roots(env):
            if not _matches_rule_filter(rule["rule_id"], allowed_rule_ids):
                continue
            for path in iter_children(root, older_than=older_than_days_value, max_items=per_root_limit):
                candidate = candidate_for(
                    path,
                    category="dev-cache",
                    reason=f"{rule['owner']} cache entry under {root}",
                    rule_id=rule["rule_id"],
                    cache_owner=rule["owner"],
                    official_cleanup_command=rule["official_cleanup_command"],
                    safe_to_delete_rationale=rule["rationale"],
                    cache_layer=rule.get("cache_layer"),
                    cache_layer_family=rule.get("cache_layer_family"),
                )
                if candidate:
                    candidates.append(candidate)
                if len(candidates) >= max_items:
                    return candidates
    if "package-cache" in categories:
        for rule, root in generic_rule_roots(PACKAGE_CACHE_RULES, env):
            if not _matches_rule_filter(rule["rule_id"], allowed_rule_ids):
                continue
            candidate = candidate_for(
                root,
                category="package-cache",
                reason=f"{rule['owner']} package cache at {root}",
                rule_id=rule["rule_id"],
                cache_owner=rule["owner"],
                official_cleanup_command=rule["official_cleanup_command"],
                safe_to_delete_rationale=rule["rationale"],
                cache_layer=rule.get("cache_layer"),
                cache_layer_family=rule.get("cache_layer_family"),
            )
            if candidate:
                candidates.append(candidate)
            if len(candidates) >= max_items:
                return candidates
    if "browser-cache" in categories:
        browser_roots = generic_rule_roots(BROWSER_CACHE_RULES, env) + browser_profile_cache_roots(env)
        seen_browser_roots: set[str] = set()
        for rule, root in browser_roots:
            root_key = str(root.resolve(strict=False)).lower()
            if root_key in seen_browser_roots:
                continue
            seen_browser_roots.add(root_key)
            if not _matches_rule_filter(rule["rule_id"], allowed_rule_ids):
                continue
            candidate = candidate_for(
                root,
                category="browser-cache",
                reason=f"{rule['owner']} cache directory at {root}",
                rule_id=rule["rule_id"],
                cache_owner=rule["owner"],
                official_cleanup_command=rule["official_cleanup_command"],
                safe_to_delete_rationale=rule["rationale"],
                cache_layer=rule.get("cache_layer"),
                cache_layer_family=rule.get("cache_layer_family"),
            )
            if candidate:
                candidates.append(candidate)
            if len(candidates) >= max_items:
                return candidates
    if "app-leftovers" in categories:
        for app_rule, root in app_leftover_rule_roots(env):
            rule_id = str(app_rule["rule_id"])
            if not _matches_rule_filter(rule_id, allowed_rule_ids):
                continue
            candidate = candidate_for(
                root,
                category="app-leftovers",
                reason=f"{app_rule['owner']} uninstall leftover cache/log at {root}",
                rule_id=rule_id,
                cache_owner=str(app_rule["owner"]),
                official_cleanup_command=str(app_rule["official_cleanup_command"]),
                safe_to_delete_rationale=str(app_rule["rationale"]),
                cache_layer=str(app_rule.get("cache_layer") or ""),
                cache_layer_family=str(app_rule.get("cache_layer_family") or ""),
            )
            if candidate:
                candidates.append(candidate)
            if len(candidates) >= max_items:
                return candidates
    return candidates


def collect_findings(categories: list[str], *, env: dict[str, str] | None = None, rule_ids: list[str] | None = None) -> list[Finding]:
    env = env or dict(os.environ)
    findings: list[Finding] = []
    allowed_rule_ids = {item for item in (rule_ids or []) if item}
    if "registry-report" in categories:
        finding = Finding(
                category="registry-report",
                title="Registry cleanup is read-only in CleanWin MVP",
                detail="Registry keys are reported for human review only; automatic registry deletion is intentionally unavailable.",
                risk="high",
                rule_id="report.registry.read-only",
                owner="Windows Registry",
                official_cleanup_command="Use vendor uninstallers, Settings > Apps, or regedit after manual backup and review.",
                review_details=_review_details(
                    suggested_paths=[r"HKCU\\Software", r"HKLM\\Software"],
                    risk_notes=["Registry deletes are irreversible without backup.", "Shared keys may affect multiple apps or Windows features."],
                    manual_review_steps=["Export affected keys before any change.", "Prefer vendor uninstallers before regedit cleanup."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "startup-report" in categories:
        finding = Finding(
                category="startup-report",
                title="Startup changes are read-only in CleanWin MVP",
                detail="Run keys, startup folders, services, scheduled tasks, and policy-managed entries are not disabled automatically.",
                risk="medium",
                rule_id="report.startup.read-only",
                owner="Windows startup configuration",
                official_cleanup_command="Use Task Manager Startup Apps, Services, Task Scheduler, or vendor settings after manual review.",
                review_details=_review_details(
                    suggested_paths=[r"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup", r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"],
                    risk_notes=["Startup entries may be policy-managed or required for security tooling.", "Disabling services can change login, sync, or update behavior."],
                    manual_review_steps=["Review publisher and command target before disabling.", "Prefer Task Manager or vendor settings to disable startup items."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "windows-report" in categories:
        finding = Finding(
                category="windows-report",
                title="Windows component stores require official tools",
                detail="WinSxS, Installer, SoftwareDistribution, Defender, and Delivery Optimization paths are protected from direct deletion.",
                risk="high",
                rule_id="report.windows.official-tools",
                owner="Windows servicing",
                official_cleanup_command="Use Disk Cleanup, Storage Sense, DISM /Online /Cleanup-Image /StartComponentCleanup, or Windows Update UI.",
                review_details=_review_details(
                    suggested_paths=[r"C:\\Windows\\WinSxS", r"C:\\Windows\\SoftwareDistribution", r"C:\\ProgramData\\Microsoft\\Windows\\DeliveryOptimization"],
                    risk_notes=["Direct deletion can break servicing stack integrity.", "Windows may require these stores for rollback and repair."],
                    manual_review_steps=["Use DISM or Storage Sense instead of Explorer deletion.", "Verify pending Windows Update state before cleanup."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "large-files" in categories:
        finding = Finding(
                category="large-files",
                title="Large files are report-only",
                detail="Downloads, Documents, Desktop, OneDrive, and SharePoint roots are protected from automatic deletion.",
                risk="medium",
                rule_id="report.large-files.read-only",
                owner="User files",
                official_cleanup_command="Review in File Explorer or Storage Settings; do not bulk-delete automatically.",
                review_details=_review_details(
                    suggested_paths=[r"%USERPROFILE%\\Downloads", r"%USERPROFILE%\\Desktop", r"%USERPROFILE%\\OneDrive"],
                    risk_notes=["Large files often include user documents and synced content.", "Cloud-backed paths may rehydrate or trigger sync churn."],
                    manual_review_steps=["Sort by size in File Explorer.", "Confirm backup or sync state before removing files."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "docker-report" in categories:
        docker_local = env.get("LOCALAPPDATA")
        docker_paths = [r"%LOCALAPPDATA%\\Docker", r"%LOCALAPPDATA%\\Docker\\wsl", r"%LOCALAPPDATA%\\Docker\\log"]
        if docker_local:
            docker_paths = [str(Path(docker_local) / "Docker"), str(Path(docker_local) / "Docker" / "wsl"), str(Path(docker_local) / "Docker" / "log")]
        finding = Finding(
                category="docker-report",
                title="Docker cleanup is read-only",
                detail="Docker images, containers, volumes, BuildKit cache, and Docker Desktop WSL data are reported only because volumes may contain durable application data.",
                risk="high",
                rule_id="report.docker.manual-cleanup",
                owner="Docker Desktop",
                official_cleanup_command="docker system df; docker builder prune; docker system prune --volumes only after manual review",
                review_details=_review_details(
                    suggested_paths=docker_paths,
                    risk_notes=["Docker volumes may contain databases or local development state.", "Docker Desktop may store WSL disk images that should not be deleted directly."],
                    manual_review_steps=["Inspect disk usage with docker system df.", "Prune builder cache before considering image/container cleanup.", "Review named volumes before any docker system prune --volumes."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "wsl-report" in categories:
        wsl_local = env.get("LOCALAPPDATA")
        wsl_paths = [r"%LOCALAPPDATA%\\Packages", r"%USERPROFILE%\\AppData\\Local\\lxss"]
        if wsl_local:
            wsl_paths = [str(Path(wsl_local) / "Packages"), str(Path(wsl_local) / "lxss")]
        finding = Finding(
                category="wsl-report",
                title="WSL cleanup is read-only",
                detail="WSL distributions, ext4.vhdx files, package caches, and distro home directories are never cleaned by direct file deletion.",
                risk="high",
                rule_id="report.wsl.manual-cleanup",
                owner="WSL",
                official_cleanup_command="wsl --list --verbose; use distro package managers or wsl --unregister only after backup and review",
                review_details=_review_details(
                    suggested_paths=wsl_paths,
                    risk_notes=["ext4.vhdx files contain entire Linux filesystems.", "Manual file deletion can corrupt registered distros."],
                    manual_review_steps=["List distros with wsl --list --verbose.", "Clean package caches inside each distro first.", "Export or back up a distro before unregistering it."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "visual-studio-report" in categories:
        user_profile = env.get("USERPROFILE") or env.get("HOME")
        vs_paths = [r"%LOCALAPPDATA%\\Microsoft\\VisualStudio", r"%USERPROFILE%\\.nuget\\packages"]
        if user_profile:
            vs_paths[1] = str(Path(user_profile) / ".nuget" / "packages")
        finding = Finding(
                category="visual-studio-report",
                title="Visual Studio cleanup is read-only",
                detail="Visual Studio component caches, workloads, NuGet integration, and installer state are reported only; direct deletion can break repair and updates.",
                risk="medium",
                rule_id="report.visual-studio.official-tools",
                owner="Visual Studio",
                official_cleanup_command="Use Visual Studio Installer modify/repair and dotnet nuget locals all --clear for NuGet caches.",
                review_details=_review_details(
                    suggested_paths=vs_paths,
                    risk_notes=["Installer state is shared across workloads and SDKs.", "Deleting caches blindly can trigger repair loops or broken updates."],
                    manual_review_steps=["Use Visual Studio Installer to remove unused workloads.", "Clear NuGet caches with official dotnet or nuget commands first."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    if "browser-cache-report" in categories:
        local_app_data = env.get("LOCALAPPDATA")
        roaming_app_data = env.get("APPDATA")
        browser_paths = [r"%LOCALAPPDATA%\\Google\\Chrome\\User Data", r"%LOCALAPPDATA%\\Microsoft\\Edge\\User Data", r"%APPDATA%\\Mozilla\\Firefox\\Profiles"]
        if local_app_data:
            browser_paths[0] = str(Path(local_app_data) / "Google" / "Chrome" / "User Data")
            browser_paths[1] = str(Path(local_app_data) / "Microsoft" / "Edge" / "User Data")
        if roaming_app_data:
            browser_paths[2] = str(Path(roaming_app_data) / "Mozilla" / "Firefox" / "Profiles")
        finding = Finding(
                category="browser-cache-report",
                title="Browser cache cleanup is read-only",
                detail="Browser profiles include cache next to cookies, sessions, extension state, passwords, and synced data; CleanWin does not delete browser profile files directly.",
                risk="high",
                rule_id="report.browser-cache.in-app-cleanup",
                owner="Browsers",
                official_cleanup_command="Use each browser's Clear browsing data UI and keep passwords, cookies, sessions, and synced profile data under user control.",
                review_details=_review_details(
                    suggested_paths=browser_paths,
                    risk_notes=["Browser profiles mix cache with authentication sessions and extensions.", "Manual deletion can sign users out or corrupt profiles."],
                    manual_review_steps=["Use browser-native Clear browsing data controls.", "Prefer clearing cached images/files without removing passwords or cookies unless requested."],
                ),
            )
        if _matches_rule_filter(finding.rule_id, allowed_rule_ids):
            findings.append(finding)
    virtual_report_categories = {"browser-profile-inventory"}
    unknown = sorted(set(categories) - DEFAULT_SAFE_CATEGORIES - READ_ONLY_CATEGORIES - virtual_report_categories)
    for category in unknown:
        findings.append(
            Finding(
                category=category,
                title=f"Unknown category: {category}",
                detail="No collector is registered; no actions were planned.",
                risk="low",
            )
        )
    return findings
