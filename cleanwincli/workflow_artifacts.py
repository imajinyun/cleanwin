"""Workflow decision and trace contracts for AI-safe CleanWin operation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from cleanwincli.workflow_router import workflow_router_report

WORKFLOW_DECISION_SCHEMA = "cleanwin.workflow-decision.v1"
WORKFLOW_TRACE_SCHEMA = "cleanwin.workflow-trace.v1"


def _route_by_id(route_id: str) -> Mapping[str, Any] | None:
    for route in workflow_router_report()["routes"]:
        if route.get("id") == route_id:
            return route
    return None


def workflow_decision_report(
    *,
    route_id: str,
    requested_tool: str | None = None,
    artifacts: Sequence[str] = (),
    arguments: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    route = _route_by_id(route_id)
    if route is None:
        return {
            "schema": WORKFLOW_DECISION_SCHEMA,
            "allowed": False,
            "route_id": route_id,
            "requested_tool": requested_tool,
            "risk": "unknown",
            "missing_artifacts": [],
            "blocking_reasons": [{"code": "ROUTE_NOT_FOUND", "detail": f"Unknown workflow route: {route_id}"}],
        }

    provided_artifacts = set(artifacts)
    required_artifacts = [str(item) for item in route.get("required_artifacts", [])]
    missing_artifacts = [item for item in required_artifacts if item not in provided_artifacts]
    allowed_tools = [str(item) for item in route.get("allowed_tools", [])]
    blocking_reasons: list[dict[str, str]] = []
    if requested_tool and requested_tool not in allowed_tools:
        blocking_reasons.append(
            {
                "code": "TOOL_NOT_ALLOWED_FOR_ROUTE",
                "detail": f"{requested_tool} is not allowed for route {route_id}",
            }
        )
    if missing_artifacts:
        blocking_reasons.append({"code": "MISSING_REQUIRED_ARTIFACTS", "detail": ", ".join(missing_artifacts)})
    if route.get("destructive") and route.get("auto_call_allowed") is False:
        blocking_reasons.append(
            {
                "code": "DESTRUCTIVE_ROUTE_REQUIRES_MANUAL_GATES",
                "detail": "Destructive routes are not auto-callable and require explicit execution gates.",
            }
        )

    argument_values = arguments or {}
    required_arguments = route.get("required_arguments", {})
    if isinstance(required_arguments, Mapping):
        for name, required_value in required_arguments.items():
            if name not in argument_values:
                blocking_reasons.append({"code": "MISSING_REQUIRED_ARGUMENT", "detail": str(name)})
            elif required_value == "recycle" and argument_values.get(name) != "recycle":
                blocking_reasons.append({"code": "RECYCLE_MODE_REQUIRED", "detail": str(name)})

    return {
        "schema": WORKFLOW_DECISION_SCHEMA,
        "allowed": not blocking_reasons,
        "route_id": route_id,
        "requested_tool": requested_tool,
        "risk": route.get("risk"),
        "destructive": bool(route.get("destructive")),
        "auto_call_allowed": bool(route.get("auto_call_allowed")),
        "allowed_tools": allowed_tools,
        "provided_artifacts": sorted(provided_artifacts),
        "required_artifacts": required_artifacts,
        "missing_artifacts": missing_artifacts,
        "blocking_reasons": blocking_reasons,
    }


def workflow_trace_report() -> dict[str, Any]:
    return {
        "schema": WORKFLOW_TRACE_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "purpose": "Describe the auditable artifact chain expected for a CleanWin AI/MCP workflow.",
        "artifact_chain": [
            {"step": 1, "route": "discover-capabilities", "artifact_schema": "cleanwin.workflow-router.v1", "required": True},
            {"step": 2, "route": "read-only-inventory", "artifact_schema": "cleanwin.inspect.v1", "required": True},
            {"step": 3, "route": "plan-cleanup", "artifact_schema": "cleanwin.plan.v1", "required": True},
            {"step": 4, "route": "validate-and-review", "artifact_schema": "cleanwin.review.v1", "required": True},
            {"step": 5, "route": "validate-and-review", "artifact_schema": "cleanwin.ai-policy-simulation.v1", "required": True},
            {"step": 6, "route": "dry-run-execution", "artifact_schema": "cleanwin.ai-confirmation-summary.v1", "required": True},
            {
                "step": 7,
                "route": "recycle-execution",
                "artifact_schema": "cleanwin.operation-log.jsonl",
                "required": True,
                "destructive": True,
            },
        ],
        "execution_gate": {
            "requires_all_prior_artifacts": True,
            "requires_matching_plan_fingerprint": True,
            "requires_matching_dry_run_token": True,
            "requires_operation_log": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": ["This report does not read local artifact files.", "This report does not execute cleanup."],
    }
