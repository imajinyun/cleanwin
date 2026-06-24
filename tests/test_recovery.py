from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from cleanwincli.recovery import RECOVERY_READINESS_SCHEMA, recovery_readiness_report

ROOT = Path(__file__).resolve().parents[1]


class RecoveryReadinessTests(unittest.TestCase):
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

    def test_recovery_readiness_is_non_destructive_and_declares_gates(self) -> None:
        report = recovery_readiness_report()

        self.assertEqual(report["schema"], RECOVERY_READINESS_SCHEMA)
        self.assertFalse(report["destructive"])
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["executes_system_commands"])
        self.assertTrue(report["ready_for_recovery_planning"])
        self.assertFalse(report["ready_for_system_execution"])
        self.assertTrue(report["execution_gate"]["requires_recovery_snapshot"])
        self.assertFalse(report["execution_gate"]["system_execution_enabled"])

    def test_recovery_readiness_declares_snapshot_specs(self) -> None:
        report = recovery_readiness_report()
        specs = {item["id"]: item for item in report["snapshot_specs"]}

        self.assertIn("system-restore-point", specs)
        self.assertIn("registry-export", specs)
        self.assertIn("service-state", specs)
        self.assertIn("scheduled-task-state", specs)
        self.assertIn("appx-inventory", specs)
        self.assertIn("installed-app-inventory", specs)
        self.assertTrue(all(not spec["executed_by_report"] for spec in specs.values()))
        self.assertIn("registry-change", specs["registry-export"]["required_before"])

    def test_cli_exposes_recovery_readiness(self) -> None:
        result = self.run_cleanwin("recovery-readiness")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema"], RECOVERY_READINESS_SCHEMA)
        self.assertFalse(payload["executes_system_commands"])

    def test_ai_tools_provider_exposes_recovery_readiness(self) -> None:
        result = self.run_cleanwin("ai-tools", "--provider", "recovery-readiness")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)

        self.assertEqual(payload["schema"], RECOVERY_READINESS_SCHEMA)
