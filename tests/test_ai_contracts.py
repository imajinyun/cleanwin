from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import (
    AI_TOOL_DEFINITIONS,
    CONFIRMATION_PHRASE,
    tool_catalog,
    validate_ai_schema,
    validate_tool_arguments,
)
from cleanwincli.ai_versioning import schema_registry, schema_sample

JSONPayload = dict[str, Any]
RunCleanWin = Callable[..., subprocess.CompletedProcess[str]]
CleanWinResultJSON = Callable[[subprocess.CompletedProcess[str]], JSONPayload]
CleanWinJSON = Callable[..., JSONPayload]
CleanWinPlanFile = Callable[..., JSONPayload]


def require_schema_sample(name: str) -> dict[str, Any]:
    sample = schema_sample(name)
    if sample is None:
        raise AssertionError(f"missing schema sample: {name}")
    return sample


def test_ai_schema_validation_and_provider_parity() -> None:
    validation = validate_ai_schema()
    assert validation["valid"], validation
    destructive = [tool for tool in AI_TOOL_DEFINITIONS if tool["risk"] == "destructive"]
    assert [tool["name"] for tool in destructive] == ["cleanwin_execute_plan"]
    assert destructive[0]["auto_call_allowed"] is False
    assert destructive[0]["requires_confirmation"] is True


def test_schema_registry_includes_ai_host_critical_schemas() -> None:
    names = {entry["name"] for entry in schema_registry()["entries"]}
    for required in [
        "cleanwin.plan.v1",
        "cleanwin.ai-tools.v1",
        "cleanwin.ai-host-policy.v1",
        "cleanwin.ai-host-tool-call-decision.v1",
        "cleanwin.ai-tool-argument-validation.v1",
        "cleanwin.ai-policy-simulation.v1",
        "cleanwin.review.v1",
        "cleanwin.doctor.v1",
    ]:
        assert required in names


def test_schema_samples_include_rule_metadata_and_review_details() -> None:
    inspect_sample = require_schema_sample("cleanwin.inspect.v1")
    assert inspect_sample["candidates"][0]["rule_id"] == "dev-cache.npm.cache"
    assert inspect_sample["candidates"][0]["cache_owner"] == "npm"
    assert "official_cleanup_command" in inspect_sample["candidates"][0]
    assert "review_details" in inspect_sample["findings"][0]

    plan_sample = require_schema_sample("cleanwin.plan.v1")
    assert plan_sample["candidates"][0]["rule_id"] == "dev-cache.npm.cache"
    assert plan_sample["candidates"][0]["identity"]["schema"] == "cleanwin.filesystem-identity.v1"

    execute_sample = require_schema_sample("cleanwin.execute.v1")
    assert execute_sample["schema"] == "cleanwin.execute.v1"
    assert execute_sample["dry_run"] is True
    assert execute_sample["results"][0]["status"] == "dry-run"
    assert "confirmation_token" in execute_sample["confirmation"]

    doctor_sample = require_schema_sample("cleanwin.doctor.v1")
    assert doctor_sample["schema"] == "cleanwin.doctor.v1"
    assert doctor_sample["destructive"] is False
    assert "recommended_commands" in doctor_sample

    review_sample = require_schema_sample("cleanwin.review.v1")
    assert review_sample["schema"] == "cleanwin.review.v1"
    assert review_sample["destructive"] is False
    assert "execution_handoff" in review_sample
    assert "sensitive_exclusions" in review_sample

    argument_validation_sample = require_schema_sample("cleanwin.ai-tool-argument-validation.v1")
    assert argument_validation_sample["schema"] == "cleanwin.ai-tool-argument-validation.v1"
    assert argument_validation_sample["valid"] is False


def test_ai_tools_expose_rule_id_filter_for_inspect_and_plan() -> None:
    by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
    assert "rule_ids" in by_name["cleanwin_inspect"]["parameters"]["properties"]
    assert "rule_ids" in by_name["cleanwin_generate_plan"]["parameters"]["properties"]


def test_schema_samples_cover_package_and_browser_cache_categories() -> None:
    inspect_sample = require_schema_sample("cleanwin.inspect.v1")
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
) -> None:
    temp_root = tmp_path / "Temp"
    temp_root.mkdir()
    target = temp_root / "stale.tmp"
    target.write_text("x", encoding="utf-8")
    env = {"TEMP": str(temp_root), "TMP": str(temp_root), "CLEANWIN_TEST_MODE": "1"}
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
