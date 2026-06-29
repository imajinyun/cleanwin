from __future__ import annotations

import subprocess
from collections.abc import Callable, Collection, Sequence
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
AssertReadonlyPayload = Callable[[JSONPayload], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertCommandSequence = Callable[[list[list[str]], list[list[str]]], None]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertTextContainsAll = Callable[[str, Sequence[str]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
AssertExactSequence = Callable[[Sequence[Any], Sequence[Any]], Sequence[Any]]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertReturnCode = Callable[[subprocess.CompletedProcess[str], int], subprocess.CompletedProcess[str]]
AssertPathExists = Callable[[Path], Path]
AssertPathMissing = Callable[[Path], Path]

READONLY_WORKFLOW_CONTEXT_TOOLS = [
    "cleanwin_environment_index",
    "cleanwin_workflow_decision",
    "cleanwin_workflow_trace",
]


def test_ai_schema_validation_and_provider_parity(
    assert_payload_status_true: AssertPayloadStatus,
    assert_field_values: AssertFieldValues,
    assert_exact_sequence: AssertExactSequence,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    validation = validate_ai_schema()
    assert_payload_status_true(validation, "valid")
    destructive = [tool for tool in AI_TOOL_DEFINITIONS if tool["risk"] == "destructive"]
    assert_exact_sequence([tool["name"] for tool in destructive], ["cleanwin_execute_plan"])
    assert_field_values(destructive[0], {"auto_call_allowed": False, "requires_confirmation": True})
    assert_text_contains_all(destructive[0]["description"], ["low-risk cache", "recycle mode"])


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
            "cleanwin.contract-exposure-matrix.v1",
            "cleanwin.contract-exposure-validation.v1",
        ]
    )


def test_schema_samples_include_rule_metadata_and_review_details(
    assert_schema_samples: AssertSchemaSamples,
    assert_readonly_schema_sample: AssertReadonlySchemaSample,
    assert_readonly_payload: AssertReadonlyPayload,
    assert_payload_schema: AssertPayloadSchema,
    assert_command_sequence: AssertCommandSequence,
    assert_payload_status_false: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
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
    assert_field_values(inspect_sample["candidates"][0], {"rule_id": "dev-cache.npm.cache", "cache_owner": "npm"})
    assert_contains_all(inspect_sample["candidates"][0], ["official_cleanup_command"])
    assert_contains_all(inspect_sample["findings"][0], ["review_details"])

    plan_sample = samples["cleanwin.plan.v1"]
    assert_field_values(plan_sample["candidates"][0], {"rule_id": "dev-cache.npm.cache"})
    assert_payload_schema(plan_sample["candidates"][0]["identity"], "cleanwin.filesystem-identity.v1")

    execute_sample = samples["cleanwin.execute.v1"]
    assert_readonly_payload(execute_sample)
    assert_field_values(execute_sample["results"][0], {"status": "dry-run"})
    assert_contains_all(execute_sample["confirmation"], ["confirmation_token"])

    doctor_sample = assert_readonly_schema_sample("cleanwin.doctor.v1")
    assert_contains_all(doctor_sample, ["recommended_commands"])
    assert_command_sequence(doctor_sample["recommended_commands"], [["make", "pytest"], ["make", "quality"]])

    review_sample = assert_readonly_schema_sample("cleanwin.review.v1")
    assert_contains_all(review_sample, ["execution_handoff", "sensitive_exclusions"])

    argument_validation_sample = samples["cleanwin.ai-tool-argument-validation.v1"]
    assert_payload_status_false(argument_validation_sample, "valid")


def test_ai_tools_expose_rule_id_filter_for_inspect_and_plan(assert_contains_all: AssertContainsAll) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert_contains_all(by_name["cleanwin_inspect"]["parameters"]["properties"], ["rule_ids"])
    assert_contains_all(by_name["cleanwin_generate_plan"]["parameters"]["properties"], ["rule_ids"])


def test_ai_tools_expose_readonly_workflow_router(assert_field_values: AssertFieldValues) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    router = by_name["cleanwin_workflow_router"]
    assert_field_values(
        router,
        {
            "risk": "readonly",
            "auto_call_allowed": True,
            "requires_confirmation": False,
            "parameters.additionalProperties": False,
        },
    )


@pytest.mark.parametrize("tool_name", READONLY_WORKFLOW_CONTEXT_TOOLS)
def test_ai_tools_expose_readonly_workflow_context_tools(
    tool_name: str,
    assert_field_values: AssertFieldValues,
) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    tool = by_name[tool_name]
    assert_field_values(tool, {"risk": "readonly", "auto_call_allowed": True, "requires_confirmation": False})


def test_workflow_decision_tool_requires_route_id(assert_contains_all: AssertContainsAll) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert_contains_all(by_name["cleanwin_workflow_decision"]["parameters"]["required"], ["route_id"])


def test_workflow_router_sample_keeps_execution_non_auto_callable(
    assert_readonly_schema_sample: AssertReadonlySchemaSample,
    assert_readonly_payload: AssertReadonlyPayload,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    sample = assert_readonly_schema_sample("cleanwin.workflow-router.v1")
    assert_readonly_payload(sample)
    execution_route = next(route for route in sample["routes"] if route["id"] == "recycle-execution")
    assert_field_values(
        execution_route,
        {"destructive": True, "auto_call_allowed": False, "required_arguments.delete_mode": "recycle"},
    )
    assert_any_text_contains(execution_route["blocked_actions"], "raw shell command")


def test_workflow_context_schema_samples_are_registered(
    assert_readonly_schema_sample: AssertReadonlySchemaSample,
    assert_schema_samples: AssertSchemaSamples,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_payload_status_false: AssertPayloadStatus,
    assert_field_values: AssertFieldValues,
) -> None:
    environment = assert_readonly_schema_sample("cleanwin.environment-index.v1")
    assert_field_values(environment, {"operation_log.required_for_execution": True})

    samples = assert_schema_samples(
        [
            "cleanwin.workflow-decision.v1",
            "cleanwin.workflow-trace.v1",
            "cleanwin.low-risk-cache-readiness-validation.v1",
            "cleanwin.operation-log-readiness-validation.v1",
        ]
    )
    decision = samples["cleanwin.workflow-decision.v1"]
    assert_payload_status_false(decision, "allowed")

    trace = samples["cleanwin.workflow-trace.v1"]
    assert_execution_disabled(trace["execution_gate"], "ai_auto_call_allowed")
    readiness_validation = samples["cleanwin.low-risk-cache-readiness-validation.v1"]
    assert_payload_status_false(readiness_validation, "valid")
    assert_execution_disabled(readiness_validation)
    operation_log_readiness_validation = samples["cleanwin.operation-log-readiness-validation.v1"]
    assert_payload_status_false(operation_log_readiness_validation, "valid")
    assert_execution_disabled(operation_log_readiness_validation)


def test_schema_samples_cover_package_and_browser_cache_categories(
    assert_schema_samples: AssertSchemaSamples,
    assert_contains_all: AssertContainsAll,
) -> None:
    samples = assert_schema_samples(["cleanwin.inspect.v1"])
    inspect_sample = samples["cleanwin.inspect.v1"]
    assert_contains_all(inspect_sample["categories"], ["browser-cache", "package-cache"])
    candidate_categories = {candidate["category"] for candidate in inspect_sample["candidates"]}
    assert_contains_all(candidate_categories, ["browser-cache", "package-cache"])


def test_ai_tools_expose_review_plan_tool(
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert_contains_all(by_name, ["cleanwin_review_plan"])
    assert_field_values(by_name["cleanwin_review_plan"], {"risk": "planning", "requires_confirmation": False})
    assert_contains_all(by_name["cleanwin_review_plan"]["parameters"]["required"], ["plan_file"])


def test_tool_argument_validation_rejects_invalid_types_and_unknown_fields(
    assert_payload_status_false: AssertPayloadStatus,
    assert_payload_status_true: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    validation = validate_tool_arguments(
        by_name["cleanwin_generate_plan"],
        {"categories": "dev-cache", "older_than_days": "0", "unexpected": True},
    )
    assert_payload_status_false(validation, "valid")
    assert_contains_all(
        validation["violations"],
        [
            "arguments.categories must be an array",
            "arguments.older_than_days must be a number",
            "arguments.unexpected is not allowed",
        ],
    )

    valid = validate_tool_arguments(by_name["cleanwin_generate_plan"], {"categories": ["dev-cache"], "older_than_days": 0})
    assert_payload_status_true(valid, "valid")


def test_host_policy_blocks_raw_command_and_missing_destructive_gates(
    assert_payload_status_false: AssertPayloadStatus,
    assert_payload_status_true: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    tool = next(tool for tool in tool_catalog()["tools"] if tool["name"] == "cleanwin_execute_plan")
    denied = evaluate_ai_host_tool_call(tool=tool, arguments={"cmd": "remove things"}, source="test")
    assert_payload_status_false(denied, "allowed")
    codes = {reason["code"] for reason in denied["blocking_reasons"]}
    assert_contains_all(codes, ["RAW_COMMAND_ARGUMENT_DENIED", "RECYCLE_MODE_REQUIRED", "OPERATION_LOG_REQUIRED"])

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
    assert_payload_status_true(allowed, "allowed")


def test_cli_ai_tools_and_host_policy_are_valid(
    cleanwin_json: CleanWinJSON,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
) -> None:
    assert_payload_schema(cleanwin_json("ai-tools"), "cleanwin.ai-tools.v1")

    assert_payload_status_true(cleanwin_json("ai-tools", "--provider", "parity"), "valid")

    assert_payload_status_true(cleanwin_json("host-policy", "--validate"), "valid")


def test_execute_requires_dry_run_confirmation_token(
    tmp_path: Path,
    run_cleanwin: RunCleanWin,
    cleanwin_result_json: CleanWinResultJSON,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
    assert_text_contains_all: AssertTextContainsAll,
    assert_returncode: AssertReturnCode,
    assert_path_exists: AssertPathExists,
    assert_path_missing: AssertPathMissing,
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
    assert_returncode(denied, 2)
    assert_text_contains_all(cleanwin_result_json(denied)["error"], ["confirmation phrase"])
    assert_path_exists(target)

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
    assert_returncode(allowed, 0)
    assert_path_missing(target)
