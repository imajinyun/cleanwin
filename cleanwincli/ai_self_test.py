"""Deterministic AI self-test checks for CleanWin."""

from __future__ import annotations

from typing import Any

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_readiness import ai_readiness_report, validate_ai_readiness
from cleanwincli.ai_schema import CONFIRMATION_PHRASE, tool_catalog, validate_ai_schema


def _result(name: str, passed: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "evidence": evidence}


def ai_self_test_report() -> dict[str, Any]:
    catalog = tool_catalog()
    tool_by_name = {tool["name"]: tool for tool in catalog["tools"]}
    schema_validation = validate_ai_schema()
    readiness = ai_readiness_report()
    readiness_validation = validate_ai_readiness(readiness)

    readonly_decision = evaluate_ai_host_tool_call(
        tool=tool_by_name["cleanwin_capabilities"], arguments={}, source="cleanwin.ai-self-test"
    )
    raw_denial = evaluate_ai_host_tool_call(
        tool=tool_by_name["cleanwin_capabilities"],
        arguments={"raw_command": "del C:\\Windows"},
        source="cleanwin.ai-self-test",
    )
    destructive_denial = evaluate_ai_host_tool_call(
        tool=tool_by_name["cleanwin_execute_plan"], arguments={"plan_file": "plan.json"}, source="cleanwin.ai-self-test"
    )
    destructive_allowed = evaluate_ai_host_tool_call(
        tool=tool_by_name["cleanwin_execute_plan"],
        arguments={
            "delete_mode": "recycle",
            "operation_log": "ops.jsonl",
            "confirmation_phrase": CONFIRMATION_PHRASE,
            "confirmation_token": "token",
            "require_plan_context": True,
        },
        source="cleanwin.ai-self-test",
    )
    tests = [
        _result("ai_schema_validation", bool(schema_validation["valid"]), schema_validation),
        _result("ai_readiness_validation", bool(readiness_validation["valid"]), readiness_validation),
        _result("readonly_tool_allowed", bool(readonly_decision["allowed"]), readonly_decision),
        _result("raw_command_denied", not raw_denial["allowed"], raw_denial),
        _result("destructive_missing_gates_denied", not destructive_denial["allowed"], destructive_denial),
        _result("destructive_all_gates_allowed_by_policy", bool(destructive_allowed["allowed"]), destructive_allowed),
    ]
    return {
        "schema": "cleanwin.ai-self-test.v1",
        "passed": all(test["passed"] for test in tests),
        "test_count": len(tests),
        "passed_count": sum(1 for test in tests if test["passed"]),
        "tests": tests,
    }
