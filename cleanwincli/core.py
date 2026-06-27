"""CleanWin orchestration for inspect, plan, validation, and execution."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from cleanwincli import __version__
from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call, render_ai_host_policy, validate_ai_host_policy
from cleanwincli.ai_readiness import ai_readiness_report, validate_ai_readiness
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_schema import (
    AI_TOOL_DEFINITIONS,
    CONFIRMATION_PHRASE,
    DEFAULT_OPERATION_LOG,
    anthropic_tools_export,
    openai_functions_export,
    provider_export_parity,
    tool_catalog,
    validate_ai_schema,
)
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.ai_versioning import negotiate_plan_schema, schema_registry
from cleanwincli.browser_inventory import browser_profile_inventory_report
from cleanwincli.collectors import collect_candidates, collect_findings
from cleanwincli.debloat_privacy import debloat_privacy_report
from cleanwincli.delete_ops import safe_delete
from cleanwincli.environment_index import environment_index_report
from cleanwincli.execution_contracts import (
    backup_delete_contract_report,
    disable_revert_contract_report,
    permanent_delete_denial_report,
)
from cleanwincli.external_rules import translate_external_rules_file
from cleanwincli.file_reports import file_report
from cleanwincli.identity import capture_filesystem_identity, compare_identity
from cleanwincli.installed_apps import installed_app_inventory_report
from cleanwincli.models import PLAN_SCHEMA, HostContext, Plan, plan_from_dict
from cleanwincli.official_commands import official_command_plan_report
from cleanwincli.presets import preset_catalog_report
from cleanwincli.promotion_gates import promotion_gates_report
from cleanwincli.protection import validate_filesystem_candidate
from cleanwincli.recovery import recovery_readiness_report
from cleanwincli.scan_governance import scan_governance_report
from cleanwincli.startup_inventory import startup_service_inventory_report
from cleanwincli.system_health import system_health_report
from cleanwincli.windows_inventory import windows_inventory_report
from cleanwincli.windows_native_artifacts import windows_native_artifacts_report
from cleanwincli.windows_smoke import windows_smoke_matrix_report
from cleanwincli.workflow_artifacts import workflow_decision_report, workflow_trace_report
from cleanwincli.workflow_router import workflow_router_report


def capabilities() -> dict[str, Any]:
    return {
        "tool": "cleanwin",
        "version": __version__,
        "default_dry_run": True,
        "plan_schema": PLAN_SCHEMA,
        "execution_requires_execute_flag": True,
        "deletion_exit": "cleanwincli.delete_ops.safe_delete",
        "default_delete_mode": "recycle",
        "fail_closed": [
            "non-windows recycle execution without CLEANWIN_TEST_MODE",
            "symlink or junction candidates",
            "protected Windows paths",
            "protected user data paths",
            "operation log write failures",
        ],
        "safe_categories": ["app-leftovers", "browser-cache", "dev-cache", "package-cache", "temp"],
        "read_only_categories": [
            "browser-cache-report",
            "backup-delete-contract",
            "browser-profile-inventory",
            "docker-report",
            "file-report",
            "large-files",
            "permanent-delete-denial",
            "registry-report",
            "scan-governance",
            "startup-report",
            "system-health-report",
            "disable-revert-contract",
            "visual-studio-report",
            "windows-inventory",
            "windows-report",
            "wsl-report",
        ],
        "never_auto_execute": ["registry-clean", "startup-disable", "windows-component-clean"],
        "promotion_gates_schema": "cleanwin.promotion-gates.v1",
        "ai": {
            "tool_catalog_schema": "cleanwin.ai-tools.v1",
            "workflow_router_schema": "cleanwin.workflow-router.v1",
            "host_policy_schema": "cleanwin.ai-host-policy.v1",
            "destructive_tool": "cleanwin_execute_plan",
            "confirmation_phrase": CONFIRMATION_PHRASE,
        },
    }


def inspect(categories: list[str], *, older_than_days: int, max_items: int, rule_ids: list[str] | None = None) -> dict[str, Any]:
    candidates = collect_candidates(categories, older_than_days_value=older_than_days, max_items=max_items, rule_ids=rule_ids)
    findings = collect_findings(categories, rule_ids=rule_ids)
    return {
        "schema": "cleanwin.inspect.v1",
        "categories": categories,
        "filters": {"rule_ids": rule_ids or []},
        "candidates": [candidate.to_dict() for candidate in candidates],
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "candidate_count": len(candidates),
            "finding_count": len(findings),
            "bytes_reclaimable": sum(candidate.size_bytes for candidate in candidates if candidate.safe_to_delete),
        },
    }


def build_plan(categories: list[str], *, older_than_days: int, max_items: int, rule_ids: list[str] | None = None) -> Plan:
    candidates = collect_candidates(categories, older_than_days_value=older_than_days, max_items=max_items, rule_ids=rule_ids)
    return Plan(candidates=candidates, categories=categories)


def load_plan(path: Path) -> tuple[Plan, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    plan = plan_from_dict(raw)
    return plan, raw


def validate_plan_payload(plan: Plan, raw: dict[str, Any], *, require_context: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    negotiation = negotiate_plan_schema(str(raw.get("schema") or ""))
    if raw.get("schema") != PLAN_SCHEMA:
        errors.append(f"Unsupported plan schema: {raw.get('schema')}")
    expected_fingerprint = plan.source_fingerprint()
    if raw.get("source_fingerprint") != expected_fingerprint:
        errors.append("Plan source_fingerprint does not match current payload")
    if require_context:
        current = HostContext.current()
        raw_context = plan.context
        if raw_context.home and raw_context.home != current.home:
            errors.append("Plan home context does not match current user home")
        if raw_context.user and raw_context.user != current.user:
            errors.append("Plan user context does not match current user")
    for candidate in plan.candidates:
        if not candidate.safe_to_delete:
            errors.append(f"Candidate is not marked safe_to_delete: {candidate.path}")
            continue
        if candidate.delete_mode != "recycle":
            errors.append(f"Unsupported plan delete_mode for MVP: {candidate.path} uses {candidate.delete_mode}")
            continue
        if candidate.requires_admin:
            errors.append(f"Admin-scoped candidate is not executable in MVP: {candidate.path}")
            continue
        try:
            candidate_path = Path(candidate.path)
            validate_filesystem_candidate(candidate_path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        current_identity = capture_filesystem_identity(candidate_path)
        identity_mismatches = compare_identity(candidate.identity, current_identity)
        if identity_mismatches:
            errors.append(f"Filesystem identity mismatch for {candidate.path}: {'; '.join(identity_mismatches)}")
    return {
        "schema": "cleanwin.validate-plan.v1",
        "valid": not errors,
        "errors": errors,
        "candidate_count": len(plan.candidates),
        "plan_schema": negotiation,
    }


def confirmation_token_for_plan(plan: Plan, raw_payload: dict[str, Any]) -> str:
    fingerprint = str(raw_payload.get("source_fingerprint") or plan.source_fingerprint())
    token_context = {
        "schema": "cleanwin.ai-confirmation-token-context.v1",
        "plan_fingerprint": fingerprint,
        "delete_mode": "recycle",
        "candidate_count": len(plan.candidates),
        "categories": plan.categories,
    }
    encoded = json.dumps(token_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def execution_result_summary(results: list[dict[str, str]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {"result_count": len(results), "status_counts": dict(sorted(status_counts.items()))}


def execute_plan(
    plan: Plan,
    *,
    execute: bool,
    yes: bool,
    require_context: bool,
    raw_payload: dict[str, Any],
    operation_log: Path | None,
    trash_root: Path | None,
    confirmation_phrase: str | None = None,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    validation = validate_plan_payload(plan, raw_payload, require_context=require_context)
    if not validation["valid"]:
        return {"schema": "cleanwin.execute.v1", "executed": False, "validation": validation, "results": []}
    if not execute:
        results = [
            safe_delete(
                candidate.path,
                dry_run=True,
                mode=candidate.delete_mode,
                allow_permanent=False,
                trash_root=trash_root,
                operation_log=None,
                expected_identity=candidate.identity,
            )
            for candidate in plan.candidates
        ]
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "dry_run": True,
            "validation": validation,
            "results": results,
            "summary": execution_result_summary(results),
            "confirmation": {
                "schema": "cleanwin.ai-confirmation-summary.v1",
                "required_phrase": CONFIRMATION_PHRASE,
                "confirmation_token": confirmation_token_for_plan(plan, raw_payload),
                "delete_mode": "recycle",
            },
        }
    if not yes:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires --yes",
        }
    if operation_log is None:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires --operation-log",
        }
    if confirmation_phrase != CONFIRMATION_PHRASE:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires exact confirmation phrase",
        }
    expected_token = confirmation_token_for_plan(plan, raw_payload)
    if confirmation_token != expected_token:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires matching dry-run confirmation token",
        }
    results = []
    for candidate in plan.candidates:
        results.append(
            safe_delete(
                candidate.path,
                dry_run=False,
                mode=candidate.delete_mode,
                allow_permanent=False,
                trash_root=trash_root,
                operation_log=operation_log,
                expected_identity=candidate.identity,
            )
        )
    return {"schema": "cleanwin.execute.v1", "executed": True, "validation": validation, "results": results, "summary": execution_result_summary(results)}


def _doctor_check(check_id: str, passed: bool, detail: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": check_id, "passed": passed, "detail": detail, "evidence": evidence or {}}


def _pyproject_project_version(project_root: Path) -> str | None:
    in_project_section = False
    try:
        lines = (project_root / "pyproject.toml").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project_section = line == "[project]"
            continue
        if in_project_section and line.startswith("version") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"')
    return None


def _installed_distribution_version() -> str | None:
    try:
        return importlib.metadata.version("cleanwin")
    except importlib.metadata.PackageNotFoundError:
        return None


def _delete_primitive_violations() -> list[dict[str, Any]]:
    project_root = Path(__file__).resolve().parents[1]
    allowed = {str((project_root / "cleanwincli" / "delete_ops.py").resolve())}
    forbidden = (
        "shutil." + "rmtree(",
        "shutil." + "move(",
        "." + "unlink(",
        "os." + "remove(",
        "os." + "unlink(",
        "os." + "rmdir(",
        "SHFile" + "Operation",
    )
    violations: list[dict[str, Any]] = []
    for source in sorted((project_root / "cleanwincli").glob("*.py")) + [project_root / "cleanwin.py"]:
        if str(source.resolve()) in allowed:
            continue
        try:
            lines = source.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            violations.append({"file": str(source.relative_to(project_root)), "line": 0, "pattern": "read-error", "detail": str(exc)})
            continue
        for line_number, line in enumerate(lines, start=1):
            for pattern in forbidden:
                if pattern in line:
                    violations.append({"file": str(source.relative_to(project_root)), "line": line_number, "pattern": pattern})
    return violations


def doctor_report() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[1]
    capabilities_report = capabilities()
    pyproject_version = _pyproject_project_version(project_root)
    distribution_version = _installed_distribution_version()
    catalog = tool_catalog()
    schema_validation = validate_ai_schema()
    policy = render_ai_host_policy(tool_catalog=catalog)
    policy_validation = validate_ai_host_policy(policy)
    registry = schema_registry()
    registry_names = {str(entry.get("name")) for entry in registry.get("entries", []) if isinstance(entry, dict)}
    registry_samples = registry.get("samples", {}) if isinstance(registry.get("samples"), dict) else {}
    delete_violations = _delete_primitive_violations()
    try:
        __import__("cleanwincli.windows_identity")
        windows_identity_importable = True
        windows_identity_error = None
    except Exception as exc:  # noqa: BLE001 - doctor should report import errors as data.
        windows_identity_importable = False
        windows_identity_error = str(exc)
    checks = [
        _doctor_check(
            "default_dry_run",
            capabilities_report.get("default_dry_run") is True and capabilities_report.get("execution_requires_execute_flag") is True,
            "CLI must default to dry-run and require an explicit execute flag.",
        ),
        _doctor_check(
            "single_destructive_exit",
            capabilities_report.get("deletion_exit") == "cleanwincli.delete_ops.safe_delete",
            "All destructive cleanup must route through cleanwincli.delete_ops.safe_delete.",
            {"deletion_exit": capabilities_report.get("deletion_exit")},
        ),
        _doctor_check(
            "delete_primitives_owned_by_delete_ops",
            not delete_violations,
            "Low-level delete/move primitives must not appear outside cleanwincli.delete_ops.",
            {"violations": delete_violations},
        ),
        _doctor_check(
            "ai_contracts_valid",
            bool(schema_validation.get("valid")),
            "AI tool schema and provider parity must validate.",
            {"violation_count": schema_validation.get("violation_count")},
        ),
        _doctor_check(
            "host_policy_valid",
            bool(policy_validation.get("valid")) and "cleanwin_execute_plan" in policy.get("auto_call", {}).get("deny", []),
            "AI host policy must deny destructive auto-calls and validate successfully.",
            {"violations": policy_validation.get("violations", [])},
        ),
        _doctor_check(
            "schema_registry_samples_present",
            all(name in registry_samples for name in ["cleanwin.plan.v1", "cleanwin.inspect.v1", "cleanwin.filesystem-identity.v1"]),
            "Machine-readable schema registry must include representative samples for core contracts.",
            {"sample_names": sorted(registry_samples)},
        ),
        _doctor_check(
            "critical_schemas_registered",
            all(name in registry_names for name in ["cleanwin.plan.v1", "cleanwin.inspect.v1", "cleanwin.doctor.v1", "cleanwin.ai-tools.v1"]),
            "Core CLI and AI schemas must be registered.",
            {"schema_count": registry.get("schema_count")},
        ),
        _doctor_check(
            "windows_identity_backend_importable",
            windows_identity_importable,
            "Windows-native identity backend module must be importable on non-Windows hosts for packaging checks.",
            {"error": windows_identity_error},
        ),
        _doctor_check(
            "version_consistency",
            (pyproject_version is not None or distribution_version is not None)
            and capabilities_report.get("version") == __version__
            and (pyproject_version is None or pyproject_version == __version__)
            and (distribution_version is None or distribution_version == __version__),
            "Package metadata, installed distribution metadata, cleanwincli.__version__, and capabilities version must stay in sync.",
            {
                "pyproject_version": pyproject_version,
                "distribution_version": distribution_version,
                "package_version": __version__,
                "capabilities_version": capabilities_report.get("version"),
            },
        ),
    ]
    failed = [check["id"] for check in checks if not check["passed"]]
    return {
        "schema": "cleanwin.doctor.v1",
        "destructive": False,
        "dry_run": True,
        "ready": not failed,
        "failed_check_ids": failed,
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "recommended_commands": [
            ["make", "pytest"],
            ["make", "lint"],
            ["make", "type"],
            ["make", "compile"],
            ["python3", "-m", "pytest", "-q"],
            ["python3", "-m", "ruff", "check", "cleanwin.py", "cleanwincli", "tests"],
            ["python3", "-m", "mypy", "cleanwin.py", "cleanwincli", "tests"],
            ["python3", "-m", "compileall", "cleanwin.py", "cleanwincli", "tests"],
            ["python3", "-m", "build", "--sdist", "--wheel"],
            ["make", "package-install-smoke"],
            ["make", "sdist-install-smoke"],
            ["make", "mcp-install-smoke"],
            ["python3", "cleanwin.py", "--json", "ai-tools", "--provider", "validation"],
            ["python3", "cleanwin.py", "--json", "ai-readiness", "--validate"],
            ["python3", "cleanwin.py", "--json", "ai-self-test"],
            ["python3", "cleanwin.py", "--json", "ai-runbook"],
            ["python3", "cleanwin.py", "--json", "doctor"],
            ["make", "docs-smoke"],
            ["make", "ai-smoke"],
            ["make", "mcp-smoke"],
            ["make", "version-smoke"],
            ["make", "clean"],
            ["make", "quality"],
        ],
    }


def review_plan(plan: Plan, raw_payload: dict[str, Any], *, require_context: bool) -> dict[str, Any]:
    validation = validate_plan_payload(plan, raw_payload, require_context=require_context)
    candidates = list(plan.candidates)
    unique_rule_ids = sorted({candidate.rule_id for candidate in candidates if candidate.rule_id})
    official_cleanup_commands = sorted({candidate.official_cleanup_command for candidate in candidates if candidate.official_cleanup_command})
    category_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    rule_summary: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        category_counts[candidate.category] = category_counts.get(candidate.category, 0) + 1
        risk_counts[candidate.risk] = risk_counts.get(candidate.risk, 0) + 1
        if candidate.rule_id:
            entry = rule_summary.setdefault(
                candidate.rule_id,
                {
                    "rule_id": candidate.rule_id,
                    "cache_owner": candidate.cache_owner,
                    "candidate_count": 0,
                    "bytes_reclaimable": 0,
                    "official_cleanup_command": candidate.official_cleanup_command,
                },
            )
            entry["candidate_count"] += 1
            entry["bytes_reclaimable"] += candidate.size_bytes
    grouped_risks = [
        {"risk": risk, "candidate_count": count}
        for risk, count in sorted(risk_counts.items())
    ]
    read_only_categories = set(capabilities().get("read_only_categories", []))
    manual_only_categories = sorted(category for category in plan.categories if category in read_only_categories)
    candidate_categories = {candidate.category for candidate in candidates}
    strategy_cleanup_commands = set(official_cleanup_commands)
    browser_tool_commands = {
        "Google Chrome": "Use Chrome > Clear browsing data",
        "Microsoft Edge": "Use Edge > Clear browsing data",
        "Mozilla Firefox": "Use Firefox > Clear recent history",
    }
    for candidate in candidates:
        if candidate.category == "browser-cache" and candidate.cache_owner in browser_tool_commands:
            strategy_cleanup_commands.add(browser_tool_commands[candidate.cache_owner])
    cleanup_strategy = {
        "preferred": "official-tool-or-app-ui" if "browser-cache" in candidate_categories else "official-cli-command",
        "fallback": "cleanwin-recycle-execution",
        "requires_review": True,
        "official_cleanup_commands": sorted(strategy_cleanup_commands),
    }
    sensitive_exclusions = []
    if any(candidate.category == "browser-cache" for candidate in candidates):
        sensitive_exclusions.append(
            {
                "category": "browser-cache",
                "reason": "Only browser cache directories are planned; profile databases, cookies, sessions, passwords, extensions, and sync state remain excluded.",
                "excluded_patterns": [
                    {"pattern": "Cookies", "risk": "authentication sessions and site state"},
                    {"pattern": "Login Data", "risk": "saved credentials database"},
                    {"pattern": "Local State", "risk": "browser profile and encryption metadata"},
                    {"pattern": "Sessions", "risk": "open tab and browser session state"},
                    {"pattern": "Extensions", "risk": "installed extension state and settings"},
                    {"pattern": "Firefox profile root", "risk": "mixed cookies, history, extension, and account data"},
                ],
            }
        )
    execution_handoff = {
        "safe_to_execute": bool(validation["valid"] and all(candidate.delete_mode == "recycle" and not candidate.requires_admin for candidate in candidates)),
        "requires_human_confirmation": True,
        "requires_matching_dry_run_token": True,
        "requires_plan_context": require_context,
        "required_predecessor_tools": [
            "cleanwin_validate_plan",
            "cleanwin_policy_simulate",
            "cleanwin_dry_run_plan",
            "cleanwin_execute_plan",
        ],
        "blocked_reasons": list(validation["errors"]),
    }
    return {
        "schema": "cleanwin.review.v1",
        "destructive": False,
        "plan_schema": plan.schema,
        "plan_source_fingerprint": raw_payload.get("source_fingerprint"),
        "validation": validation,
        "summary": {
            "candidate_count": len(candidates),
            "bytes_reclaimable": sum(candidate.size_bytes for candidate in candidates if candidate.safe_to_delete),
            "safe_candidate_count": sum(1 for candidate in candidates if candidate.safe_to_delete),
        },
        "category_counts": [{"category": category, "candidate_count": count} for category, count in sorted(category_counts.items())],
        "risk_summary": grouped_risks,
        "rule_ids": unique_rule_ids,
        "rule_summary": [rule_summary[key] for key in sorted(rule_summary)],
        "official_cleanup_commands": official_cleanup_commands,
        "cleanup_strategy": cleanup_strategy,
        "manual_only_categories": manual_only_categories,
        "sensitive_exclusions": sensitive_exclusions,
        "execution_handoff": execution_handoff,
    }


def ai_tools_report(provider: str = "catalog") -> dict[str, Any]:
    if provider == "catalog":
        return tool_catalog()
    if provider == "openai":
        return openai_functions_export()
    if provider == "anthropic":
        return anthropic_tools_export()
    if provider == "parity":
        return provider_export_parity()
    if provider == "validation":
        return validate_ai_schema()
    if provider == "registry":
        return schema_registry()
    if provider == "host-policy":
        return render_ai_host_policy(tool_catalog=tool_catalog())
    if provider == "readiness":
        return ai_readiness_report()
    if provider == "self-test":
        return ai_self_test_report()
    if provider == "runbook":
        return ai_runbook_report()
    if provider == "workflow-router":
        return workflow_router_report()
    if provider == "environment-index":
        return environment_index_report()
    if provider == "workflow-decision":
        return workflow_decision_report(route_id="recycle-execution", requested_tool="cleanwin_execute_plan")
    if provider == "workflow-trace":
        return workflow_trace_report()
    if provider == "doctor":
        return doctor_report()
    if provider == "file-report":
        return file_report()
    if provider == "recovery-readiness":
        return recovery_readiness_report()
    if provider == "scan-governance":
        return scan_governance_report()
    if provider == "installed-app-inventory":
        return installed_app_inventory_report()
    if provider == "official-command-plan":
        return official_command_plan_report()
    if provider == "preset-catalog":
        return preset_catalog_report()
    if provider == "promotion-gates":
        return promotion_gates_report()
    if provider == "browser-profile-inventory":
        return browser_profile_inventory_report()
    if provider == "debloat-privacy-report":
        return debloat_privacy_report()
    if provider == "backup-delete-contract":
        return backup_delete_contract_report()
    if provider == "disable-revert-contract":
        return disable_revert_contract_report()
    if provider == "permanent-delete-denial":
        return permanent_delete_denial_report()
    if provider == "startup-service-inventory":
        return startup_service_inventory_report()
    if provider == "system-health-report":
        return system_health_report()
    if provider == "windows-native-artifacts":
        return windows_native_artifacts_report()
    if provider == "windows-inventory":
        return windows_inventory_report()
    if provider == "windows-smoke-matrix":
        return windows_smoke_matrix_report()
    if provider == "review-sample":
        sample = schema_registry().get("samples", {}).get("cleanwin.review.v1")
        if isinstance(sample, dict):
            return sample
        raise RuntimeError("Schema sample unavailable: cleanwin.review.v1")
    raise RuntimeError(f"Unsupported ai-tools provider: {provider}")


def host_policy_report(*, validate: bool = False) -> dict[str, Any]:
    policy = render_ai_host_policy(tool_catalog=tool_catalog())
    if validate:
        return validate_ai_host_policy(policy)
    return policy


def ai_readiness_command(*, validate: bool = False) -> dict[str, Any]:
    report = ai_readiness_report()
    if validate:
        return validate_ai_readiness(report)
    return report


def ai_self_test_command() -> dict[str, Any]:
    return ai_self_test_report()


def ai_runbook_command() -> dict[str, Any]:
    return ai_runbook_report()


def workflow_router_command() -> dict[str, Any]:
    return workflow_router_report()


def environment_index_command() -> dict[str, Any]:
    return environment_index_report()


def workflow_decision_command(
    *,
    route_id: str,
    requested_tool: str | None = None,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    return workflow_decision_report(route_id=route_id, requested_tool=requested_tool, artifacts=artifacts or [])


def workflow_trace_command() -> dict[str, Any]:
    return workflow_trace_report()


def recovery_readiness_command() -> dict[str, Any]:
    return recovery_readiness_report()


def file_report_command() -> dict[str, Any]:
    return file_report()


def scan_governance_command() -> dict[str, Any]:
    return scan_governance_report()


def external_rule_translate_command(
    path: Path,
    *,
    source_format: str,
    upstream_project: str | None,
    upstream_rule_id_or_commit: str,
    license_name: str,
) -> dict[str, Any]:
    return translate_external_rules_file(
        path,
        source_format=source_format,
        upstream_project=upstream_project,
        upstream_rule_id_or_commit=upstream_rule_id_or_commit,
        license_name=license_name,
    )


def installed_app_inventory_command() -> dict[str, Any]:
    return installed_app_inventory_report()


def official_command_plan_command() -> dict[str, Any]:
    return official_command_plan_report()


def preset_catalog_command() -> dict[str, Any]:
    return preset_catalog_report()


def promotion_gates_command() -> dict[str, Any]:
    return promotion_gates_report()


def browser_profile_inventory_command() -> dict[str, Any]:
    return browser_profile_inventory_report()


def debloat_privacy_report_command() -> dict[str, Any]:
    return debloat_privacy_report()


def backup_delete_contract_command() -> dict[str, Any]:
    return backup_delete_contract_report()


def disable_revert_contract_command() -> dict[str, Any]:
    return disable_revert_contract_report()


def permanent_delete_denial_command() -> dict[str, Any]:
    return permanent_delete_denial_report()


def startup_service_inventory_command() -> dict[str, Any]:
    return startup_service_inventory_report()


def system_health_report_command() -> dict[str, Any]:
    return system_health_report()


def windows_native_artifacts_command() -> dict[str, Any]:
    return windows_native_artifacts_report()


def windows_inventory_command() -> dict[str, Any]:
    return windows_inventory_report()


def windows_smoke_matrix_command() -> dict[str, Any]:
    return windows_smoke_matrix_report()


def policy_simulate(
    plan: Plan,
    raw_payload: dict[str, Any],
    *,
    execute: bool,
    delete_mode: str,
    operation_log: str | None,
    require_plan_context: bool,
    require_confirmation_token: bool,
    confirmation_token: str | None,
    confirmation_phrase: str | None,
) -> dict[str, Any]:
    validation = validate_plan_payload(plan, raw_payload, require_context=require_plan_context)
    tool_name = "cleanwin_execute_plan" if execute else "cleanwin_dry_run_plan"
    tool = next(tool for tool in AI_TOOL_DEFINITIONS if tool["name"] == tool_name)
    args: dict[str, Any] = {"delete_mode": delete_mode, "require_plan_context": require_plan_context}
    if operation_log is not None:
        args["operation_log"] = operation_log
    if require_confirmation_token or confirmation_token:
        args["confirmation_token"] = confirmation_token or ""
    if confirmation_phrase is not None:
        args["confirmation_phrase"] = confirmation_phrase
    decision = evaluate_ai_host_tool_call(tool=tool, arguments=args, source="cleanwin.policy-simulate")
    recommended_argv = ["cleanwin", "--json", "execute-plan", "--plan-file", "<plan-file>"]
    if execute:
        recommended_argv.extend(["--execute", "--yes", "--operation-log", operation_log or DEFAULT_OPERATION_LOG])
        recommended_argv.extend(["--confirmation-phrase", CONFIRMATION_PHRASE])
        recommended_argv.extend(["--confirmation-token", confirmation_token_for_plan(plan, raw_payload)])
    return {
        "schema": "cleanwin.ai-policy-simulation.v1",
        "execute_intent": execute,
        "delete_mode": delete_mode,
        "validation": validation,
        "decision": decision,
        "recommended_argv": recommended_argv,
        "safe_to_execute": bool(validation["valid"] and decision["allowed"] and execute),
    }
