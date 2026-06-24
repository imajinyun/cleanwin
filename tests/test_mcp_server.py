from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cleanwincli import __version__

ROOT = Path(__file__).resolve().parents[1]
MCP_MODULE = "cleanwincli.mcp_server"
JSONPayload = dict[str, Any]
MCPRequest = dict[str, Any]
MCPResponse = dict[str, Any]
CleanWinPlanFile = Callable[..., JSONPayload]
CleanWinTestEnv = Callable[..., dict[str, str]]
WriteTextFile = Callable[[Path, str], Path]
MakeDirectory = Callable[[Path], Path]

MCP_RESOURCE_SCHEMAS: tuple[tuple[str, str], ...] = (
    ("cleanwin://ai/host-policy", "cleanwin.ai-host-policy.v1"),
    ("cleanwin://ai/readiness", "cleanwin.ai-readiness.v1"),
    ("cleanwin://ai/self-test", "cleanwin.ai-self-test.v1"),
    ("cleanwin://ai/runbook", "cleanwin.ai-runbook.v1"),
    ("cleanwin://ai/workflow-router", "cleanwin.workflow-router.v1"),
    ("cleanwin://ai/environment-index", "cleanwin.environment-index.v1"),
    ("cleanwin://ai/workflow-decision", "cleanwin.workflow-decision.v1"),
    ("cleanwin://ai/workflow-trace", "cleanwin.workflow-trace.v1"),
    ("cleanwin://engineering/doctor", "cleanwin.doctor.v1"),
    ("cleanwin://engineering/recovery-readiness", "cleanwin.recovery-readiness.v1"),
    ("cleanwin://inventory/installed-apps", "cleanwin.installed-app-inventory.v1"),
    ("cleanwin://plan/official-command-plan", "cleanwin.official-command-plan.v1"),
    ("cleanwin://inventory/debloat-privacy", "cleanwin.debloat-privacy-report.v1"),
    ("cleanwin://inventory/startup-services", "cleanwin.startup-service-inventory.v1"),
    ("cleanwin://plan/review-sample", "cleanwin.review.v1"),
)
EXPECTED_MCP_RESOURCE_URIS = ("cleanwin://ai/schema-registry", *(uri for uri, _ in MCP_RESOURCE_SCHEMAS))


def load_json_object(text: str) -> JSONPayload:
    payload = json.loads(text)
    assert isinstance(payload, dict)
    return payload


def parse_mcp_stdout(stdout: str, stderr: str) -> MCPResponse:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"empty MCP stdout; stderr={stderr}")
    try:
        response = load_json_object(lines[0])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid MCP JSON response: {lines[0]!r}; stderr={stderr}") from exc
    return response


def mcp_request(request: MCPRequest, env: dict[str, str]) -> MCPResponse:
    proc = subprocess.Popen(
        [sys.executable, "-m", MCP_MODULE],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = proc.communicate(input=json.dumps(request), timeout=15)
    return parse_mcp_stdout(stdout, stderr)


def persistent_mcp_request(request: MCPRequest, env: dict[str, str]) -> MCPResponse:
    proc = subprocess.Popen(
        [sys.executable, "-m", MCP_MODULE],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    stdout_pipe = proc.stdout
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    lines: queue.Queue[str] = queue.Queue()
    reader = threading.Thread(target=lambda: lines.put(stdout_pipe.readline()), daemon=True)
    reader.start()
    try:
        line = lines.get(timeout=5)
    except queue.Empty:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
        raise RuntimeError(f"timed out waiting for persistent MCP response; stdout={stdout}; stderr={stderr}") from None
    if line.strip():
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 999, "method": "shutdown"}) + "\n")
        proc.stdin.flush()
        proc.communicate(timeout=5)
        return load_json_object(line)
    proc.kill()
    stdout, stderr = proc.communicate(timeout=5)
    raise RuntimeError(f"empty persistent MCP response; stdout={stdout}; stderr={stderr}")


def mcp_content_json(response: MCPResponse) -> JSONPayload:
    return load_json_object(response["result"]["contents"][0]["text"])


def read_mcp_resource(uri: str, env: dict[str, str]) -> JSONPayload:
    read = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "resources/read",
            "params": {"uri": uri},
        },
        env,
    )
    return mcp_content_json(read)


def generate_temp_plan(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_test_env: CleanWinTestEnv,
    write_text_file: WriteTextFile,
    make_directory: MakeDirectory,
) -> tuple[Path, Path, dict[str, str]]:
    temp_root = make_directory(tmp_path / "Temp")
    stale_file = write_text_file(temp_root / "stale.tmp", "x")
    plan_file = tmp_path / "plan.json"
    env = cleanwin_test_env(extra={"TEMP": str(temp_root), "TMP": str(temp_root)})
    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)
    return plan_file, stale_file, env


