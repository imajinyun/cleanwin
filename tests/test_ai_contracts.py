from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import (
    AI_TOOL_DEFINITIONS,
    CONFIRMATION_PHRASE,
    tool_catalog,
    validate_ai_schema,
    validate_tool_arguments,
)

JSONPayload = dict[str, Any]
RunCleanWin = Callable[..., subprocess.CompletedProcess[str]]
CleanWinResultJSON = Callable[[subprocess.CompletedProcess[str]], JSONPayload]
CleanWinJSON = Callable[..., JSONPayload]
CleanWinPlanFile = Callable[..., JSONPayload]
MakeTempPlan = Callable[[Path, bool], tuple[Path, Path, dict[str, str]]]
AssertSchemasRegistered = Callable[[list[str]], None]
AssertSchemaSample = Callable[[str], JSONPayload]
AssertSchemaSamples = Callable[[Sequence[str]], dict[str, JSONPayload]]
AssertReadonlySchemaSample = Callable[[str], JSONPayload]
AssertNoUnittestCommands = Callable[[list[list[str]]], None]

READONLY_WORKFLOW_CONTEXT_TOOLS = [
    "cleanwin_environment_index",
    "cleanwin_workflow_decision",
    "cleanwin_workflow_trace",
]


def test_ai_schema_validation_and_provider_parity() -> None:
    validation = validate_ai_schema()
    assert validation["valid"], validation
    destructive = [tool for tool in AI_TOOL_DEFINITIONS if tool["risk"] == "destructive"]
    assert [tool["name"] for tool in destructive] == ["cleanwin_execute_plan"]
    assert destructive[0]["auto_call_allowed"] is False
    assert destructive[0]["requires_confirmation"] is True


def test_schema_registry_includes_ai_host_critical_schemas(
    assert_schemas_registered: AssertSchemasRegistered,
) -> None:
    assert_schemas_registered(
        [
            "cleanwin.plan.v1",
            "cleanwin.ai-tools.v1",
            "cleanwin.ai-host-policy.v1",
            "cleanwin.ai-host-tool-call-decision.v1",
            "cleanwin.ai-tool-argument-validation.v1",
            "cleanwin.ai-policy-simulation.v1",
            "cleanwin.workflow-router.v1",
            "cleanwin.environment-index.v1",
            "cleanwin.workflow-decision.v1",
            "cleanwin.workflow-trace.v1",
            "cleanwin.review.v1",
            "cleanwin.doctor.v1",
        ]
    )


def test_schema_samples_include_rule_metadata_and_review_details(
    assert_schema_samples: AssertSchemaSamples,
    assert_readonly_schema_sample: AssertReadonlySchemaSample,
    assert_no_unittest_commands: AssertNoUnittestCommands,
) -> None:
    samples = assert_schema_samples(
        [
            "cleanwin.inspect.v1",
            "cleanwin.plan.v1",
            "cleanwin.execute.v1",
            "cleanwin.ai-tool-argument-validation.v1",
        ]
    )
    inspect_sample = samples["cleanwin.inspect.v1"]
    assert inspect_sample["candidates"][0]["rule_id"] == "dev-cache.npm.cache"
    assert inspect_sample["candidates"][0]["cache_owner"] == "npm"
    assert "official_cleanup_command" in inspect_sample["candidates"][0]
    assert "review_details" in inspect_sample["findings"][0]

    plan_sample = samples["cleanwin.plan.v1"]
    assert plan_sample["candidates"][0]["rule_id"] == "dev-cache.npm.cache"
    assert plan_sample["candidates"][0]["identity"]["schema"] == "cleanwin.filesystem-identity.v1"

    execute_sample = samples["cleanwin.execute.v1"]
    assert execute_sample["schema"] == "cleanwin.execute.v1"
    assert execute_sample["dry_run"] is True
    assert execute_sample["results"][0]["status"] == "dry-run"
    assert "confirmation_token" in execute_sample["confirmation"]

    doctor_sample = assert_readonly_schema_sample("cleanwin.doctor.v1")
    assert doctor_sample["schema"] == "cleanwin.doctor.v1"
    assert "recommended_commands" in doctor_sample
    assert ["make", "pytest"] in doctor_sample["recommended_commands"]
    assert ["make", "quality"] in doctor_sample["recommended_commands"]
    assert_no_unittest_commands(doctor_sample["recommended_commands"])

    review_sample = assert_readonly_schema_sample("cleanwin.review.v1")
    assert review_sample["schema"] == "cleanwin.review.v1"
    assert "execution_handoff" in review_sample
    assert "sensitive_exclusions" in review_sample

    argument_validation_sample = samples["cleanwin.ai-tool-argument-validation.v1"]
    assert argument_validation_sample["schema"] == "cleanwin.ai-tool-argument-validation.v1"
    assert argument_validation_sample["valid"] is False


