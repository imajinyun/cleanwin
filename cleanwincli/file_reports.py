"""Read-only large-file and duplicate-file reporting."""

from __future__ import annotations

import hashlib
import os
import platform
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from cleanwincli.report_helpers import get_env

FILE_REPORT_SCHEMA = "cleanwin.file-report.v1"

DEFAULT_MIN_LARGE_FILE_BYTES = 100 * 1024 * 1024
DEFAULT_MIN_DUPLICATE_BYTES = 1024 * 1024
DEFAULT_MAX_FILES_SCANNED = 2000
DEFAULT_HASH_BYTES = 1024 * 1024
PROTECTED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "appdata",
    "node_modules",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
}


def _platform() -> dict[str, Any]:
    return {"os_name": os.name, "platform": platform.platform(), "is_windows": os.name == "nt"}


def _scan_roots(env: Mapping[str, str]) -> list[Path]:
    configured = env.get("CLEANWIN_FILE_REPORT_ROOTS")
    if configured:
        return [Path(item) for item in configured.split(os.pathsep) if item]
    user_profile = env.get("USERPROFILE") or env.get("HOME")
    if not user_profile:
        return []
    profile = Path(user_profile)
    roots = [profile / "Downloads", profile / "Desktop", profile / "Documents", profile / "Videos"]
    roots.extend(Path(value) for key, value in env.items() if key.upper().startswith("ONEDRIVE") and value)
    return roots


def _is_onedrive_path(path: Path, env: Mapping[str, str]) -> bool:
    lowered = str(path.resolve(strict=False)).lower()
    for key, value in env.items():
        if key.upper().startswith("ONEDRIVE") and value:
            root = str(Path(value).resolve(strict=False)).lower()
            if lowered == root or lowered.startswith(root + os.sep):
                return True
    return "onedrive" in {part.lower() for part in path.parts}


def _iter_files(roots: Iterable[Path], *, max_files: int) -> tuple[list[Path], dict[str, Any]]:
    files: list[Path] = []
    skipped_roots: list[str] = []
    skipped_dirs: list[str] = []
    for root in roots:
        if len(files) >= max_files:
            break
        if not root.exists() or not root.is_dir() or root.is_symlink():
            skipped_roots.append(str(root))
            continue
        for current_root, dir_names, file_names in os.walk(root):
            current = Path(current_root)
            if current.is_symlink():
                skipped_dirs.append(str(current))
                dir_names[:] = []
                continue
            dir_names[:] = [
                name
                for name in dir_names
                if name.lower() not in PROTECTED_DIR_NAMES and not (current / name).is_symlink()
            ]
            for file_name in sorted(file_names):
                candidate = current / file_name
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                files.append(candidate)
                if len(files) >= max_files:
                    return files, {"max_files": max_files, "limit_reached": True, "skipped_roots": skipped_roots, "skipped_dirs": skipped_dirs}
    return files, {"max_files": max_files, "limit_reached": False, "skipped_roots": skipped_roots, "skipped_dirs": skipped_dirs}


def _hash_file(path: Path, *, hash_bytes: int) -> str | None:
    digest = hashlib.sha256()
    remaining = hash_bytes
    try:
        with path.open("rb") as file:
            while remaining > 0:
                chunk = file.read(min(65536, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _file_record(path: Path, *, env: Mapping[str, str]) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return {
        "path": str(path),
        "name": path.name,
        "extension": path.suffix.lower() or "<none>",
        "size_bytes": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
        "onedrive_or_cloud_path": _is_onedrive_path(path, env),
        "safe_to_execute": False,
        "review_required": True,
    }


def file_report(
    *,
    env: Mapping[str, str] | None = None,
    min_large_file_bytes: int = DEFAULT_MIN_LARGE_FILE_BYTES,
    min_duplicate_bytes: int = DEFAULT_MIN_DUPLICATE_BYTES,
    max_files_scanned: int = DEFAULT_MAX_FILES_SCANNED,
    hash_bytes: int = DEFAULT_HASH_BYTES,
) -> dict[str, Any]:
    current_env = get_env(env)
    roots = _scan_roots(current_env)
    files, budget = _iter_files(roots, max_files=max_files_scanned)
    records = [record for record in (_file_record(path, env=current_env) for path in files) if record is not None]
    large_files = sorted(
        [record for record in records if int(record["size_bytes"]) >= min_large_file_bytes],
        key=lambda record: (-int(record["size_bytes"]), str(record["path"]).lower()),
    )
    extension_groups: dict[str, dict[str, Any]] = {}
    for record in records:
        extension = str(record["extension"])
        group = extension_groups.setdefault(extension, {"extension": extension, "file_count": 0, "total_bytes": 0})
        group["file_count"] += 1
        group["total_bytes"] += int(record["size_bytes"])

    size_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        size = int(record["size_bytes"])
        if size >= min_duplicate_bytes:
            size_groups[size].append(record)
    duplicate_groups: list[dict[str, Any]] = []
    for size, candidates in sorted(size_groups.items()):
        if len(candidates) < 2:
            continue
        hash_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            digest = _hash_file(Path(str(candidate["path"])), hash_bytes=hash_bytes)
            if digest:
                hash_groups[digest].append(candidate)
        for digest, duplicates in sorted(hash_groups.items()):
            if len(duplicates) < 2:
                continue
            duplicate_groups.append(
                {
                    "digest": digest,
                    "hash_scope": f"first-{hash_bytes}-bytes",
                    "size_bytes": size,
                    "file_count": len(duplicates),
                    "potential_reclaimable_bytes": size * (len(duplicates) - 1),
                    "files": sorted(duplicates, key=lambda item: str(item["path"]).lower()),
                    "safe_to_execute": False,
                    "review_required": True,
                }
            )
    duplicate_groups.sort(key=lambda group: (-int(group["potential_reclaimable_bytes"]), str(group["digest"])))
    return {
        "schema": FILE_REPORT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": _platform(),
        "scan_roots": [str(root) for root in roots],
        "traversal_budget": budget,
        "large_files": large_files,
        "duplicate_groups": duplicate_groups,
        "extension_groups": sorted(extension_groups.values(), key=lambda item: (-int(item["total_bytes"]), str(item["extension"]))),
        "summary": {
            "file_count": len(records),
            "bytes_scanned": sum(int(record["size_bytes"]) for record in records),
            "large_file_count": len(large_files),
            "duplicate_group_count": len(duplicate_groups),
            "potential_duplicate_reclaimable_bytes": sum(int(group["potential_reclaimable_bytes"]) for group in duplicate_groups),
            "onedrive_or_cloud_file_count": sum(1 for record in records if record["onedrive_or_cloud_path"]),
        },
        "execution_gate": {
            "file_execution_enabled": False,
            "requires_human_review": True,
            "requires_backup_or_cloud_sync_review": True,
            "requires_exact_file_identity": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not delete large files.",
            "This report does not delete duplicate files.",
            "This report does not traverse protected system, application, or dependency directories.",
        ],
    }
