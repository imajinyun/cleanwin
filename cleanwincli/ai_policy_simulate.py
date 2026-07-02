"""AI policy simulation — dry-run evaluation of plan execution against host policy."""

from __future__ import annotations

from typing import Any

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import (
    AI_TOOL_DEFINITIONS,
    CONFIRMATION_PHRASE,
    DEFAULT_OPERATION_LOG,
)
from cleanwincli.models import Plan
from cleanwincli.plan_validation import confirmation_token_for_plan, validate_plan_payload


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
