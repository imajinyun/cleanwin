"""AI schema registry and plan schema negotiation for cleanwin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchemaEntry:
    name: str
    version: int
    module: str
    stability: str
    kind: str
    producer: str
    consumers: tuple[str, ...]
    latest: bool


_REGISTRY: tuple[tuple[str, int, str, str, str, str, tuple[str, ...]], ...] = (
    ("cleanwin.plan.v1", 1, "cleanwincli.models", "stable", "contract", "cleanwin", ("cli", "ai-host", "mcp")),
    ("cleanwin.inspect.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.execute.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.review.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp")),
    ("cleanwin.error.v1", 1, "cleanwincli.cli", "stable", "error", "cleanwin", ("cli", "ai-host", "mcp")),
    ("cleanwin.validate-plan.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.doctor.v1", 1, "cleanwincli.core", "stable", "report", "cleanwin", ("cli", "ai-host", "mcp", "ci")),
    ("cleanwin.filesystem-identity.v1", 1, "cleanwincli.identity", "stable", "contract", "cleanwin", ("cli", "ai-host")),
    ("cleanwin.ai-tools.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-openai-functions.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("openai" ,)),
    ("cleanwin.ai-anthropic-tools.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("anthropic",)),
    ("cleanwin.ai-provider-export-parity.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host",)),
    ("cleanwin.ai-schema-validation.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-tool-argument-validation.v1", 1, "cleanwincli.ai_schema", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-host-policy.v1", 1, "cleanwincli.ai_host_policy", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-host-policy-validation.v1", 1, "cleanwincli.ai_host_policy", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-host-tool-call-decision.v1", 1, "cleanwincli.ai_host_policy", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.ai-policy-simulation.v1", 1, "cleanwincli.core", "stable", "ai", "cleanwin", ("ai-host", "cli")),
    ("cleanwin.ai-schema-registry.v1", 1, "cleanwincli.ai_versioning", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-readiness.v1", 1, "cleanwincli.ai_readiness", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.ai-readiness-validation.v1", 1, "cleanwincli.ai_readiness", "stable", "ai", "cleanwin", ("ai-host", "ci")),
    ("cleanwin.ai-self-test.v1", 1, "cleanwincli.ai_self_test", "stable", "ai", "cleanwin", ("ai-host", "mcp", "ci")),
    ("cleanwin.ai-runbook.v1", 1, "cleanwincli.ai_runbook", "stable", "ai", "cleanwin", ("ai-host", "mcp")),
    ("cleanwin.mcp-tool-error.v1", 1, "cleanwincli.mcp_server", "stable", "mcp", "cleanwin", ("mcp",)),
    ("cleanwin.mcp-text-output.v1", 1, "cleanwincli.mcp_server", "stable", "mcp", "cleanwin", ("mcp",)),
)

LATEST_PLAN_SCHEMA = "cleanwin.plan.v1"
SUPPORTED_PLAN_SCHEMAS: tuple[str, ...] = (LATEST_PLAN_SCHEMA,)


def schema_registry() -> dict[str, Any]:
    entries = [
        {
            "name": name,
            "version": version,
            "module": module,
            "stability": stability,
            "kind": kind,
            "producer": producer,
            "consumers": list(consumers),
            "latest": True,
        }
        for name, version, module, stability, kind, producer, consumers in _REGISTRY
    ]
    samples = {}
    for entry in entries:
        sample = schema_sample(str(entry["name"]))
        if sample is not None:
            samples[entry["name"]] = sample
    return {
        "schema": "cleanwin.ai-schema-registry.v1",
        "latest_plan_schema": LATEST_PLAN_SCHEMA,
        "supported_plan_schemas": list(SUPPORTED_PLAN_SCHEMAS),
        "schema_count": len(entries),
        "entries": entries,
        "samples": samples,
    }


def _sample_identity() -> dict[str, Any]:
    return {
        "schema": "cleanwin.filesystem-identity.v1",
        "path": r"C:\\Users\\tester\\AppData\\Local\\npm-cache\\_cacache",
        "canonical_path": r"C:\\Users\\tester\\AppData\\Local\\npm-cache\\_cacache",
        "platform_os_name": "nt",
        "source": "python-stdlib-stat+windows-native",
        "exists": True,
        "file_type": "directory",
        "is_symlink": False,
        "is_junction": False,
        "size_bytes": 1024,
        "modified_ns": 1710000000000000000,
        "device": 1234,
        "file_id": 5678,
        "mode": 16895,
        "windows_file_attributes": 16,
        "windows_reparse_tag": None,
        "owner_sid": "S-1-5-21-example",
    }


def _sample_candidate() -> dict[str, Any]:
    return {
        "path": r"C:\\Users\\tester\\AppData\\Local\\npm-cache\\_cacache",
        "category": "dev-cache",
        "size_bytes": 1024,
        "reason": r"npm cache entry under C:\\Users\\tester\\AppData\\Local\\npm-cache",
        "safe_to_delete": True,
        "delete_mode": "recycle",
        "requires_admin": False,
        "risk": "low",
        "discovered_by": "collector",
        "modified_at": "2026-06-20T00:00:00+00:00",
        "identity": _sample_identity(),
        "rule_id": "dev-cache.npm.cache",
        "cache_owner": "npm",
        "official_cleanup_command": "npm cache clean --force",
        "safe_to_delete_rationale": "npm content-addressed cache entries are verified package artifacts that can be regenerated by npm.",
    }


def _sample_package_candidate() -> dict[str, Any]:
    candidate = _sample_candidate()
    candidate.update(
        {
            "path": r"C:\Users\tester\AppData\Local\Microsoft\WinGet\Packages",
            "category": "package-cache",
            "reason": r"WinGet package cache at C:\Users\tester\AppData\Local\Microsoft\WinGet\Packages",
            "rule_id": "package-cache.winget.packages",
            "cache_owner": "WinGet",
            "official_cleanup_command": "winget source reset --force or remove stale installer payloads only after review",
            "safe_to_delete_rationale": "WinGet package download payloads are installer artifacts that can be re-downloaded by winget.",
        }
    )
    return candidate


def _sample_browser_candidate() -> dict[str, Any]:
    candidate = _sample_candidate()
    candidate.update(
        {
            "path": r"C:\Users\tester\AppData\Local\Google\Chrome\User Data\Default\Cache",
            "category": "browser-cache",
            "reason": r"Google Chrome cache directory at C:\Users\tester\AppData\Local\Google\Chrome\User Data\Default\Cache",
            "rule_id": "browser-cache.chrome.default.cache",
            "cache_owner": "Google Chrome",
            "official_cleanup_command": "Use Chrome > Clear browsing data and clear cached images/files only.",
            "safe_to_delete_rationale": "Chrome Cache directory stores temporary web resources separate from Cookies, Login Data, and profile databases.",
        }
    )
    return candidate


def _sample_app_leftover_candidate() -> dict[str, Any]:
    candidate = _sample_candidate()
    candidate.update(
        {
            "path": r"C:\Users\tester\AppData\Roaming\Code\CachedData",
            "category": "app-leftovers",
            "reason": r"Visual Studio Code uninstall leftover cache/log at C:\Users\tester\AppData\Roaming\Code\CachedData",
            "rule_id": "app-leftovers.vscode.cached-data",
            "cache_owner": "Visual Studio Code",
            "official_cleanup_command": "Uninstall Visual Studio Code from Settings > Apps, then remove reviewed Code cache/log leftovers.",
            "safe_to_delete_rationale": "VS Code CachedData contains regenerated extension host and workbench cache artifacts, not user projects or settings.",
        }
    )
    return candidate


def _sample_finding() -> dict[str, Any]:
    return {
        "category": "docker-report",
        "title": "Docker cleanup is read-only",
        "detail": "Docker images, containers, volumes, BuildKit cache, and Docker Desktop WSL data are reported only.",
        "risk": "high",
        "safe_to_execute": False,
        "rule_id": "report.docker.manual-cleanup",
        "owner": "Docker Desktop",
        "official_cleanup_command": "docker system df; docker builder prune; docker system prune --volumes only after manual review",
        "review_details": {
            "suggested_paths": [r"%LOCALAPPDATA%\\Docker", r"%LOCALAPPDATA%\\Docker\\wsl"],
            "risk_notes": ["Docker volumes may contain databases or local development state."],
            "manual_review_steps": ["Inspect disk usage with docker system df before pruning."],
        },
    }


def schema_sample(schema_name: str) -> dict[str, Any] | None:
    if schema_name == "cleanwin.inspect.v1":
        return {
            "schema": "cleanwin.inspect.v1",
            "categories": ["dev-cache", "package-cache", "browser-cache", "app-leftovers", "docker-report"],
            "filters": {"rule_ids": ["dev-cache.npm.cache", "package-cache.winget.packages", "browser-cache.chrome.default.cache", "app-leftovers.vscode.cached-data", "report.docker.manual-cleanup"]},
            "candidates": [_sample_candidate(), _sample_package_candidate(), _sample_browser_candidate(), _sample_app_leftover_candidate()],
            "findings": [_sample_finding()],
            "summary": {"candidate_count": 4, "finding_count": 1, "bytes_reclaimable": 4096},
        }
    if schema_name == "cleanwin.plan.v1":
        return {
            "schema": "cleanwin.plan.v1",
            "categories": ["dev-cache"],
            "context": {
                "hostname": "TEST-WIN",
                "platform": "Windows-11",
                "os_name": "nt",
                "user": "tester",
                "home": r"C:\\Users\\tester",
            },
            "candidates": [_sample_candidate()],
            "created_at": "2026-06-20T00:00:00+00:00",
            "source_fingerprint": "0" * 64,
            "summary": {"candidate_count": 1, "safe_candidate_count": 1, "bytes_reclaimable": 1024},
        }
    if schema_name == "cleanwin.execute.v1":
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "dry_run": True,
            "validation": {"schema": "cleanwin.validate-plan.v1", "valid": True, "errors": [], "candidate_count": 1},
            "results": [
                {
                    "status": "dry-run",
                    "path": r"C:\Users\tester\AppData\Local\npm-cache\_cacache",
                    "mode": "recycle",
                }
            ],
            "summary": {"result_count": 1, "status_counts": {"dry-run": 1}},
            "confirmation": {
                "schema": "cleanwin.ai-confirmation-summary.v1",
                "required_phrase": "确认执行 cleanwin 清理",
                "confirmation_token": "1" * 64,
                "delete_mode": "recycle",
            },
        }
    if schema_name == "cleanwin.ai-tool-argument-validation.v1":
        return {
            "schema": "cleanwin.ai-tool-argument-validation.v1",
            "tool": "cleanwin_review_plan",
            "valid": False,
            "violation_count": 1,
            "violations": ["arguments.plan_file is required"],
        }
    if schema_name == "cleanwin.review.v1":
        return {
            "schema": "cleanwin.review.v1",
            "destructive": False,
            "plan_schema": "cleanwin.plan.v1",
            "plan_source_fingerprint": "0" * 64,
            "validation": {"schema": "cleanwin.validate-plan.v1", "valid": True, "errors": [], "candidate_count": 1},
            "summary": {"candidate_count": 1, "safe_candidate_count": 1, "bytes_reclaimable": 1024},
            "category_counts": [{"category": "dev-cache", "candidate_count": 1}],
            "risk_summary": [{"risk": "low", "candidate_count": 1}],
            "rule_ids": ["dev-cache.npm.cache"],
            "rule_summary": [
                {
                    "rule_id": "dev-cache.npm.cache",
                    "cache_owner": "npm",
                    "candidate_count": 1,
                    "bytes_reclaimable": 1024,
                    "official_cleanup_command": "npm cache clean --force",
                }
            ],
            "official_cleanup_commands": ["npm cache clean --force"],
            "cleanup_strategy": {
                "preferred": "official-cli-command",
                "fallback": "cleanwin-recycle-execution",
                "requires_review": True,
                "official_cleanup_commands": ["npm cache clean --force"],
            },
            "manual_only_categories": [],
            "sensitive_exclusions": [],
            "execution_handoff": {
                "safe_to_execute": True,
                "requires_human_confirmation": True,
                "requires_matching_dry_run_token": True,
                "requires_plan_context": True,
                "required_predecessor_tools": ["cleanwin_validate_plan", "cleanwin_policy_simulate", "cleanwin_dry_run_plan", "cleanwin_execute_plan"],
                "blocked_reasons": [],
            },
        }
    if schema_name == "cleanwin.filesystem-identity.v1":
        return _sample_identity()
    if schema_name == "cleanwin.doctor.v1":
        return {
            "schema": "cleanwin.doctor.v1",
            "destructive": False,
            "dry_run": True,
            "ready": True,
            "failed_check_ids": [],
            "check_count": 4,
            "passed_count": 4,
            "checks": [
                {
                    "id": "single_destructive_exit",
                    "passed": True,
                    "detail": "All destructive cleanup must route through cleanwincli.delete_ops.safe_delete.",
                    "evidence": {"deletion_exit": "cleanwincli.delete_ops.safe_delete"},
                },
                {
                    "id": "delete_primitives_owned_by_delete_ops",
                    "passed": True,
                    "detail": "Low-level delete/move primitives must not appear outside cleanwincli.delete_ops.",
                    "evidence": {"violations": []},
                },
                {
                    "id": "ai_contracts_valid",
                    "passed": True,
                    "detail": "AI tool schema and provider parity must validate.",
                    "evidence": {"violation_count": 0},
                },
                {
                    "id": "version_consistency",
                    "passed": True,
                    "detail": "Package metadata, cleanwincli.__version__, and capabilities version must stay in sync.",
                    "evidence": {"pyproject_version": "0.1.0", "package_version": "0.1.0", "capabilities_version": "0.1.0"},
                },
            ],
            "recommended_commands": [
                ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
                ["python3", "cleanwin.py", "--json", "doctor"],
                ["make", "version-smoke"],
            ],
        }
    return None


def negotiate_plan_schema(requested: str | None) -> dict[str, Any]:
    if not requested:
        requested = LATEST_PLAN_SCHEMA
    accepted = requested in SUPPORTED_PLAN_SCHEMAS
    return {
        "schema": "cleanwin.validate-plan.v1",
        "requested_schema": requested,
        "accepted": accepted,
        "selected_schema": requested if accepted else None,
        "supported_plan_schemas": list(SUPPORTED_PLAN_SCHEMAS),
        "error": None if accepted else f"Unsupported plan schema: {requested}",
    }