def test_ai_tools_expose_rule_id_filter_for_inspect_and_plan() -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert "rule_ids" in by_name["cleanwin_inspect"]["parameters"]["properties"]
    assert "rule_ids" in by_name["cleanwin_generate_plan"]["parameters"]["properties"]


def test_ai_tools_expose_readonly_workflow_router() -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    router = by_name["cleanwin_workflow_router"]
    assert router["risk"] == "readonly"
    assert router["auto_call_allowed"] is True
    assert router["requires_confirmation"] is False
    assert router["parameters"]["additionalProperties"] is False


@pytest.mark.parametrize("tool_name", READONLY_WORKFLOW_CONTEXT_TOOLS)
def test_ai_tools_expose_readonly_workflow_context_tools(tool_name: str) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    tool = by_name[tool_name]
    assert tool["risk"] == "readonly"
    assert tool["auto_call_allowed"] is True
    assert tool["requires_confirmation"] is False


def test_workflow_decision_tool_requires_route_id() -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert "route_id" in by_name["cleanwin_workflow_decision"]["parameters"]["required"]


def test_workflow_router_sample_keeps_execution_non_auto_callable(
    assert_readonly_schema_sample: AssertReadonlySchemaSample,
) -> None:
    sample = assert_readonly_schema_sample("cleanwin.workflow-router.v1")
    assert sample["schema"] == "cleanwin.workflow-router.v1"
    assert sample["destructive"] is False
    execution_route = next(route for route in sample["routes"] if route["id"] == "recycle-execution")
    assert execution_route["destructive"] is True
    assert execution_route["auto_call_allowed"] is False
    assert execution_route["required_arguments"]["delete_mode"] == "recycle"
    assert "raw shell command" in execution_route["blocked_actions"]


