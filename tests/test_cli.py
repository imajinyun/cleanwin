from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from cleanwincli.core import validate_plan_payload
from cleanwincli.models import Candidate, Plan

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cleanwin(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)
        return subprocess.run(
            [sys.executable, str(ROOT / "cleanwin.py"), "--json", *args],
            cwd=ROOT,
            env=merged_env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_capabilities_reports_dry_run_and_single_exit(self) -> None:
        result = self.run_cleanwin("capabilities")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["default_dry_run"])
        self.assertEqual(payload["deletion_exit"], "cleanwincli.delete_ops.safe_delete")
        self.assertIn("browser-cache", payload["safe_categories"])
        self.assertIn("package-cache", payload["safe_categories"])
        self.assertIn("registry-clean", payload["never_auto_execute"])

    def test_inspect_temp_finds_sandbox_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp) / "Temp"
            temp_root.mkdir()
            stale_file = temp_root / "stale.tmp"
            stale_file.write_text("x", encoding="utf-8")
            result = self.run_cleanwin("inspect", "--categories", "temp", "--older-than-days", "0", env={"TEMP": str(temp_root), "TMP": str(temp_root)})
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["candidate_count"], 1)
            self.assertEqual(payload["candidates"][0]["path"], str(stale_file))
            self.assertEqual(payload["candidates"][0]["identity"]["schema"], "cleanwin.filesystem-identity.v1")

    def test_plan_validate_round_trip(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            temp_root = tmp_path / "Temp"
            temp_root.mkdir()
            (temp_root / "stale.tmp").write_text("x", encoding="utf-8")
            plan_file = tmp_path / "plan.json"
            env = {"TEMP": str(temp_root), "TMP": str(temp_root)}
            plan_result = self.run_cleanwin("plan", "--categories", "temp", "--older-than-days", "0", "--output", str(plan_file), env=env)
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
            validate_result = self.run_cleanwin("validate-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(validate_result.returncode, 0, validate_result.stderr)
            self.assertTrue(json.loads(validate_result.stdout)["valid"])

    def test_execute_plan_dry_run_reports_candidate_results_without_deleting(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            temp_root = tmp_path / "Temp"
            temp_root.mkdir()
            stale_file = temp_root / "stale.tmp"
            stale_file.write_text("x", encoding="utf-8")
            plan_file = tmp_path / "plan.json"
            env = {"TEMP": str(temp_root), "TMP": str(temp_root), "CLEANWIN_TEST_MODE": "1"}

            plan_result = self.run_cleanwin("plan", "--categories", "temp", "--older-than-days", "0", "--output", str(plan_file), env=env)
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
            dry_run_result = self.run_cleanwin("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(dry_run_result.returncode, 0, dry_run_result.stderr)

            payload = json.loads(dry_run_result.stdout)
            self.assertEqual(payload["schema"], "cleanwin.execute.v1")
            self.assertFalse(payload["executed"])
            self.assertTrue(payload["dry_run"])
            self.assertTrue(payload["validation"]["valid"])
            self.assertEqual(payload["results"], [{"status": "dry-run", "path": str(stale_file), "mode": "recycle"}])
            self.assertEqual(payload["summary"], {"result_count": 1, "status_counts": {"dry-run": 1}})
            self.assertIn("confirmation_token", payload["confirmation"])
            self.assertTrue(stale_file.exists())

    def test_review_plan_summarizes_execution_handoff(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            npm_cache = tmp_path / "npm-cache"
            npm_cache.mkdir()
            entry = npm_cache / "_cacache"
            entry.mkdir()
            (entry / "index").write_text("x", encoding="utf-8")
            plan_file = tmp_path / "plan.json"
            env = {"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path / "User")}
            plan_result = self.run_cleanwin(
                "plan",
                "--categories",
                "dev-cache",
                "--older-than-days",
                "0",
                "--rule-id",
                "dev-cache.npm.cache",
                "--output",
                str(plan_file),
                env=env,
            )
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)

            review_result = self.run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            review = json.loads(review_result.stdout)
            self.assertEqual(review["schema"], "cleanwin.review.v1")
            self.assertFalse(review["destructive"])
            self.assertTrue(review["validation"]["valid"])
            self.assertTrue(review["execution_handoff"]["requires_human_confirmation"])
            self.assertEqual(review["summary"]["candidate_count"], 1)
            self.assertEqual(review["rule_summary"][0]["rule_id"], "dev-cache.npm.cache")
            self.assertEqual(review["official_cleanup_commands"], ["npm cache clean --force"])
            self.assertIn("cleanwin_dry_run_plan", review["execution_handoff"]["required_predecessor_tools"])

    def test_review_plan_rejects_invalid_plan_exit_code(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            plan = Plan(
                candidates=[
                    Candidate(
                        path=str(target),
                        category="temp",
                        size_bytes=1,
                        reason="test",
                        safe_to_delete=True,
                        delete_mode="permanent",
                    )
                ],
                categories=["temp"],
            )
            plan_file = Path(tmp) / "invalid-plan.json"
            plan_file.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
            result = self.run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context")
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["validation"]["valid"])
            self.assertFalse(payload["execution_handoff"]["safe_to_execute"])

    def test_read_only_categories_do_not_create_candidates(self) -> None:
        result = self.run_cleanwin(
            "inspect",
            "--categories",
            "registry-report,startup-report,windows-report,large-files,docker-report,wsl-report,visual-studio-report,browser-cache-report",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["candidate_count"], 0)
        self.assertEqual(payload["summary"]["finding_count"], 8)
        self.assertTrue(all(not finding["safe_to_execute"] for finding in payload["findings"]))
        by_category = {finding["category"]: finding for finding in payload["findings"]}
        self.assertEqual(by_category["docker-report"]["rule_id"], "report.docker.manual-cleanup")
        self.assertEqual(by_category["wsl-report"]["owner"], "WSL")
        self.assertIn("browser profiles", by_category["browser-cache-report"]["detail"].lower())

    def test_dev_cache_candidates_include_rule_metadata_and_official_commands(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            npm_cache = root / "npm-cache"
            npm_cache.mkdir()
            entry = npm_cache / "_cacache"
            entry.mkdir()
            (entry / "index").write_text("x", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "dev-cache",
                "--older-than-days",
                "0",
                env={"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(root / "LocalAppData"), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["candidate_count"], 1)
            candidate = payload["candidates"][0]
            self.assertEqual(candidate["category"], "dev-cache")
            self.assertEqual(candidate["rule_id"], "dev-cache.npm.cache")
            self.assertEqual(candidate["cache_owner"], "npm")
            self.assertEqual(candidate["official_cleanup_command"], "npm cache clean --force")
            self.assertIn("regenerated", candidate["safe_to_delete_rationale"].lower())
            self.assertEqual(candidate["identity"]["schema"], "cleanwin.filesystem-identity.v1")

    def test_package_cache_scans_common_windows_package_manager_caches(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LocalAppData"
            winget_cache = local / "Microsoft" / "WinGet" / "Packages"
            winget_cache.mkdir(parents=True)
            (winget_cache / "installer.msix").write_text("winget", encoding="utf-8")
            scoop_cache = root / "User" / "scoop" / "cache"
            scoop_cache.mkdir(parents=True)
            (scoop_cache / "app.zip").write_text("scoop", encoding="utf-8")
            choco_cache = root / "ProgramData" / "chocolatey" / "cache"
            choco_cache.mkdir(parents=True)
            (choco_cache / "pkg.nupkg").write_text("choco", encoding="utf-8")
            uv_cache = local / "uv" / "cache"
            uv_cache.mkdir(parents=True)
            (uv_cache / "wheel.whl").write_text("uv", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "package-cache",
                "--older-than-days",
                "0",
                env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User"), "PROGRAMDATA": str(root / "ProgramData")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            rule_ids = {candidate["rule_id"] for candidate in payload["candidates"]}
            self.assertEqual(payload["summary"]["candidate_count"], 4)
            self.assertIn("package-cache.winget.packages", rule_ids)
            self.assertIn("package-cache.scoop.cache", rule_ids)
            self.assertIn("package-cache.chocolatey.cache", rule_ids)
            self.assertIn("package-cache.uv.cache", rule_ids)
            by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
            self.assertEqual(by_rule["package-cache.winget.packages"]["cache_owner"], "WinGet")
            self.assertIn("winget", by_rule["package-cache.winget.packages"]["official_cleanup_command"].lower())
            self.assertEqual(by_rule["package-cache.uv.cache"]["cache_owner"], "uv")

    def test_app_leftovers_scans_common_uninstalled_app_cache_and_logs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roaming = root / "Roaming"
            local = root / "LocalAppData"

            slack_cache = roaming / "Slack" / "Cache"
            slack_cache.mkdir(parents=True)
            (slack_cache / "entry").write_text("slack", encoding="utf-8")

            teams_logs = roaming / "Microsoft" / "Teams" / "logs"
            teams_logs.mkdir(parents=True)
            (teams_logs / "current.log").write_text("teams", encoding="utf-8")

            vscode_cache = roaming / "Code" / "CachedData"
            vscode_cache.mkdir(parents=True)
            (vscode_cache / "cache.bin").write_text("code", encoding="utf-8")

            jetbrains_logs = local / "JetBrains" / "PyCharm2024.1" / "log"
            jetbrains_logs.mkdir(parents=True)
            (jetbrains_logs / "idea.log").write_text("jetbrains", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "app-leftovers",
                "--older-than-days",
                "0",
                env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            paths = {candidate["path"] for candidate in payload["candidates"]}
            self.assertEqual(payload["summary"]["candidate_count"], 4)
            self.assertIn(str(slack_cache), paths)
            self.assertIn(str(teams_logs), paths)
            self.assertIn(str(vscode_cache), paths)
            self.assertIn(str(jetbrains_logs), paths)
            self.assertTrue(all(candidate["category"] == "app-leftovers" for candidate in payload["candidates"]))
            self.assertTrue(all(candidate["delete_mode"] == "recycle" for candidate in payload["candidates"]))

    def test_app_leftovers_skips_when_active_install_marker_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roaming = root / "Roaming"
            local = root / "LocalAppData"
            slack_cache = roaming / "Slack" / "Cache"
            slack_cache.mkdir(parents=True)
            (slack_cache / "entry").write_text("slack", encoding="utf-8")

            active_marker = local / "slack" / "slack.exe"
            active_marker.parent.mkdir(parents=True)
            active_marker.write_text("exe", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "app-leftovers",
                "--older-than-days",
                "0",
                env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["candidate_count"], 0)

    def test_app_leftovers_skips_globbed_active_install_markers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roaming = root / "Roaming"
            local = root / "LocalAppData"
            program_files = root / "ProgramFiles"

            discord_cache = roaming / "discord" / "Cache"
            discord_cache.mkdir(parents=True)
            (discord_cache / "entry").write_text("discord", encoding="utf-8")
            discord_marker = local / "Discord" / "app-1.2.3" / "Discord.exe"
            discord_marker.parent.mkdir(parents=True)
            discord_marker.write_text("exe", encoding="utf-8")

            jetbrains_log = local / "JetBrains" / "PyCharm2024.1" / "log"
            jetbrains_log.mkdir(parents=True)
            (jetbrains_log / "idea.log").write_text("jetbrains", encoding="utf-8")
            jetbrains_marker = program_files / "JetBrains" / "PyCharm 2024.1" / "bin" / "pycharm64.exe"
            jetbrains_marker.parent.mkdir(parents=True)
            jetbrains_marker.write_text("exe", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "app-leftovers",
                "--older-than-days",
                "0",
                env={
                    "APPDATA": str(roaming),
                    "LOCALAPPDATA": str(local),
                    "PROGRAMFILES": str(program_files),
                    "USERPROFILE": str(root / "User"),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            paths = {candidate["path"] for candidate in payload["candidates"]}
            self.assertNotIn(str(discord_cache), paths)
            self.assertNotIn(str(jetbrains_log), paths)

    def test_app_leftovers_scans_more_common_app_cache_and_logs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roaming = root / "Roaming"
            local = root / "LocalAppData"

            notion_cache = roaming / "Notion" / "Cache"
            notion_cache.mkdir(parents=True)
            (notion_cache / "entry").write_text("notion", encoding="utf-8")

            figma_logs = roaming / "Figma" / "logs"
            figma_logs.mkdir(parents=True)
            (figma_logs / "figma.log").write_text("figma", encoding="utf-8")

            obs_logs = roaming / "obs-studio" / "logs"
            obs_logs.mkdir(parents=True)
            (obs_logs / "obs.log").write_text("obs", encoding="utf-8")

            spotify_cache = local / "Spotify" / "Browser" / "Cache"
            spotify_cache.mkdir(parents=True)
            (spotify_cache / "entry").write_text("spotify", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "app-leftovers",
                "--older-than-days",
                "0",
                env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
            self.assertEqual(by_rule["app-leftovers.notion.cache"]["path"], str(notion_cache))
            self.assertEqual(by_rule["app-leftovers.figma.logs"]["path"], str(figma_logs))
            self.assertEqual(by_rule["app-leftovers.obs-studio.logs"]["path"], str(obs_logs))
            self.assertEqual(by_rule["app-leftovers.spotify.browser-cache"]["path"], str(spotify_cache))

    def test_app_leftovers_rule_filter_review_and_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roaming = root / "Roaming"
            local = root / "LocalAppData"
            slack_cache = roaming / "Slack" / "Cache"
            slack_cache.mkdir(parents=True)
            (slack_cache / "entry").write_text("slack", encoding="utf-8")
            vscode_cache = roaming / "Code" / "CachedData"
            vscode_cache.mkdir(parents=True)
            (vscode_cache / "cache.bin").write_text("code", encoding="utf-8")
            plan_file = root / "vscode-leftovers-plan.json"
            env = {"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User"), "CLEANWIN_TEST_MODE": "1"}

            plan_result = self.run_cleanwin(
                "plan",
                "--categories",
                "app-leftovers",
                "--older-than-days",
                "0",
                "--rule-id",
                "app-leftovers.vscode.cached-data",
                "--output",
                str(plan_file),
                env=env,
            )
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
            plan_payload = json.loads(plan_file.read_text(encoding="utf-8"))
            self.assertEqual(plan_payload["summary"]["candidate_count"], 1)
            self.assertEqual(plan_payload["candidates"][0]["path"], str(vscode_cache))
            self.assertEqual(plan_payload["candidates"][0]["rule_id"], "app-leftovers.vscode.cached-data")

            review_result = self.run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            review = json.loads(review_result.stdout)
            self.assertEqual(review["rule_ids"], ["app-leftovers.vscode.cached-data"])
            self.assertTrue(any("Uninstall Visual Studio Code" in command for command in review["cleanup_strategy"]["official_cleanup_commands"]))

            dry_run = self.run_cleanwin("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            dry_run_payload = json.loads(dry_run.stdout)
            self.assertEqual(dry_run_payload["results"], [{"status": "dry-run", "path": str(vscode_cache), "mode": "recycle"}])
            self.assertTrue(vscode_cache.exists())
            self.assertTrue(slack_cache.exists())

    def test_browser_cache_scans_cache_only_directories_without_profile_data(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LocalAppData"
            chrome_cache = local / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
            chrome_cache.mkdir(parents=True)
            (chrome_cache / "entry").write_text("chrome", encoding="utf-8")
            edge_code_cache = local / "Microsoft" / "Edge" / "User Data" / "Profile 1" / "Code Cache"
            edge_code_cache.mkdir(parents=True)
            (edge_code_cache / "js").write_text("edge", encoding="utf-8")
            cookies = local / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
            cookies.write_text("do-not-touch", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "browser-cache",
                "--older-than-days",
                "0",
                env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            paths = {candidate["path"] for candidate in payload["candidates"]}
            self.assertEqual(payload["summary"]["candidate_count"], 2)
            self.assertIn(str(chrome_cache), paths)
            self.assertIn(str(edge_code_cache), paths)
            self.assertNotIn(str(cookies), paths)
            self.assertTrue(all(candidate["category"] == "browser-cache" for candidate in payload["candidates"]))
            self.assertTrue(all("cookies" not in candidate["path"].lower() for candidate in payload["candidates"]))

    def test_browser_cache_discovers_additional_browser_profiles(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LocalAppData"
            chrome_profile_cache = local / "Google" / "Chrome" / "User Data" / "Profile 2" / "Cache"
            chrome_profile_cache.mkdir(parents=True)
            (chrome_profile_cache / "entry").write_text("chrome", encoding="utf-8")
            edge_default_cache = local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"
            edge_default_cache.mkdir(parents=True)
            (edge_default_cache / "entry").write_text("edge", encoding="utf-8")
            firefox_cache = local / "Mozilla" / "Firefox" / "Profiles" / "abcd1234.work" / "cache2"
            firefox_cache.mkdir(parents=True)
            (firefox_cache / "entry").write_text("firefox", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "browser-cache",
                "--older-than-days",
                "0",
                env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            paths = {candidate["path"] for candidate in payload["candidates"]}
            self.assertEqual(payload["summary"]["candidate_count"], 3)
            self.assertIn(str(chrome_profile_cache), paths)
            self.assertIn(str(edge_default_cache), paths)
            self.assertIn(str(firefox_cache), paths)

    def test_review_plan_for_browser_cache_reports_sensitive_exclusions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LocalAppData"
            chrome_cache = local / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
            chrome_cache.mkdir(parents=True)
            (chrome_cache / "entry").write_text("chrome", encoding="utf-8")
            (chrome_cache.parent / "Cookies").write_text("secret", encoding="utf-8")
            plan_file = root / "browser-plan.json"
            env = {"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")}
            plan_result = self.run_cleanwin("plan", "--categories", "browser-cache", "--older-than-days", "0", "--output", str(plan_file), env=env)
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)

            review_result = self.run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            review = json.loads(review_result.stdout)
            exclusions = review["sensitive_exclusions"]
            self.assertTrue(exclusions)
            self.assertEqual(exclusions[0]["category"], "browser-cache")
            excluded_patterns = "\n".join(item["pattern"] for item in exclusions[0]["excluded_patterns"])
            self.assertIn("Cookies", excluded_patterns)
            self.assertIn("Login Data", excluded_patterns)
            self.assertIn("Extensions", excluded_patterns)
            strategy = review["cleanup_strategy"]
            self.assertEqual(strategy["preferred"], "official-tool-or-app-ui")
            self.assertEqual(strategy["fallback"], "cleanwin-recycle-execution")
            self.assertTrue(strategy["requires_review"])
            self.assertIn("Use Chrome > Clear browsing data", strategy["official_cleanup_commands"])

    def test_rule_id_precise_plan_review_and_dry_run_for_package_cache(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LocalAppData"
            uv_cache = local / "uv" / "cache"
            uv_cache.mkdir(parents=True)
            (uv_cache / "wheel.whl").write_text("uv", encoding="utf-8")
            winget_cache = local / "Microsoft" / "WinGet" / "Packages"
            winget_cache.mkdir(parents=True)
            (winget_cache / "installer.msix").write_text("winget", encoding="utf-8")
            plan_file = root / "uv-plan.json"
            env = {"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User"), "CLEANWIN_TEST_MODE": "1"}

            plan_result = self.run_cleanwin(
                "plan",
                "--categories",
                "package-cache",
                "--older-than-days",
                "0",
                "--rule-id",
                "package-cache.uv.cache",
                "--output",
                str(plan_file),
                env=env,
            )
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
            plan_payload = json.loads(plan_file.read_text(encoding="utf-8"))
            self.assertEqual(plan_payload["summary"]["candidate_count"], 1)
            self.assertEqual(plan_payload["candidates"][0]["rule_id"], "package-cache.uv.cache")

            review_result = self.run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            review = json.loads(review_result.stdout)
            self.assertEqual(review["rule_ids"], ["package-cache.uv.cache"])
            self.assertIn("uv cache clean", review["cleanup_strategy"]["official_cleanup_commands"])

            dry_run = self.run_cleanwin("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            dry_run_payload = json.loads(dry_run.stdout)
            self.assertEqual(dry_run_payload["results"], [{"status": "dry-run", "path": str(uv_cache), "mode": "recycle"}])
            self.assertTrue(uv_cache.exists())
            self.assertTrue(winget_cache.exists())

    def test_inspect_rule_id_filters_dev_cache_candidates(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pip_cache = root / "LocalAppData" / "pip" / "Cache"
            pip_cache.mkdir(parents=True)
            (pip_cache / "http-v2").mkdir()
            ((pip_cache / "http-v2") / "entry").write_text("pip", encoding="utf-8")

            npm_cache = root / "npm-cache"
            npm_cache.mkdir()
            (npm_cache / "_cacache").mkdir()
            ((npm_cache / "_cacache") / "entry").write_text("npm", encoding="utf-8")

            result = self.run_cleanwin(
                "inspect",
                "--categories",
                "dev-cache",
                "--older-than-days",
                "0",
                "--rule-id",
                "dev-cache.npm.cache",
                env={"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(root / "LocalAppData"), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["candidate_count"], 1)
            self.assertEqual(payload["candidates"][0]["rule_id"], "dev-cache.npm.cache")

    def test_plan_rule_id_filters_candidates_before_write(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "LocalAppData"
            npm_cache = root / "npm-cache"
            npm_cache.mkdir()
            (npm_cache / "_cacache").mkdir()
            ((npm_cache / "_cacache") / "entry").write_text("npm", encoding="utf-8")
            pip_cache = local / "pip" / "Cache"
            pip_cache.mkdir(parents=True)
            (pip_cache / "wheels").mkdir()
            ((pip_cache / "wheels") / "entry").write_text("pip", encoding="utf-8")
            plan_file = root / "plan.json"

            result = self.run_cleanwin(
                "plan",
                "--categories",
                "dev-cache",
                "--older-than-days",
                "0",
                "--rule-id",
                "dev-cache.pip.cache",
                "--output",
                str(plan_file),
                env={"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(plan_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["candidate_count"], 1)
            self.assertEqual(payload["candidates"][0]["rule_id"], "dev-cache.pip.cache")

    def test_read_only_findings_include_structured_review_details(self) -> None:
        result = self.run_cleanwin("inspect", "--categories", "docker-report")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        finding = payload["findings"][0]
        self.assertIn("review_details", finding)
        self.assertIn("suggested_paths", finding["review_details"])
        self.assertIn("risk_notes", finding["review_details"])
        self.assertIn("manual_review_steps", finding["review_details"])

    def test_validate_plan_rejects_permanent_and_admin_candidates(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            permanent_plan = Plan(
                candidates=[
                    Candidate(
                        path=str(target),
                        category="temp",
                        size_bytes=1,
                        reason="test",
                        safe_to_delete=True,
                        delete_mode="permanent",
                    )
                ],
                categories=["temp"],
            )
            permanent_raw = permanent_plan.to_dict()
            permanent_validation = validate_plan_payload(permanent_plan, permanent_raw, require_context=False)
            self.assertFalse(permanent_validation["valid"])
            self.assertIn("Unsupported plan delete_mode", "\n".join(permanent_validation["errors"]))

            admin_plan = Plan(
                candidates=[replace(permanent_plan.candidates[0], delete_mode="recycle", requires_admin=True)],
                categories=["temp"],
            )
            admin_raw = admin_plan.to_dict()
            admin_validation = validate_plan_payload(admin_plan, admin_raw, require_context=False)
            self.assertFalse(admin_validation["valid"])
            self.assertIn("Admin-scoped candidate", "\n".join(admin_validation["errors"]))


if __name__ == "__main__":
    unittest.main()