def call_mcp_tool(
    name: str, arguments: JSONPayload, env: dict[str, str], request_id: int = 52
) -> MCPResponse:
    proc = subprocess.Popen(
        [sys.executable, "-m", MCP_MODULE],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    stdout, stderr = proc.communicate(
        input=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        ),
        timeout=15,
    )
    return parse_mcp_stdout(stdout, stderr)


@pytest.mark.parametrize(
    "uri",
    EXPECTED_MCP_RESOURCE_URIS,
)
def test_resources_list_exposes_expected_uri(uri: str, cleanwin_test_env: CleanWinTestEnv) -> None:
    listed = mcp_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list"}, cleanwin_test_env())
    uris = {resource["uri"] for resource in listed["result"]["resources"]}

    assert uri in uris


def test_host_policy_resource_exposes_execute_plan_denial(cleanwin_test_env: CleanWinTestEnv) -> None:
    payload = read_mcp_resource("cleanwin://ai/host-policy", cleanwin_test_env())

    assert payload["schema"] == "cleanwin.ai-host-policy.v1"
    assert "cleanwin_execute_plan" in payload["auto_call"]["deny"]


@pytest.mark.parametrize(("uri", "schema"), MCP_RESOURCE_SCHEMAS)
def test_resources_readiness_self_test_and_runbook(
    uri: str, schema: str, cleanwin_test_env: CleanWinTestEnv
) -> None:
    payload = read_mcp_resource(uri, cleanwin_test_env())

    assert payload["schema"] == schema


def test_initialize_and_tools_list(cleanwin_test_env: CleanWinTestEnv) -> None:
    env = cleanwin_test_env()
    initialized = mcp_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, env)
    assert initialized["result"]["serverInfo"]["name"] == "cleanwin-mcp"
    assert initialized["result"]["serverInfo"]["version"] == __version__

    response = mcp_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, env)
    tools = response["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert "cleanwin_capabilities" in names
    assert "cleanwin_workflow_router" in names
    assert "cleanwin_environment_index" in names
    assert "cleanwin_workflow_decision" in names
    assert "cleanwin_workflow_trace" in names
    assert "cleanwin_execute_plan" in names
    assert "cleanwin_review_plan" in names
    tool_by_name = {tool["name"]: tool for tool in tools}
    assert tool_by_name["cleanwin_capabilities"]["annotations"]["readOnlyHint"]
    assert tool_by_name["cleanwin_workflow_router"]["annotations"]["readOnlyHint"]
    assert tool_by_name["cleanwin_environment_index"]["annotations"]["readOnlyHint"]
    assert tool_by_name["cleanwin_workflow_decision"]["annotations"]["readOnlyHint"]
    assert tool_by_name["cleanwin_workflow_trace"]["annotations"]["readOnlyHint"]
    assert tool_by_name["cleanwin_execute_plan"]["annotations"]["destructiveHint"]


def test_resources_read_responds_before_persistent_stdin_eof(cleanwin_test_env: CleanWinTestEnv) -> None:
    read = persistent_mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "resources/read",
            "params": {"uri": "cleanwin://ai/runbook"},
        },
        cleanwin_test_env(),
    )
    payload = mcp_content_json(read)
    assert payload["schema"] == "cleanwin.ai-runbook.v1"


