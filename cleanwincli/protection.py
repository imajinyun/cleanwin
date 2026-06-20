"""CleanWin protection policy logic."""

from __future__ import annotations

from pathlib import Path

from cleanwincli import protection_data as data
from cleanwincli.paths import (
    contains_traversal,
    has_control_characters,
    is_absolute_path_text,
    looks_like_windows_path,
    normalize_windows_text,
    windows_parts,
)


def is_protected_registry_key(key: str) -> bool:
    normalized = normalize_windows_text(key).replace("\\\\", "\\")
    aliases = {
        "hkey_local_machine": "hklm",
        "hkey_current_user": "hkcu",
    }
    for long_name, short_name in aliases.items():
        if normalized.startswith(long_name + "\\"):
            normalized = short_name + normalized[len(long_name) :]
    return any(normalized == prefix or normalized.startswith(prefix + "\\") for prefix in data.PROTECTED_REGISTRY_PREFIXES)


def is_windows_system_path(path_text: str) -> bool:
    if not looks_like_windows_path(path_text):
        return False
    normalized = normalize_windows_text(path_text)
    if any(normalized == root or normalized.startswith(root + "\\") for root in data.PROTECTED_WINDOWS_ROOTS):
        return True
    return any(normalized.endswith(suffix) or f"{suffix}\\" in normalized for suffix in data.PROTECTED_ROOT_SUFFIXES)


def is_user_profile_root_or_known_data(path_text: str) -> bool:
    if not looks_like_windows_path(path_text):
        return False
    parts = windows_parts(path_text)
    if len(parts) < 3:
        return False
    try:
        users_idx = parts.index("users")
    except ValueError:
        return False
    rel = parts[users_idx + 2 :]
    if not rel:
        return True
    first = rel[0]
    return first in data.PROTECTED_USER_DIR_NAMES


def is_sensitive_user_data(path_text: str) -> bool:
    normalized = normalize_windows_text(path_text)
    if is_browser_cache_path_text(path_text):
        return False
    return any(segment in normalized for segment in data.SENSITIVE_USER_SEGMENTS)


def is_browser_cache_path_text(path_text: str) -> bool:
    normalized = normalize_windows_text(path_text)
    if any(normalized.endswith(suffix) for suffix in data.BROWSER_CACHE_ALLOWED_SUFFIXES):
        return True
    parts = list(windows_parts(path_text))
    for browser_parts in (("google", "chrome", "user data"), ("microsoft", "edge", "user data")):
        for index in range(0, len(parts) - 4):
            if tuple(parts[index : index + 3]) == browser_parts:
                cache_leaf = parts[index + 4]
                return cache_leaf in {"cache", "code cache"}
    for index in range(0, len(parts) - 4):
        if tuple(parts[index : index + 3]) == ("mozilla", "firefox", "profiles"):
            return parts[index + 4] == "cache2"
    return False


def validate_path_text(path_text: str) -> None:
    if path_text == "":
        raise RuntimeError("Refusing empty path")
    if has_control_characters(path_text):
        raise RuntimeError(f"Refusing path with control characters: {path_text!r}")
    if contains_traversal(path_text):
        raise RuntimeError(f"Refusing path with traversal component: {path_text}")
    if not is_absolute_path_text(path_text):
        raise RuntimeError(f"Refusing non-absolute path: {path_text}")
    if is_windows_system_path(path_text):
        raise RuntimeError(f"Refusing protected Windows system path: {path_text}")
    if is_user_profile_root_or_known_data(path_text):
        raise RuntimeError(f"Refusing protected user profile data path: {path_text}")
    if is_sensitive_user_data(path_text):
        raise RuntimeError(f"Refusing sensitive user data path: {path_text}")


def assert_not_reparse_or_symlink(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink/reparse-point candidate: {path}")
    if hasattr(path, "is_junction") and path.is_junction():  # pragma: no cover - Windows only on supported Python.
        raise RuntimeError(f"Refusing junction/reparse-point candidate: {path}")


def validate_filesystem_candidate(path: Path) -> None:
    validate_path_text(str(path))
    assert_not_reparse_or_symlink(path)
