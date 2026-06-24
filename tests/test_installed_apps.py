from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cleanwincli.installed_apps import INSTALLED_APP_INVENTORY_SCHEMA, installed_app_inventory_report

ROOT = Path(__file__).resolve().parents[1]


class InstalledAppInventoryTests(unittest.TestCase):
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

    def test_report_is_non_destructive_and_supports_non_windows(self) -> None:
        report = installed_app_inventory_report(raw_registry_entries=[], env={})

        self.assertEqual(report["schema"], INSTALLED_APP_INVENTORY_SCHEMA)
        self.assertFalse(report["destructive"])
        self.assertTrue(report["dry_run"])
        self.assertFalse(report["executes_system_commands"])
        self.assertEqual(report["summary"]["application_count"], 0)
        self.assertTrue(any(source["id"] == "winget" and not source["available"] for source in report["sources"]))
        self.assertTrue(any("does not uninstall" in item for item in report["non_goals"]))

    def test_registry_entries_are_normalized_without_uninstalling(self) -> None:
        report = installed_app_inventory_report(
            raw_registry_entries=[
                {
                    "DisplayName": "Slack",
                    "DisplayVersion": "4.40.0",
                    "Publisher": "Slack Technologies LLC",
                    "InstallLocation": r"C:\Users\tester\AppData\Local\slack",
                    "UninstallString": r"C:\Users\tester\AppData\Local\slack\Update.exe --uninstall",
                    "EstimatedSize": "250000",
                    "InstallDate": "20260620",
                    "key_path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Slack",
                }
            ],
            env={},
        )

        self.assertEqual(report["summary"]["registry_application_count"], 1)
        app = report["applications"][0]
        self.assertEqual(app["display_name"], "Slack")
        self.assertEqual(app["publisher"], "Slack Technologies LLC")
        self.assertTrue(app["uninstall_string_present"])
        self.assertEqual(app["estimated_size_kb"], 250000)
        correlation = next(item for item in report["leftover_correlations"] if item["rule_id"] == "app-leftovers.slack.cache")
        self.assertEqual(correlation["state"], "installed-application-present")
        self.assertEqual(correlation["recommendation"], "skip-leftover-cleanup-until-uninstalled")

    def test_filesystem_package_sources_and_leftover_correlation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "Local"
            profile = root / "Profile"
            program_data = root / "ProgramData"
            app_data = root / "Roaming"
            (profile / "scoop" / "apps" / "git").mkdir(parents=True)
            choco_dir = program_data / "chocolatey" / "lib" / "nodejs"
            choco_dir.mkdir(parents=True)
            (choco_dir / "nodejs.nuspec").write_text(
                "<package><metadata><id>nodejs</id><version>22.0.0</version></metadata></package>",
                encoding="utf-8",
            )
            (local / "Programs" / "PortableTool").mkdir(parents=True)
            slack_cache = app_data / "Slack" / "Cache"
            slack_cache.mkdir(parents=True)

            report = installed_app_inventory_report(
                raw_registry_entries=[],
                env={
                    "LOCALAPPDATA": str(local),
                    "USERPROFILE": str(profile),
                    "HOME": str(profile),
                    "PROGRAMDATA": str(program_data),
                    "APPDATA": str(app_data),
                },
            )

        apps = {(app["source"], app["display_name"]) for app in report["applications"]}
        self.assertIn(("scoop", "git"), apps)
        self.assertIn(("chocolatey", "nodejs"), apps)
        self.assertIn(("portable-location", "PortableTool"), apps)
        slack_correlation = next(item for item in report["leftover_correlations"] if item["rule_id"] == "app-leftovers.slack.cache")
        self.assertEqual(slack_correlation["state"], "potential-uninstall-leftover")
        self.assertEqual(slack_correlation["leftover_path"], str(slack_cache))

    def test_cli_and_ai_provider_expose_inventory(self) -> None:
        cli = self.run_cleanwin("installed-app-inventory")
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["schema"], INSTALLED_APP_INVENTORY_SCHEMA)

        provider = self.run_cleanwin("ai-tools", "--provider", "installed-app-inventory")
        self.assertEqual(provider.returncode, 0, provider.stderr)
        self.assertEqual(json.loads(provider.stdout)["schema"], INSTALLED_APP_INVENTORY_SCHEMA)