def test_tools_call_readonly_capabilities(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "cleanwin_capabilities", "arguments": {}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert not result["isError"]
    assert result["structuredContent"]["tool"] == "cleanwin"
    assert result["governanceDecision"]["schema"] == "cleanwin.ai-host-tool-call-decision.v1"
    assert result["governanceDecision"]["allowed"]


def test_tools_call_workflow_router(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {"name": "cleanwin_workflow_router", "arguments": {}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert not result["isError"], result
    assert result["structuredContent"]["schema"] == "cleanwin.workflow-router.v1"
    routes = {route["id"]: route for route in result["structuredContent"]["routes"]}
    assert routes["recycle-execution"]["auto_call_allowed"] is False


@pytest.mark.parametrize(
    ("tool", "arguments", "schema"),
    [
        ("cleanwin_environment_index", {}, "cleanwin.environment-index.v1"),
        (
            "cleanwin_workflow_decision",
            {"route_id": "recycle-execution", "requested_tool": "cleanwin_execute_plan"},
            "cleanwin.workflow-decision.v1",
        ),
        ("cleanwin_workflow_trace", {}, "cleanwin.workflow-trace.v1"),
    ],
)
def test_tools_call_workflow_context_tools(
    tool: str, arguments: JSONPayload, schema: str, cleanwin_test_env: CleanWinTestEnv
) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 54,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert not result["isError"], result
    assert result["structuredContent"]["schema"] == schema


def test_tools_call_inspect_supports_rule_id_filter(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 51,
            "method": "tools/call",
            "params": {
                "name": "cleanwin_inspect",
                "arguments": {"categories": ["dev-cache"], "rule_ids": ["dev-cache.npm.cache"], "older_than_days": 0, "max_items": 5},
            },
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert not result["isError"], result
    assert result["structuredContent"]["schema"] == "cleanwin.inspect.v1"
    assert result["structuredContent"]["filters"]["rule_ids"] == ["dev-cache.npm.cache"]


def test_tools_call_review_plan(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_test_env: CleanWinTestEnv,
    write_text_file: WriteTextFile,
    make_directory: MakeDirectory,
) -> None:
    plan_file, _, env = generate_temp_plan(
        tmp_path, cleanwin_plan_file, cleanwin_test_env, write_text_file, make_directory
    )
    response = call_mcp_tool(
        "cleanwin_review_plan",
        {"plan_file": str(plan_file), "require_plan_context": False},
        env=env,
        request_id=52,
    )
    result = response["result"]

    assert not result["isError"], result
    assert result["structuredContent"]["schema"] == "cleanwin.review.v1"
    assert "execution_handoff" in result["structuredContent"]


def test_tools_call_dry_run_plan_returns_candidate_results_and_token(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_test_env: CleanWinTestEnv,
    write_text_file: WriteTextFile,
    make_directory: MakeDirectory,
) -> None:
    plan_file, stale_file, env = generate_temp_plan(
        tmp_path, cleanwin_plan_file, cleanwin_test_env, write_text_file, make_directory
    )
    response = call_mcp_tool("cleanwin_dry_run_plan", {"plan_file": str(plan_file)}, env=env, request_id=53)
    result = response["result"]

    assert not result["isError"], result
    structured = result["structuredContent"]
    assert structured["schema"] == "cleanwin.execute.v1"
    assert not structured["executed"]
    assert structured["results"][0]["status"] == "dry-run"
    assert structured["results"][0]["path"] == str(stale_file)
    assert structured["summary"] == {"result_count": 1, "status_counts": {"dry-run": 1}}
    assert "confirmation_token" in structured["confirmation"]
    assert stale_file.exists()


def test_raw_command_argument_denied_for_readonly_tool(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "cleanwin_capabilities", "arguments": {"raw_command": "del C:\\Windows"}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert result["isError"]
    assert result["structuredContent"]["schema"] == "cleanwin.mcp-tool-error.v1"
    assert result["governanceDecision"]["blocking_reasons"][0]["code"] == "RAW_COMMAND_ARGUMENT_DENIED"


def test_tool_call_rejects_schema_invalid_arguments(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 61,
            "method": "tools/call",
            "params": {"name": "cleanwin_inspect", "arguments": {"categories": "dev-cache", "older_than_days": "0"}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert result["isError"]
    validation = result["structuredContent"]["argument_validation"]
    assert validation["schema"] == "cleanwin.ai-tool-argument-validation.v1"
    assert "arguments.categories must be an array" in validation["violations"]
    assert "arguments.older_than_days must be a number" in validation["violations"]
    assert result["governanceDecision"]["allowed"]


def test_tool_call_rejects_unknown_non_raw_arguments(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 62,
            "method": "tools/call",
            "params": {"name": "cleanwin_capabilities", "arguments": {"unexpected": "ignored-before"}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert result["isError"]
    validation = result["structuredContent"]["argument_validation"]
    assert "arguments.unexpected is not allowed" in validation["violations"]


def test_tool_call_rejects_missing_required_arguments(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 63,
            "method": "tools/call",
            "params": {"name": "cleanwin_review_plan", "arguments": {}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert result["isError"]
    validation = result["structuredContent"]["argument_validation"]
    assert "arguments.plan_file is required" in validation["violations"]


def test_destructive_tool_missing_gates_denied(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "cleanwin_execute_plan", "arguments": {"plan_file": "plan.json"}},
        },
        cleanwin_test_env(),
    )
    result = response["result"]
    assert result["isError"]
    codes = {reason["code"] for reason in result["governanceDecision"]["blocking_reasons"]}
    assert "RECYCLE_MODE_REQUIRED" in codes
    assert "OPERATION_LOG_REQUIRED" in codes
    assert "HUMAN_CONFIRMATION_PHRASE_REQUIRED" in codes
    assert "CONFIRMATION_TOKEN_REQUIRED" in codes


def test_unknown_method_returns_jsonrpc_error(cleanwin_test_env: CleanWinTestEnv) -> None:
    response = mcp_request({"jsonrpc": "2.0", "id": 8, "method": "unknown/method"}, cleanwin_test_env())
    assert response["error"]["code"] == -32601