def test_workflow_context_schema_samples_are_registered(
    assert_readonly_schema_sample: AssertReadonlySchemaSample,
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    environment = assert_readonly_schema_sample("cleanwin.environment-index.v1")
    assert environment["schema"] == "cleanwin.environment-index.v1"
    assert environment["operation_log"]["required_for_execution"] is True

    samples = assert_schema_samples(["cleanwin.workflow-decision.v1", "cleanwin.workflow-trace.v1"])
    decision = samples["cleanwin.workflow-decision.v1"]
    assert decision["schema"] == "cleanwin.workflow-decision.v1"
    assert decision["allowed"] is False

    trace = samples["cleanwin.workflow-trace.v1"]
    assert trace["schema"] == "cleanwin.workflow-trace.v1"
    assert trace["execution_gate"]["ai_auto_call_allowed"] is False


def test_schema_samples_cover_package_and_browser_cache_categories(
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    samples = assert_schema_samples(["cleanwin.inspect.v1"])
    inspect_sample = samples["cleanwin.inspect.v1"]
    assert "browser-cache" in inspect_sample["categories"]
    assert "package-cache" in inspect_sample["categories"]
    candidate_categories = {candidate["category"] for candidate in inspect_sample["candidates"]}
    assert "browser-cache" in candidate_categories
    assert "package-cache" in candidate_categories


def test_ai_tools_expose_review_plan_tool() -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert "cleanwin_review_plan" in by_name
    assert by_name["cleanwin_review_plan"]["risk"] == "planning"
    assert by_name["cleanwin_review_plan"]["requires_confirmation"] is False
    assert "plan_file" in by_name["cleanwin_review_plan"]["parameters"]["required"]


def test_tool_argument_validation_rejects_invalid_types_and_unknown_fields() -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    validation = validate_tool_arguments(
        by_name["cleanwin_generate_plan"],
        {"categories": "dev-cache", "older_than_days": "0", "unexpected": True},
    )
    assert validation["valid"] is False
    assert "arguments.categories must be an array" in validation["violations"]
    assert "arguments.older_than_days must be a number" in validation["violations"]
    assert "arguments.unexpected is not allowed" in validation["violations"]

    valid = validate_tool_arguments(by_name["cleanwin_generate_plan"], {"categories": ["dev-cache"], "older_than_days": 0})
    assert valid["valid"], valid


def test_host_policy_blocks_raw_command_and_missing_destructive_gates() -> None:
    tool = next(tool for tool in tool_catalog()["tools"] if tool["name"] == "cleanwin_execute_plan")
    denied = evaluate_ai_host_tool_call(tool=tool, arguments={"cmd": "remove things"}, source="test")
    assert denied["allowed"] is False
    codes = {reason["code"] for reason in denied["blocking_reasons"]}
    assert "RAW_COMMAND_ARGUMENT_DENIED" in codes
    assert "RECYCLE_MODE_REQUIRED" in codes
    assert "OPERATION_LOG_REQUIRED" in codes

    allowed = evaluate_ai_host_tool_call(
        tool=tool,
        arguments={
            "delete_mode": "recycle",
            "operation_log": "ops.jsonl",
            "confirmation_phrase": CONFIRMATION_PHRASE,
            "confirmation_token": "token",
            "require_plan_context": True,
        },
        source="test",
    )
    assert allowed["allowed"], allowed


def test_cli_ai_tools_and_host_policy_are_valid(cleanwin_json: CleanWinJSON) -> None:
    assert cleanwin_json("ai-tools")["schema"] == "cleanwin.ai-tools.v1"

    assert cleanwin_json("ai-tools", "--provider", "parity")["valid"]

    assert cleanwin_json("host-policy", "--validate")["valid"]


def test_execute_requires_dry_run_confirmation_token(
    tmp_path: Path,
    run_cleanwin: RunCleanWin,
    cleanwin_result_json: CleanWinResultJSON,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
) -> None:
    _, target, env = make_temp_plan_fixture(tmp_path, True)
    plan_file = tmp_path / "plan.json"
    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)

    confirmation = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)[
        "confirmation"
    ]

    denied = run_cleanwin(
        "execute-plan",
        "--plan-file",
        str(plan_file),
        "--execute",
        "--yes",
        "--no-require-plan-context",
        "--operation-log",
        str(tmp_path / "ops.jsonl"),
        "--trash-root",
        str(tmp_path / "trash"),
        env=env,
    )
    assert denied.returncode == 2
    assert "confirmation phrase" in cleanwin_result_json(denied)["error"]
    assert target.exists()

    allowed = run_cleanwin(
        "execute-plan",
        "--plan-file",
        str(plan_file),
        "--execute",
        "--yes",
        "--no-require-plan-context",
        "--operation-log",
        str(tmp_path / "ops.jsonl"),
        "--trash-root",
        str(tmp_path / "trash"),
        "--confirmation-phrase",
        confirmation["required_phrase"],
        "--confirmation-token",
        confirmation["confirmation_token"],
        env=env,
    )
    assert allowed.returncode == 0, allowed.stderr
    assert not target.exists()
