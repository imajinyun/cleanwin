from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cleanwincli.ai_host_policy import evaluate_ai_host_tool_call
from cleanwincli.ai_schema import AI_TOOL_DEFINITIONS, CONFIRMATION_PHRASE, tool_catalog, validate_ai_schema, validate_tool_arguments
from cleanwincli.ai_versioning import schema_registry, schema_sample

ROOT = Path(__file__).resolve().parents[1]


class AIContractTests(unittest.TestCase):
    def run_cleanwin(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(ROOT / "cleanwin.py"), "--json", *args],
            cwd=ROOT,
            env=merged_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_ai_schema_validation_and_provider_parity(self) -> None:
        validation = validate_ai_schema()
        self.assertTrue(validation["valid"], validation)
        destructive = [tool for tool in AI_TOOL_DEFINITIONS if tool["risk"] == "destructive"]
        self.assertEqual([tool["name"] for tool in destructive], ["cleanwin_execute_plan"])
        self.assertFalse(destructive[0]["auto_call_allowed"])
        self.assertTrue(destructive[0]["requires_confirmation"])

    def test_schema_registry_includes_ai_host_critical_schemas(self) -> None:
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
            self.assertIn(required, names)

    def test_schema_samples_include_rule_metadata_and_review_details(self) -> None:
        inspect_sample = schema_sample("cleanwin.inspect.v1")
        self.assertEqual(inspect_sample["candidates"][0]["rule_id"], "dev-cache.npm.cache")
        self.assertEqual(inspect_sample["candidates"][0]["cache_owner"], "npm")
        self.assertIn("official_cleanup_command", inspect_sample["candidates"][0])
        self.assertIn("review_details", inspect_sample["findings"][0])

        plan_sample = schema_sample("cleanwin.plan.v1")
        self.assertEqual(plan_sample["candidates"][0]["rule_id"], "dev-cache.npm.cache")
        self.assertEqual(plan_sample["candidates"][0]["identity"]["schema"], "cleanwin.filesystem-identity.v1")

        execute_sample = schema_sample("cleanwin.execute.v1")
        self.assertEqual(execute_sample["schema"], "cleanwin.execute.v1")
        self.assertTrue(execute_sample["dry_run"])
        self.assertEqual(execute_sample["results"][0]["status"], "dry-run")
        self.assertIn("confirmation_token", execute_sample["confirmation"])

        doctor_sample = schema_sample("cleanwin.doctor.v1")
        self.assertEqual(doctor_sample["schema"], "cleanwin.doctor.v1")
        self.assertFalse(doctor_sample["destructive"])
        self.assertIn("recommended_commands", doctor_sample)

        review_sample = schema_sample("cleanwin.review.v1")
        self.assertEqual(review_sample["schema"], "cleanwin.review.v1")
        self.assertFalse(review_sample["destructive"])
        self.assertIn("execution_handoff", review_sample)
        self.assertIn("sensitive_exclusions", review_sample)

        argument_validation_sample = schema_sample("cleanwin.ai-tool-argument-validation.v1")
        self.assertEqual(argument_validation_sample["schema"], "cleanwin.ai-tool-argument-validation.v1")
        self.assertFalse(argument_validation_sample["valid"])

    def test_ai_tools_expose_rule_id_filter_for_inspect_and_plan(self) -> None:
        by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
        self.assertIn("rule_ids", by_name["cleanwin_inspect"]["parameters"]["properties"])
        self.assertIn("rule_ids", by_name["cleanwin_generate_plan"]["parameters"]["properties"])

    def test_schema_samples_cover_package_and_browser_cache_categories(self) -> None:
        inspect_sample = schema_sample("cleanwin.inspect.v1")
        self.assertIn("browser-cache", inspect_sample["categories"])
        self.assertIn("package-cache", inspect_sample["categories"])
        candidate_categories = {candidate["category"] for candidate in inspect_sample["candidates"]}
        self.assertIn("browser-cache", candidate_categories)
        self.assertIn("package-cache", candidate_categories)

    def test_ai_tools_expose_review_plan_tool(self) -> None:
        by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
        self.assertIn("cleanwin_review_plan", by_name)
        self.assertEqual(by_name["cleanwin_review_plan"]["risk"], "planning")
        self.assertFalse(by_name["cleanwin_review_plan"]["requires_confirmation"])
        self.assertIn("plan_file", by_name["cleanwin_review_plan"]["parameters"]["required"])

    def test_tool_argument_validation_rejects_invalid_types_and_unknown_fields(self) -> None:
        by_name = {tool["name"]: tool for tool in tool_catalog()["tools"]}
        validation = validate_tool_arguments(
            by_name["cleanwin_generate_plan"],
            {"categories": "dev-cache", "older_than_days": "0", "unexpected": True},
        )
        self.assertFalse(validation["valid"])
        self.assertIn("arguments.categories must be an array", validation["violations"])
        self.assertIn("arguments.older_than_days must be a number", validation["violations"])
        self.assertIn("arguments.unexpected is not allowed", validation["violations"])

        valid = validate_tool_arguments(by_name["cleanwin_generate_plan"], {"categories": ["dev-cache"], "older_than_days": 0})
        self.assertTrue(valid["valid"], valid)

    def test_host_policy_blocks_raw_command_and_missing_destructive_gates(self) -> None:
        tool = next(tool for tool in tool_catalog()["tools"] if tool["name"] == "cleanwin_execute_plan")
        denied = evaluate_ai_host_tool_call(tool=tool, arguments={"cmd": "remove things"}, source="test")
        self.assertFalse(denied["allowed"])
        codes = {reason["code"] for reason in denied["blocking_reasons"]}
        self.assertIn("RAW_COMMAND_ARGUMENT_DENIED", codes)
        self.assertIn("RECYCLE_MODE_REQUIRED", codes)
        self.assertIn("OPERATION_LOG_REQUIRED", codes)

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
        self.assertTrue(allowed["allowed"], allowed)

    def test_cli_ai_tools_and_host_policy_are_valid(self) -> None:
        tools = self.run_cleanwin("ai-tools")
        self.assertEqual(tools.returncode, 0, tools.stderr)
        self.assertEqual(json.loads(tools.stdout)["schema"], "cleanwin.ai-tools.v1")

        parity = self.run_cleanwin("ai-tools", "--provider", "parity")
        self.assertEqual(parity.returncode, 0, parity.stderr)
        self.assertTrue(json.loads(parity.stdout)["valid"])

        host_policy = self.run_cleanwin("host-policy", "--validate")
        self.assertEqual(host_policy.returncode, 0, host_policy.stderr)
        self.assertTrue(json.loads(host_policy.stdout)["valid"])

    def test_execute_requires_dry_run_confirmation_token(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            temp_root = tmp_path / "Temp"
            temp_root.mkdir()
            target = temp_root / "stale.tmp"
            target.write_text("x", encoding="utf-8")
            env = {"TEMP": str(temp_root), "TMP": str(temp_root), "CLEANWIN_TEST_MODE": "1"}
            plan_file = tmp_path / "plan.json"
            plan = self.run_cleanwin("plan", "--categories", "temp", "--older-than-days", "0", "--output", str(plan_file), env=env)
            self.assertEqual(plan.returncode, 0, plan.stderr)

            dry_run = self.run_cleanwin("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            confirmation = json.loads(dry_run.stdout)["confirmation"]

            denied = self.run_cleanwin(
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
            self.assertEqual(denied.returncode, 2)
            self.assertIn("confirmation phrase", json.loads(denied.stdout)["error"])
            self.assertTrue(target.exists())

            allowed = self.run_cleanwin(
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
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
