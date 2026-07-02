"""CleanWin doctor report — health checks for the installation and configuration."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any

from cleanwincli import __version__
from cleanwincli.ai_host_policy import render_ai_host_policy, validate_ai_host_policy
from cleanwincli.ai_schema import tool_catalog, validate_ai_schema
from cleanwincli.ai_versioning import schema_registry


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
    from cleanwincli.core import capabilities

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
            "Installed distribution, pyproject.toml, and capabilities version must stay in sync with the single source of truth.",
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
