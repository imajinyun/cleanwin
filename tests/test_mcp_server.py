from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cleanwincli import __version__

ROOT = Path(__file__).resolve().parents[1]
MCP_MODULE = "cleanwincli.mcp_server"


def mcp_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["CLEANWIN_TEST_MODE"] = "1"
    return env


def mcp_request(request: dict) -> dict:
    proc = subprocess.Popen(
        [sys.executable, "-m", MCP_MODULE],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=mcp_env(),
    )
    stdout, stderr = proc.communicate(input=json.dumps(request), timeout=15)
    if not stdout.strip():
        raise RuntimeError(f"empty MCP stdout; stderr={stderr}")
    return json.loads(stdout.strip().splitlines()[0])


def persistent_mcp_request(request: dict) -> dict:
    proc = subprocess.Popen(
        [sys.executable, "-m", MCP_MODULE],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=mcp_env(),
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
        return json.loads(line)
    proc.kill()
    stdout, stderr = proc.communicate(timeout=5)
    raise RuntimeError(f"empty persistent MCP response; stdout={stdout}; stderr={stderr}")


class CleanWinMCPServerTests(unittest.TestCase):
    def test_initialize_and_tools_list(self) -> None:
        initialized = mcp_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(initialized["result"]["serverInfo"]["name"], "cleanwin-mcp")
        self.assertEqual(initialized["result"]["serverInfo"]["version"], __version__)

        response = mcp_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = response["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertIn("cleanwin_capabilities", names)
        self.assertIn("cleanwin_execute_plan", names)
        self.assertIn("cleanwin_review_plan", names)
        tool_by_name = {tool["name"]: tool for tool in tools}
        self.assertTrue(tool_by_name["cleanwin_capabilities"]["annotations"]["readOnlyHint"])
        self.assertTrue(tool_by_name["cleanwin_execute_plan"]["annotations"]["destructiveHint"])

    def test_resources_expose_ai_contracts(self) -> None:
        listed = mcp_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
        uris = {resource["uri"] for resource in listed["result"]["resources"]}
        self.assertIn("cleanwin://ai/host-policy", uris)
        self.assertIn("cleanwin://ai/schema-registry", uris)
        self.assertIn("cleanwin://ai/readiness", uris)
        self.assertIn("cleanwin://ai/self-test", uris)
        self.assertIn("cleanwin://ai/runbook", uris)
        self.assertIn("cleanwin://engineering/doctor", uris)
        self.assertIn("cleanwin://plan/review-sample", uris)

        read = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/read",
                "params": {"uri": "cleanwin://ai/host-policy"},
            }
        )
        payload = json.loads(read["result"]["contents"][0]["text"])
        self.assertEqual(payload["schema"], "cleanwin.ai-host-policy.v1")
        self.assertIn("cleanwin_execute_plan", payload["auto_call"]["deny"])

    def test_resources_readiness_self_test_and_runbook(self) -> None:
        for uri, schema in [
            ("cleanwin://ai/readiness", "cleanwin.ai-readiness.v1"),
            ("cleanwin://ai/self-test", "cleanwin.ai-self-test.v1"),
            ("cleanwin://ai/runbook", "cleanwin.ai-runbook.v1"),
            ("cleanwin://engineering/doctor", "cleanwin.doctor.v1"),
            ("cleanwin://plan/review-sample", "cleanwin.review.v1"),
        ]:
            with self.subTest(uri=uri):
                read = mcp_request(
                    {
                        "jsonrpc": "2.0",
                        "id": 40,
                        "method": "resources/read",
                        "params": {"uri": uri},
                    }
                )
                payload = json.loads(read["result"]["contents"][0]["text"])
                self.assertEqual(payload["schema"], schema)

    def test_resources_read_responds_before_persistent_stdin_eof(self) -> None:
        read = persistent_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 41,
                "method": "resources/read",
                "params": {"uri": "cleanwin://ai/runbook"},
            }
        )
        payload = json.loads(read["result"]["contents"][0]["text"])
        self.assertEqual(payload["schema"], "cleanwin.ai-runbook.v1")

    def test_tools_call_readonly_capabilities(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "cleanwin_capabilities", "arguments": {}},
            }
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["tool"], "cleanwin")
        self.assertEqual(result["governanceDecision"]["schema"], "cleanwin.ai-host-tool-call-decision.v1")
        self.assertTrue(result["governanceDecision"]["allowed"])

    def test_tools_call_inspect_supports_rule_id_filter(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 51,
                "method": "tools/call",
                "params": {
                    "name": "cleanwin_inspect",
                    "arguments": {"categories": ["dev-cache"], "rule_ids": ["dev-cache.npm.cache"], "older_than_days": 0, "max_items": 5},
                },
            }
        )
        result = response["result"]
        self.assertFalse(result["isError"], result)
        self.assertEqual(result["structuredContent"]["schema"], "cleanwin.inspect.v1")
        self.assertEqual(result["structuredContent"]["filters"]["rule_ids"], ["dev-cache.npm.cache"])

    def test_tools_call_review_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp_root = root / "Temp"
            temp_root.mkdir()
            (temp_root / "stale.tmp").write_text("x", encoding="utf-8")
            plan_file = root / "plan.json"
            env = mcp_env()
            env["TEMP"] = str(temp_root)
            env["TMP"] = str(temp_root)
            subprocess.run(
                [sys.executable, str(ROOT / "cleanwin.py"), "--json", "plan", "--categories", "temp", "--older-than-days", "0", "--output", str(plan_file)],
                cwd=ROOT,
                env=env,
                check=True,
                text=True,
                capture_output=True,
            )
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
                        "id": 52,
                        "method": "tools/call",
                        "params": {"name": "cleanwin_review_plan", "arguments": {"plan_file": str(plan_file), "require_plan_context": False}},
                    }
                ),
                timeout=15,
            )
            self.assertTrue(stdout.strip(), stderr)
            response = json.loads(stdout.strip().splitlines()[0])
            result = response["result"]
            self.assertFalse(result["isError"], result)
            self.assertEqual(result["structuredContent"]["schema"], "cleanwin.review.v1")
            self.assertIn("execution_handoff", result["structuredContent"])

    def test_tools_call_dry_run_plan_returns_candidate_results_and_token(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp_root = root / "Temp"
            temp_root.mkdir()
            stale_file = temp_root / "stale.tmp"
            stale_file.write_text("x", encoding="utf-8")
            plan_file = root / "plan.json"
            env = mcp_env()
            env["TEMP"] = str(temp_root)
            env["TMP"] = str(temp_root)
            subprocess.run(
                [sys.executable, str(ROOT / "cleanwin.py"), "--json", "plan", "--categories", "temp", "--older-than-days", "0", "--output", str(plan_file)],
                cwd=ROOT,
                env=env,
                check=True,
                text=True,
                capture_output=True,
            )
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
                        "id": 53,
                        "method": "tools/call",
                        "params": {"name": "cleanwin_dry_run_plan", "arguments": {"plan_file": str(plan_file)}},
                    }
                ),
                timeout=15,
            )
            self.assertTrue(stdout.strip(), stderr)
            response = json.loads(stdout.strip().splitlines()[0])
            result = response["result"]
            self.assertFalse(result["isError"], result)
            structured = result["structuredContent"]
            self.assertEqual(structured["schema"], "cleanwin.execute.v1")
            self.assertFalse(structured["executed"])
            self.assertEqual(structured["results"][0]["status"], "dry-run")
            self.assertEqual(structured["results"][0]["path"], str(stale_file))
            self.assertEqual(structured["summary"], {"result_count": 1, "status_counts": {"dry-run": 1}})
            self.assertIn("confirmation_token", structured["confirmation"])
            self.assertTrue(stale_file.exists())

    def test_raw_command_argument_denied_for_readonly_tool(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "cleanwin_capabilities", "arguments": {"raw_command": "del C:\\Windows"}},
            }
        )
        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["schema"], "cleanwin.mcp-tool-error.v1")
        self.assertEqual(result["governanceDecision"]["blocking_reasons"][0]["code"], "RAW_COMMAND_ARGUMENT_DENIED")

    def test_tool_call_rejects_schema_invalid_arguments(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 61,
                "method": "tools/call",
                "params": {"name": "cleanwin_inspect", "arguments": {"categories": "dev-cache", "older_than_days": "0"}},
            }
        )
        result = response["result"]
        self.assertTrue(result["isError"])
        validation = result["structuredContent"]["argument_validation"]
        self.assertEqual(validation["schema"], "cleanwin.ai-tool-argument-validation.v1")
        self.assertIn("arguments.categories must be an array", validation["violations"])
        self.assertIn("arguments.older_than_days must be a number", validation["violations"])
        self.assertTrue(result["governanceDecision"]["allowed"])

    def test_tool_call_rejects_unknown_non_raw_arguments(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 62,
                "method": "tools/call",
                "params": {"name": "cleanwin_capabilities", "arguments": {"unexpected": "ignored-before"}},
            }
        )
        result = response["result"]
        self.assertTrue(result["isError"])
        validation = result["structuredContent"]["argument_validation"]
        self.assertIn("arguments.unexpected is not allowed", validation["violations"])

    def test_tool_call_rejects_missing_required_arguments(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 63,
                "method": "tools/call",
                "params": {"name": "cleanwin_review_plan", "arguments": {}},
            }
        )
        result = response["result"]
        self.assertTrue(result["isError"])
        validation = result["structuredContent"]["argument_validation"]
        self.assertIn("arguments.plan_file is required", validation["violations"])

    def test_destructive_tool_missing_gates_denied(self) -> None:
        response = mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "cleanwin_execute_plan", "arguments": {"plan_file": "plan.json"}},
            }
        )
        result = response["result"]
        self.assertTrue(result["isError"])
        codes = {reason["code"] for reason in result["governanceDecision"]["blocking_reasons"]}
        self.assertIn("RECYCLE_MODE_REQUIRED", codes)
        self.assertIn("OPERATION_LOG_REQUIRED", codes)
        self.assertIn("HUMAN_CONFIRMATION_PHRASE_REQUIRED", codes)
        self.assertIn("CONFIRMATION_TOKEN_REQUIRED", codes)

    def test_unknown_method_returns_jsonrpc_error(self) -> None:
        response = mcp_request({"jsonrpc": "2.0", "id": 8, "method": "unknown/method"})
        self.assertEqual(response["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
