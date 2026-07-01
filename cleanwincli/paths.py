"""Path normalization helpers shared by CleanWin safety checks."""

from __future__ import annotations

import os
import re
from pathlib import Path, PureWindowsPath

from cleanwincli.report_helpers import get_env

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def has_control_characters(value: str) -> bool:
    return bool(CONTROL_CHARS_RE.search(value))


def expand_environment_path(value: str, env: dict[str, str] | None = None) -> str:
    env = get_env(env)
    expanded = value
    for key, replacement in env.items():
        expanded = expanded.replace(f"%{key}%", replacement)
    return os.path.expandvars(expanded)


def looks_like_windows_path(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z]:[\\/]", value)) or value.startswith(("\\\\", "//", "\\\\?\\"))


def normalize_windows_text(value: str) -> str:
    text = value.strip().replace("/", "\\")
    if text.startswith("\\\\?\\"):
        text = text[4:]
    while "\\\\" in text and not text.startswith("\\\\"):
        text = text.replace("\\\\", "\\")
    return text.rstrip("\\").lower() if len(text) > 3 else text.lower()


def windows_parts(value: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PureWindowsPath(value).parts if part not in {"\\", "/"})


def contains_traversal(value: str) -> bool:
    if ".." in Path(value).parts:
        return True
    return ".." in PureWindowsPath(value).parts


def is_absolute_path_text(value: str) -> bool:
    if looks_like_windows_path(value):
        return PureWindowsPath(value).is_absolute()
    return Path(value).is_absolute()


def canonical_host_path(path: Path) -> Path:
    return path.resolve(strict=False)


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
