"""CleanWin MCP stdio server.

The server intentionally accepts only structured MCP tool arguments and builds
argv from registered cleanwin tool templates. It never accepts shell/raw command
input, and destructive tools are denied unless the cleanwin AI host policy gates
are satisfied.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cleanwincli import __version__
from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import AI_TOOL_DEFINITIONS, validate_tool_arguments
from cleanwincli.core import ai_tools_report, host_policy_report

MCP_PROTOCOL_VERSION = "2024-11-05"


def tool_annotations(tool: Mapping[str, Any]) -> dict[str, bool]:
    risk = str(tool.get("risk") or "")
    return {
        "readOnlyHint": risk == "readonly",
        "destructiveHint": risk == "destructive",
        "idempotentHint": risk in {"readonly", "planning", "dry-run"},
        "openWorldHint": False,
    }


def mcp_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["parameters"],
            "annotations": tool_annotations(tool),
        }
        for tool in AI_TOOL_DEFINITIONS
    ]


def find_cleanwin() -> list[str]:
    configured = os.environ.get("CLEANWIN_CLI")
    if configured:
        configured_path = Path(configured)
        if not configured_path.exists():
            raise RuntimeError(f"CLI not found: {configured}")
        if configured_path.suffix == ".py":
            return [sys.executable, str(configured_path)]
        return [str(configured_path)]
    executable_name = "cleanwin.exe" if os.name == "nt" else "cleanwin"
    sibling_cli = Path(sys.executable).resolve().with_name(executable_name)
    if sibling_cli.exists():
        return [str(sibling_cli)]
    project_root = Path(__file__).resolve().parents[1]
    script = project_root / "cleanwin.py"
    if script.exists():
        return [sys.executable, str(script)]
    return ["cleanwin"]


def categories_arg(arguments: Mapping[str, Any]) -> str | None:
    categories = arguments.get("categories")
    if categories is None:
        return None
    if isinstance(categories, list):
        return ",".join(str(item) for item in categories)
    return str(categories)


def repeated_string_args(arguments: Mapping[str, Any], key: str, flag: str) -> list[str]:
    value = arguments.get(key)
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in values:
        text = str(item)
        if text:
            result.extend([flag, text])
    return result


def bool_arg(arguments: Mapping[str, Any], key: str, default: bool) -> bool:
    value = arguments.get(key, default)
    return bool(value)


def build_cleanwin_argv(tool_name: str, arguments: Mapping[str, Any]) -> list[str]:
    argv = [*find_cleanwin(), "--json"]
    if tool_name == "cleanwin_capabilities":
        return [*argv, "capabilities"]
    if tool_name == "cleanwin_workflow_router":
        return [*argv, "workflow-router"]
    if tool_name == "cleanwin_environment_index":
        return [*argv, "environment-index"]
    if tool_name == "cleanwin_workflow_decision":
        result = [*argv, "workflow-decision", "--route-id", str(arguments.get("route_id") or "")]
        if arguments.get("requested_tool"):
            result.extend(["--requested-tool", str(arguments["requested_tool"])])
        for artifact in arguments.get("artifacts", []) or []:
            result.extend(["--artifact", str(artifact)])
        return result
    if tool_name == "cleanwin_workflow_trace":
        return [*argv, "workflow-trace"]
    if tool_name == "cleanwin_inspect":
        result = [*argv, "inspect"]
        categories = categories_arg(arguments)
        if categories:
            result.extend(["--categories", categories])
        if "older_than_days" in arguments:
            result.extend(["--older-than-days", str(arguments["older_than_days"])])
        if "max_items" in arguments:
            result.extend(["--max-items", str(arguments["max_items"])])
        result.extend(repeated_string_args(arguments, "rule_ids", "--rule-id"))
        return result
    if tool_name == "cleanwin_generate_plan":
        result = [*argv, "plan"]
        categories = categories_arg(arguments)
        if categories:
            result.extend(["--categories", categories])
        if "older_than_days" in arguments:
            result.extend(["--older-than-days", str(arguments["older_than_days"])])
        if "max_items" in arguments:
            result.extend(["--max-items", str(arguments["max_items"])])
        result.extend(repeated_string_args(arguments, "rule_ids", "--rule-id"))
        if arguments.get("output"):
            result.extend(["--output", str(arguments["output"])])
        return result
    if tool_name == "cleanwin_validate_plan":
        result = [*argv, "validate-plan", "--plan-file", str(arguments.get("plan_file") or "")]
        if not bool_arg(arguments, "require_plan_context", True):
            result.append("--no-require-plan-context")
        return result
    if tool_name == "cleanwin_review_plan":
        result = [*argv, "review-plan", "--plan-file", str(arguments.get("plan_file") or "")]
        if not bool_arg(arguments, "require_plan_context", True):
            result.append("--no-require-plan-context")
        return result
    if tool_name == "cleanwin_policy_simulate":
        result = [*argv, "policy-simulate", "--plan-file", str(arguments.get("plan_file") or "")]
        if arguments.get("execute"):
            result.append("--execute")
        result.extend(["--delete-mode", str(arguments.get("delete_mode") or "recycle")])
        if arguments.get("operation_log"):
            result.extend(["--operation-log", str(arguments["operation_log"])])
        if not bool_arg(arguments, "require_plan_context", True):
            result.append("--no-require-plan-context")
        if arguments.get("require_confirmation_token"):
            result.append("--require-confirmation-token")
        if arguments.get("confirmation_token"):
            result.extend(["--confirmation-token", str(arguments["confirmation_token"])])
        if arguments.get("confirmation_phrase"):
            result.extend(["--confirmation-phrase", str(arguments["confirmation_phrase"])])
        return result
    if tool_name == "cleanwin_dry_run_plan":
        result = [*argv, "execute-plan", "--plan-file", str(arguments.get("plan_file") or "")]
        if arguments.get("trash_root"):
            result.extend(["--trash-root", str(arguments["trash_root"])])
        return result
    if tool_name == "cleanwin_execute_plan":
        result = [
            *argv,
            "execute-plan",
            "--plan-file",
            str(arguments.get("plan_file") or ""),
            "--execute",
            "--yes",
            "--operation-log",
            str(arguments.get("operation_log") or ""),
            "--confirmation-phrase",
            str(arguments.get("confirmation_phrase") or ""),
            "--confirmation-token",
            str(arguments.get("confirmation_token") or ""),
        ]
        if not bool_arg(arguments, "require_plan_context", True):
            result.append("--no-require-plan-context")
        if arguments.get("trash_root"):
            result.extend(["--trash-root", str(arguments["trash_root"])])
        return result
    raise RuntimeError(f"Unknown tool: {tool_name}")


def tool_error(tool_name: str, message: str, *, policy_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    structured: dict[str, Any] = {
        "schema": "cleanwin.mcp-tool-error.v1",
        "tool": tool_name,
        "message": message,
    }
    if policy_decision is not None:
        structured["policy_decision"] = policy_decision
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": json.dumps(structured, sort_keys=True)}],
        "structuredContent": structured,
        "isError": True,
    }
    if policy_decision is not None:
        result["governanceDecision"] = policy_decision
    return result


def tool_argument_error(tool_name: str, validation: dict[str, Any], *, policy_decision: dict[str, Any]) -> dict[str, Any]:
    structured = {
        "schema": "cleanwin.mcp-tool-error.v1",
        "tool": tool_name,
        "message": "Tool arguments failed cleanwin schema validation",
        "argument_validation": validation,
    }
    return {
        "content": [{"type": "text", "text": json.dumps(structured, sort_keys=True)}],
        "structuredContent": structured,
        "governanceDecision": policy_decision,
        "isError": True,
    }


def call_tool(name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    tool = next((tool for tool in AI_TOOL_DEFINITIONS if tool["name"] == name), None)
    if tool is None:
        return tool_error(name, f"Unknown tool: {name}")
    decision = evaluate_ai_host_tool_call(tool=tool, arguments=arguments, source="cleanwin.mcp")
    if not decision["allowed"]:
        return tool_error(name, "Tool call denied by cleanwin host policy", policy_decision=decision)
    argument_validation = validate_tool_arguments(tool, arguments)
    if not argument_validation["valid"]:
        return tool_argument_error(name, argument_validation, policy_decision=decision)
    try:
        argv = build_cleanwin_argv(name, arguments)
        completed = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 - MCP must return structured tool errors.
        return tool_error(name, str(exc), policy_decision=decision)
    if completed.returncode != 0:
        text = completed.stdout.strip() or completed.stderr.strip() or f"cleanwin failed with exit {completed.returncode}"
        return tool_error(name, text, policy_decision=decision)
    text = completed.stdout.strip()
    try:
        structured = json.loads(text) if text else {}
    except json.JSONDecodeError:
        structured = {"schema": "cleanwin.mcp-text-output.v1", "text": text}
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured,
        "governanceDecision": decision,
        "isError": False,
    }


def resource_payload(uri: str) -> dict[str, Any]:
    if uri == "cleanwin://ai/tools":
        return ai_tools_report("catalog")
    if uri == "cleanwin://ai/host-policy":
        return host_policy_report(validate=False)
    if uri == "cleanwin://ai/schema-registry":
        return ai_tools_report("registry")
    if uri == "cleanwin://ai/schema-validation":
        return ai_tools_report("validation")
    if uri == "cleanwin://ai/readiness":
        return ai_tools_report("readiness")
    if uri == "cleanwin://ai/self-test":
        return ai_tools_report("self-test")
    if uri == "cleanwin://ai/runbook":
        return ai_tools_report("runbook")
    if uri == "cleanwin://ai/workflow-router":
        return ai_tools_report("workflow-router")
    if uri == "cleanwin://ai/environment-index":
        return ai_tools_report("environment-index")
    if uri == "cleanwin://ai/workflow-decision":
        return ai_tools_report("workflow-decision")
    if uri == "cleanwin://ai/workflow-trace":
        return ai_tools_report("workflow-trace")
    if uri == "cleanwin://engineering/doctor":
        return ai_tools_report("doctor")
    if uri == "cleanwin://engineering/recovery-readiness":
        return ai_tools_report("recovery-readiness")
    if uri == "cleanwin://engineering/low-risk-cache-readiness":
        return ai_tools_report("low-risk-cache-readiness")
    if uri == "cleanwin://engineering/operation-log-readiness":
        return ai_tools_report("operation-log-readiness")
    if uri == "cleanwin://engineering/contract-exposure-matrix":
        return ai_tools_report("contract-exposure-matrix")
    if uri == "cleanwin://inventory/installed-apps":
        return ai_tools_report("installed-app-inventory")
    if uri == "cleanwin://inventory/windows":
        return ai_tools_report("windows-inventory")
    if uri == "cleanwin://plan/official-command-plan":
        return ai_tools_report("official-command-plan")
    if uri == "cleanwin://inventory/debloat-privacy":
        return ai_tools_report("debloat-privacy-report")
    if uri == "cleanwin://inventory/startup-services":
        return ai_tools_report("startup-service-inventory")
    if uri == "cleanwin://plan/review-sample":
        return ai_tools_report("review-sample")
    raise KeyError(uri)


def handle_request(request: Mapping[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    if request.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid Request"}}
    method = request.get("method")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "cleanwin-mcp", "version": __version__},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": mcp_tools()}}
    if method == "tools/call":
        raw_params = request.get("params")
        params: Mapping[str, Any] = raw_params if isinstance(raw_params, Mapping) else {}
        name = str(params.get("name") or "")
        raw_arguments = params.get("arguments")
        arguments: Mapping[str, Any] = raw_arguments if isinstance(raw_arguments, Mapping) else {}
        return {"jsonrpc": "2.0", "id": request_id, "result": call_tool(name, arguments)}
    if method == "resources/list":
        resources = [
            {"uri": "cleanwin://ai/tools", "name": "CleanWin AI tools", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/host-policy", "name": "CleanWin AI host policy", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/schema-registry", "name": "CleanWin schema registry", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/schema-validation", "name": "CleanWin schema validation", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/readiness", "name": "CleanWin AI readiness", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/self-test", "name": "CleanWin AI self-test", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/runbook", "name": "CleanWin AI runbook", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/workflow-router", "name": "CleanWin workflow router", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/environment-index", "name": "CleanWin environment index", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/workflow-decision", "name": "CleanWin workflow decision sample", "mimeType": "application/json"},
            {"uri": "cleanwin://ai/workflow-trace", "name": "CleanWin workflow trace contract", "mimeType": "application/json"},
            {"uri": "cleanwin://engineering/doctor", "name": "CleanWin engineering doctor", "mimeType": "application/json"},
            {"uri": "cleanwin://engineering/recovery-readiness", "name": "CleanWin recovery readiness", "mimeType": "application/json"},
            {"uri": "cleanwin://engineering/low-risk-cache-readiness", "name": "CleanWin low-risk cache readiness", "mimeType": "application/json"},
            {"uri": "cleanwin://engineering/operation-log-readiness", "name": "CleanWin operation log readiness", "mimeType": "application/json"},
            {"uri": "cleanwin://engineering/contract-exposure-matrix", "name": "CleanWin contract exposure matrix", "mimeType": "application/json"},
            {"uri": "cleanwin://inventory/installed-apps", "name": "CleanWin installed app inventory", "mimeType": "application/json"},
            {"uri": "cleanwin://inventory/windows", "name": "CleanWin Windows inventory baseline", "mimeType": "application/json"},
            {"uri": "cleanwin://plan/official-command-plan", "name": "CleanWin official command plan", "mimeType": "application/json"},
            {"uri": "cleanwin://inventory/debloat-privacy", "name": "CleanWin debloat privacy report", "mimeType": "application/json"},
            {"uri": "cleanwin://inventory/startup-services", "name": "CleanWin startup service inventory", "mimeType": "application/json"},
            {"uri": "cleanwin://plan/review-sample", "name": "CleanWin plan review sample", "mimeType": "application/json"},
        ]
        return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": resources}}
    if method == "resources/read":
        raw_resource_params = request.get("params")
        resource_params: Mapping[str, Any] = raw_resource_params if isinstance(raw_resource_params, Mapping) else {}
        uri = str(resource_params.get("uri") or "")
        try:
            payload = resource_payload(uri)
        except KeyError:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": f"Unknown resource: {uri}"}}
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload, sort_keys=True)}]},
        }
    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": request_id, "result": None}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def iter_input_payloads(stdin_text: str) -> list[str]:
    stripped = stdin_text.strip()
    if not stripped:
        return []
    if "\n" not in stripped:
        return [stripped]
    return [line for line in stripped.splitlines() if line.strip()]


def main() -> None:
    for stdin_line in sys.stdin:
        stop = False
        for payload in iter_input_payloads(stdin_line):
            request: Any = None
            try:
                request = json.loads(payload)
                response = handle_request(request)
            except json.JSONDecodeError:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            if response is not None:
                print(json.dumps(response, sort_keys=True), flush=True)
            if isinstance(request, Mapping) and request.get("method") == "shutdown":
                stop = True
                break
        if stop:
            break


def main_once() -> None:
    for payload in iter_input_payloads(sys.stdin.read()):
        try:
            request = json.loads(payload)
            response = handle_request(request)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            print(json.dumps(response, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
