"""AI readiness reporting for CleanWin host integrations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cleanwincli.ai_host_policy import render_ai_host_policy, validate_ai_host_policy
from cleanwincli.ai_schema import AI_TOOL_DEFINITIONS, provider_export_parity, tool_catalog, validate_ai_schema
from cleanwincli.ai_versioning import schema_registry

REQUIRED_AI_SCHEMAS = frozenset(
    {
        "cleanwin.ai-tools.v1",
        "cleanwin.ai-schema-validation.v1",
        "cleanwin.ai-provider-export-parity.v1",
        "cleanwin.ai-host-policy.v1",
        "cleanwin.ai-host-policy-validation.v1",
        "cleanwin.ai-host-tool-call-decision.v1",
        "cleanwin.ai-policy-simulation.v1",
        "cleanwin.review.v1",
        "cleanwin.ai-schema-registry.v1",
        "cleanwin.ai-readiness.v1",
        "cleanwin.ai-self-test.v1",
        "cleanwin.ai-runbook.v1",
        "cleanwin.doctor.v1",
        "cleanwin.recovery-readiness.v1",
        "cleanwin.scan-governance.v1",
        "cleanwin.external-rule-review.v1",
        "cleanwin.installed-app-inventory.v1",
        "cleanwin.official-command-plan.v1",
        "cleanwin.debloat-privacy-report.v1",
        "cleanwin.system-health-report.v1",
        "cleanwin.startup-service-inventory.v1",
        "cleanwin.filesystem-identity.v1",
    }
)


def _check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail}


def _schema_names(registry: Mapping[str, Any]) -> set[str]:
    return {str(entry.get("name")) for entry in registry.get("entries", []) if isinstance(entry, Mapping)}


def ai_readiness_report() -> dict[str, Any]:
    catalog = tool_catalog()
    schema_validation = validate_ai_schema()
    parity = provider_export_parity()
    policy = render_ai_host_policy(tool_catalog=catalog)
    policy_validation = validate_ai_host_policy(policy)
    registry = schema_registry()
    names = _schema_names(registry)
    missing_schemas = sorted(REQUIRED_AI_SCHEMAS - names)
    destructive_tools = sorted(str(tool.get("name")) for tool in AI_TOOL_DEFINITIONS if tool.get("risk") == "destructive")
    checks = [
        _check("ai_schema_valid", bool(schema_validation["valid"]), "AI tool schema validation must pass."),
        _check("provider_export_parity", bool(parity["valid"]), "OpenAI/Anthropic/catalog tool names must match."),
        _check("host_policy_valid", bool(policy_validation["valid"]), "AI host policy validation must pass."),
        _check("destructive_tool_denied", "cleanwin_execute_plan" in policy["auto_call"]["deny"], "Destructive tool must be auto-call denied."),
        _check("single_destructive_tool", destructive_tools == ["cleanwin_execute_plan"], "Only cleanwin_execute_plan may be destructive in MVP."),
        _check("critical_schemas_registered", not missing_schemas, "All AI host critical schemas must be registered."),
    ]
    ready = all(check["passed"] for check in checks)
    return {
        "schema": "cleanwin.ai-readiness.v1",
        "ready_for_ai_host": ready,
        "ready_for_mcp": ready,
        "check_count": len(checks),
        "passed_count": sum(1 for check in checks if check["passed"]),
        "checks": checks,
        "missing_schemas": missing_schemas,
        "required_manual_execution_gates": policy["execution_gate"],
        "release_gate_commands": [
            "make pytest",
            "make lint",
            "make type",
            "make compile",
            "make quality",
            "python3 cleanwin.py --json ai-readiness",
            "python3 cleanwin.py --json ai-self-test",
            "python3 cleanwin.py --json doctor",
        ],
    }


def validate_ai_readiness(report: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    if report.get("schema") != "cleanwin.ai-readiness.v1":
        violations.append("schema must be cleanwin.ai-readiness.v1")
    if report.get("ready_for_ai_host") is not True:
        violations.append("ready_for_ai_host must be true")
    if report.get("ready_for_mcp") is not True:
        violations.append("ready_for_mcp must be true")
    for check in report.get("checks", []):
        if isinstance(check, Mapping) and check.get("passed") is not True:
            violations.append(f"check failed: {check.get('name')}")
    return {
        "schema": "cleanwin.ai-readiness-validation.v1",
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }
