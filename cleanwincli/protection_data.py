"""Windows protection policy data for CleanWin.

This module intentionally contains data only. Policy logic lives in
`cleanwincli.protection` and destructive operations live in
`cleanwincli.delete_ops`.
"""

from __future__ import annotations

READ_ONLY_CATEGORIES = frozenset(
    {
        "registry-report",
        "startup-report",
        "windows-report",
        "large-files",
        "docker-report",
        "wsl-report",
        "visual-studio-report",
        "browser-cache-report",
    }
)

DEFAULT_SAFE_CATEGORIES = frozenset({"temp", "dev-cache", "package-cache", "browser-cache"})

HIGH_RISK_CATEGORIES = frozenset({"recycle-bin", "startup-disable", "registry-clean"})

PROTECTED_WINDOWS_ROOTS = (
    "c:\\",
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\programdata",
    "c:\\programdata\\microsoft",
    "c:\\users",
)

PROTECTED_ROOT_SUFFIXES = (
    r"\windows",
    r"\program files",
    r"\program files (x86)",
    r"\programdata\microsoft",
)

PROTECTED_USER_DIR_NAMES = frozenset(
    {
        "desktop",
        "documents",
        "downloads",
        "music",
        "pictures",
        "videos",
        "onedrive",
        "sharepoint",
    }
)

SENSITIVE_USER_SEGMENTS = frozenset(
    {
        ".ssh",
        ".gnupg",
        "appdata\\roaming\\microsoft\\credentials",
        "appdata\\roaming\\microsoft\\protect",
        "appdata\\roaming\\microsoft\\systemcertificates",
        "appdata\\local\\microsoft\\credentials",
        "appdata\\local\\microsoft\\vault",
        "appdata\\local\\microsoft\\edge\\user data",
        "appdata\\local\\google\\chrome\\user data",
        "appdata\\roaming\\mozilla\\firefox\\profiles",
        "appdata\\local\\packages\\microsoft.windowscommunicationsapps",
        "appdata\\local\\packages\\microsoft.microsoftedge",
        "appdata\\local\\packages\\microsoft.windowsstore",
        "appdata\\local\\docker\\wsl",
        "appdata\\local\\docker\\volumes",
        "appdata\\local\\packages\\canonicalgrouplimited",
    }
)

BROWSER_CACHE_ALLOWED_SUFFIXES = frozenset(
    {
        r"\user data\default\cache",
        r"\user data\default\code cache",
        r"\user data\profile 1\cache",
        r"\user data\profile 1\code cache",
        r"\profiles\default-release\cache2",
    }
)

PROTECTED_REGISTRY_PREFIXES = (
    r"hklm\system",
    r"hklm\software\microsoft\windows",
    r"hklm\software\classes",
    r"hklm\software\microsoft\windows defender",
    r"hklm\software\policies",
    r"hklm\software\microsoft\enterprise",
    r"hkcu\software\microsoft\windows",
    r"hkcu\software\policies",
)

DEV_CACHE_ENV_KEYS = (
    "PIP_CACHE_DIR",
    "NPM_CONFIG_CACHE",
    "YARN_CACHE_FOLDER",
    "PNPM_HOME",
    "GOMODCACHE",
    "GOCACHE",
    "CARGO_HOME",
    "NUGET_PACKAGES",
    "GRADLE_USER_HOME",
    "MAVEN_OPTS",
)
