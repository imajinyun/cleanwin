from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from cleanwincli import __version__
from cleanwincli.ai_readiness import ai_readiness_report, validate_ai_readiness
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.ai_versioning import schema_registry
from cleanwincli.core import doctor_report

ROOT = Path(__file__).resolve().parents[1]


class AIReadinessTests(unittest.TestCase):
    def run_cleanwin(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run(
            [sys.executable, str(ROOT / "cleanwin.py"), "--json", *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_ai_readiness_is_valid_and_registers_critical_schemas(self) -> None:
        report = ai_readiness_report()
        self.assertEqual(report["schema"], "cleanwin.ai-readiness.v1")
        self.assertTrue(report["ready_for_ai_host"], report)
        self.assertTrue(report["ready_for_mcp"], report)
        validation = validate_ai_readiness(report)
        self.assertTrue(validation["valid"], validation)

        names = {entry["name"] for entry in schema_registry()["entries"]}
        for required in [
            "cleanwin.ai-readiness.v1",
            "cleanwin.ai-readiness-validation.v1",
            "cleanwin.ai-self-test.v1",
            "cleanwin.ai-runbook.v1",
        ]:
            self.assertIn(required, names)

    def test_ai_self_test_passes_expected_policy_checks(self) -> None:
        report = ai_self_test_report()
        self.assertEqual(report["schema"], "cleanwin.ai-self-test.v1")
        self.assertTrue(report["passed"], report)
        test_names = {test["name"] for test in report["tests"]}
        self.assertIn("raw_command_denied", test_names)
        self.assertIn("destructive_missing_gates_denied", test_names)
        self.assertIn("destructive_all_gates_allowed_by_policy", test_names)

    def test_ai_runbook_documents_safe_execution_gates(self) -> None:
        report = ai_runbook_report()
        self.assertEqual(report["schema"], "cleanwin.ai-runbook.v1")
        tools = [step["tool"] for step in report["workflow"]]
        self.assertEqual(tools[-1], "cleanwin_execute_plan")
        self.assertTrue(report["workflow"][-1]["destructive"])
        required_args = report["required_execution_arguments"]
        self.assertEqual(required_args["delete_mode"], "recycle")
        self.assertTrue(required_args["require_plan_context"])

    def test_cli_exposes_readiness_self_test_and_runbook(self) -> None:
        readiness = self.run_cleanwin("ai-readiness")
        self.assertEqual(readiness.returncode, 0, readiness.stderr)
        self.assertTrue(json.loads(readiness.stdout)["ready_for_ai_host"])

        readiness_validation = self.run_cleanwin("ai-readiness", "--validate")
        self.assertEqual(readiness_validation.returncode, 0, readiness_validation.stderr)
        self.assertTrue(json.loads(readiness_validation.stdout)["valid"])

        self_test = self.run_cleanwin("ai-self-test")
        self.assertEqual(self_test.returncode, 0, self_test.stderr)
        self.assertTrue(json.loads(self_test.stdout)["passed"])

        runbook = self.run_cleanwin("ai-runbook")
        self.assertEqual(runbook.returncode, 0, runbook.stderr)
        self.assertEqual(json.loads(runbook.stdout)["schema"], "cleanwin.ai-runbook.v1")

        doctor = self.run_cleanwin("doctor")
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        doctor_payload = json.loads(doctor.stdout)
        self.assertEqual(doctor_payload["schema"], "cleanwin.doctor.v1")
        self.assertTrue(doctor_payload["ready"], doctor_payload)
        self.assertFalse(doctor_payload["destructive"])

    def test_doctor_report_checks_static_safety_and_contracts(self) -> None:
        report = doctor_report()
        self.assertEqual(report["schema"], "cleanwin.doctor.v1")
        self.assertTrue(report["ready"], report)
        self.assertFalse(report["destructive"])
        check_ids = {check["id"] for check in report["checks"]}
        self.assertIn("single_destructive_exit", check_ids)
        self.assertIn("delete_primitives_owned_by_delete_ops", check_ids)
        self.assertIn("ai_contracts_valid", check_ids)
        self.assertIn("version_consistency", check_ids)
        version_check = next(check for check in report["checks"] if check["id"] == "version_consistency")
        self.assertTrue(version_check["passed"], version_check)
        self.assertEqual(version_check["evidence"]["package_version"], __version__)
        self.assertEqual(version_check["evidence"]["pyproject_version"], __version__)
        self.assertEqual(version_check["evidence"]["capabilities_version"], __version__)
        self.assertIn(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"], report["recommended_commands"])
        self.assertIn(["python3", "-m", "ruff", "check", "cleanwin.py", "cleanwincli", "tests"], report["recommended_commands"])
        self.assertIn(["python3", "-m", "mypy", "cleanwin.py", "cleanwincli", "tests"], report["recommended_commands"])
        self.assertIn(["python3", "-m", "build", "--sdist", "--wheel"], report["recommended_commands"])
        self.assertIn(["make", "docs-smoke"], report["recommended_commands"])
        self.assertIn(["make", "ai-smoke"], report["recommended_commands"])
        self.assertIn(["make", "mcp-smoke"], report["recommended_commands"])
        self.assertIn(["make", "version-smoke"], report["recommended_commands"])
        self.assertIn(["make", "clean"], report["recommended_commands"])
        self.assertIn(["make", "quality"], report["recommended_commands"])

    def test_ai_tools_provider_aliases_readiness_reports(self) -> None:
        for provider, schema in [
            ("readiness", "cleanwin.ai-readiness.v1"),
            ("self-test", "cleanwin.ai-self-test.v1"),
            ("runbook", "cleanwin.ai-runbook.v1"),
            ("doctor", "cleanwin.doctor.v1"),
        ]:
            with self.subTest(provider=provider):
                result = self.run_cleanwin("ai-tools", "--provider", provider)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["schema"], schema)


if __name__ == "__main__":
    unittest.main()
