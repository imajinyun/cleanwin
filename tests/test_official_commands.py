from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from cleanwincli.official_commands import OFFICIAL_COMMAND_PLAN_SCHEMA, official_command_plan_report

ROOT = Path(__file__).resolve().parents[1]


class OfficialCommandPlanTests(unittest.TestCase):
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

    def test_report_is_non_destructive_and_blocks_auto_execution(self) -> None:
        report = official_command_plan_report()

        self.assertEqual(report["schema"], OFFICIAL_COMMAND_PLAN_SCHEMA)
        self.assertFalse(report["destructive"])
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["executes_system_commands"])
        self.assertFalse(report["execution_gate"]["system_execution_enabled"])
        self.assertFalse(report["execution_gate"]["ai_auto_call_allowed"])
        self.assertTrue(any("does not execute DISM" in item for item in report["non_goals"]))
        self.assertEqual(report["summary"]["auto_executable_count"], 0)

    def test_report_covers_windows_owned_cleanup_surfaces(self) -> None:
        report = official_command_plan_report()
        by_id = {command["id"]: command for command in report["commands"]}

        self.assertIn("windows.component-cleanup.dism-startcomponentcleanup", by_id)
        self.assertIn("windows.update-cache.storage-sense", by_id)
        self.assertIn("windows.delivery-optimization.settings", by_id)
        self.assertIn("windows.wer.disk-cleanup", by_id)
        self.assertIn("windows.thumbnail-cache.disk-cleanup", by_id)
        self.assertIn("windows.defender.cleanup-settings", by_id)
        self.assertIn("windows.memory-dumps.storage-settings", by_id)
        self.assertIn("/StartComponentCleanup", by_id["windows.component-cleanup.dism-startcomponentcleanup"]["command"])
        self.assertIn("system-restore-point", by_id["windows.component-cleanup.dism-startcomponentcleanup"]["required_snapshots"])
        self.assertTrue(all(not command["executes_by_report"] for command in report["commands"]))
        self.assertTrue(all(not command["auto_executable"] for command in report["commands"]))

    def test_cli_and_ai_provider_expose_official_command_plan(self) -> None:
        cli = self.run_cleanwin("official-command-plan")
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["schema"], OFFICIAL_COMMAND_PLAN_SCHEMA)

        provider = self.run_cleanwin("ai-tools", "--provider", "official-command-plan")
        self.assertEqual(provider.returncode, 0, provider.stderr)
        self.assertEqual(json.loads(provider.stdout)["schema"], OFFICIAL_COMMAND_PLAN_SCHEMA)
