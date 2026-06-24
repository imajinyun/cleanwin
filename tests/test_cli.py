from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from cleanwincli.core import validate_plan_payload
from cleanwincli.models import Candidate, Plan

JSONPayload = dict[str, Any]
RunCleanWin = Callable[..., subprocess.CompletedProcess[str]]
CleanWinResultJSON = Callable[[subprocess.CompletedProcess[str]], JSONPayload]
CleanWinJSON = Callable[..., JSONPayload]
CleanWinPlanFile = Callable[..., JSONPayload]


def test_capabilities_reports_dry_run_and_single_exit(cleanwin_json: CleanWinJSON) -> None:
    payload = cleanwin_json("capabilities")
    assert payload["default_dry_run"]
    assert payload["deletion_exit"] == "cleanwincli.delete_ops.safe_delete"
    assert "browser-cache" in payload["safe_categories"]
    assert "package-cache" in payload["safe_categories"]
    assert "registry-clean" in payload["never_auto_execute"]

def test_inspect_temp_finds_sandbox_candidate(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    temp_root = tmp_path / "Temp"
    temp_root.mkdir()
    stale_file = temp_root / "stale.tmp"
    stale_file.write_text("x", encoding="utf-8")
    payload = cleanwin_json("inspect", "--categories", "temp", "--older-than-days", "0", env={"TEMP": str(temp_root), "TMP": str(temp_root)})
    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["path"] == str(stale_file)
    assert payload["candidates"][0]["identity"]["schema"] == "cleanwin.filesystem-identity.v1"

def test_plan_validate_round_trip(tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, cleanwin_json: CleanWinJSON) -> None:
    temp_root = tmp_path / "Temp"
    temp_root.mkdir()
    (temp_root / "stale.tmp").write_text("x", encoding="utf-8")
    plan_file = tmp_path / "plan.json"
    env = {"TEMP": str(temp_root), "TMP": str(temp_root)}
    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)
    assert cleanwin_json("validate-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)["valid"]

def test_execute_plan_dry_run_reports_candidate_results_without_deleting(
    tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, cleanwin_json: CleanWinJSON
) -> None:
    temp_root = tmp_path / "Temp"
    temp_root.mkdir()
    stale_file = temp_root / "stale.tmp"
    stale_file.write_text("x", encoding="utf-8")
    plan_file = tmp_path / "plan.json"
    env = {"TEMP": str(temp_root), "TMP": str(temp_root), "CLEANWIN_TEST_MODE": "1"}

    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)
    payload = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert payload["schema"] == "cleanwin.execute.v1"
    assert not payload["executed"]
    assert payload["dry_run"]
    assert payload["validation"]["valid"]
    assert payload["results"] == [{"status": "dry-run", "path": str(stale_file), "mode": "recycle"}]
    assert payload["summary"] == {"result_count": 1, "status_counts": {"dry-run": 1}}
    assert "confirmation_token" in payload["confirmation"]
    assert stale_file.exists()

def test_review_plan_summarizes_execution_handoff(
    tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, cleanwin_json: CleanWinJSON
) -> None:
    npm_cache = tmp_path / "npm-cache"
    npm_cache.mkdir()
    entry = npm_cache / "_cacache"
    entry.mkdir()
    (entry / "index").write_text("x", encoding="utf-8")
    plan_file = tmp_path / "plan.json"
    env = {"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(tmp_path / "LocalAppData"), "USERPROFILE": str(tmp_path / "User")}
    cleanwin_plan_file(
        plan_file,
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        "--rule-id",
        "dev-cache.npm.cache",
        env=env,
    )

    review = cleanwin_json("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert review["schema"] == "cleanwin.review.v1"
    assert not review["destructive"]
    assert review["validation"]["valid"]
    assert review["execution_handoff"]["requires_human_confirmation"]
    assert review["summary"]["candidate_count"] == 1
    assert review["rule_summary"][0]["rule_id"] == "dev-cache.npm.cache"
    assert review["official_cleanup_commands"] == ["npm cache clean --force"]
    assert "cleanwin_dry_run_plan" in review["execution_handoff"]["required_predecessor_tools"]

def test_review_plan_rejects_invalid_plan_exit_code(
    tmp_path: Path, run_cleanwin: RunCleanWin, cleanwin_result_json: CleanWinResultJSON
) -> None:
    target = tmp_path / "candidate.tmp"
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
    plan_file = tmp_path / "invalid-plan.json"
    plan_file.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    result = run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context")
    assert result.returncode == 2
    payload = cleanwin_result_json(result)
    assert not payload["validation"]["valid"]
    assert not payload["execution_handoff"]["safe_to_execute"]

def test_read_only_categories_do_not_create_candidates(cleanwin_json: CleanWinJSON) -> None:
    payload = cleanwin_json(
        "inspect",
        "--categories",
        "registry-report,startup-report,windows-report,large-files,docker-report,wsl-report,visual-studio-report,browser-cache-report",
    )
    assert payload["summary"]["candidate_count"] == 0
    assert payload["summary"]["finding_count"] == 8
    assert all(not finding["safe_to_execute"] for finding in payload["findings"])
    by_category = {finding["category"]: finding for finding in payload["findings"]}
    assert by_category["docker-report"]["rule_id"] == "report.docker.manual-cleanup"
    assert by_category["wsl-report"]["owner"] == "WSL"
    assert "browser profiles" in by_category["browser-cache-report"]["detail"].lower()

def test_dev_cache_candidates_include_rule_metadata_and_official_commands(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    npm_cache = root / "npm-cache"
    npm_cache.mkdir()
    entry = npm_cache / "_cacache"
    entry.mkdir()
    (entry / "index").write_text("x", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        env={"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(root / "LocalAppData"), "USERPROFILE": str(root / "User")},
    )
    assert payload["summary"]["candidate_count"] == 1
    candidate = payload["candidates"][0]
    assert candidate["category"] == "dev-cache"
    assert candidate["rule_id"] == "dev-cache.npm.cache"
    assert candidate["cache_owner"] == "npm"
    assert candidate["official_cleanup_command"] == "npm cache clean --force"
    assert "regenerated" in candidate["safe_to_delete_rationale"].lower()
    assert candidate["identity"]["schema"] == "cleanwin.filesystem-identity.v1"

def test_dev_cache_scans_expanded_python_and_node_tool_caches(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    user = root / "User"
    poetry_cache = local / "pypoetry" / "Cache"
    poetry_cache.mkdir(parents=True)
    (poetry_cache / "artifact.whl").write_text("poetry", encoding="utf-8")
    pipenv_cache = local / "pipenv" / "Cache"
    pipenv_cache.mkdir(parents=True)
    (pipenv_cache / "resolver.json").write_text("pipenv", encoding="utf-8")
    pre_commit_cache = user / ".cache" / "pre-commit"
    pre_commit_cache.mkdir(parents=True)
    (pre_commit_cache / "repo.db").write_text("precommit", encoding="utf-8")
    node_gyp_cache = local / "node-gyp" / "Cache"
    node_gyp_cache.mkdir(parents=True)
    (node_gyp_cache / "headers.tar.gz").write_text("node-gyp", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(user)},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["dev-cache.poetry.cache"]["cache_owner"] == "Poetry"
    assert by_rule["dev-cache.pipenv.cache"]["cache_owner"] == "Pipenv"
    assert by_rule["dev-cache.pre-commit.cache"]["cache_owner"] == "pre-commit"
    assert by_rule["dev-cache.node-gyp.cache"]["cache_owner"] == "node-gyp"
    assert "poetry cache clear" in by_rule["dev-cache.poetry.cache"]["official_cleanup_command"]

def test_package_cache_scans_common_windows_package_manager_caches(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
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

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "package-cache",
        "--older-than-days",
        "0",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User"), "PROGRAMDATA": str(root / "ProgramData")},
    )
    rule_ids = {candidate["rule_id"] for candidate in payload["candidates"]}
    assert payload["summary"]["candidate_count"] == 4
    assert "package-cache.winget.packages" in rule_ids
    assert "package-cache.scoop.cache" in rule_ids
    assert "package-cache.chocolatey.cache" in rule_ids
    assert "package-cache.uv.cache" in rule_ids
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["package-cache.winget.packages"]["cache_owner"] == "WinGet"
    assert "winget" in by_rule["package-cache.winget.packages"]["official_cleanup_command"].lower()
    assert by_rule["package-cache.uv.cache"]["cache_owner"] == "uv"

def test_app_leftovers_scans_common_uninstalled_app_cache_and_logs(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
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

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert payload["summary"]["candidate_count"] == 4
    assert str(slack_cache) in paths
    assert str(teams_logs) in paths
    assert str(vscode_cache) in paths
    assert str(jetbrains_logs) in paths
    assert all(candidate["category"] == "app-leftovers" for candidate in payload["candidates"])
    assert all(candidate["delete_mode"] == "recycle" for candidate in payload["candidates"])

def test_app_leftovers_scans_expanded_electron_gpu_caches(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    teams_gpu_cache = roaming / "Microsoft" / "Teams" / "GPUCache"
    teams_gpu_cache.mkdir(parents=True)
    (teams_gpu_cache / "shader.bin").write_text("teams", encoding="utf-8")
    discord_gpu_cache = roaming / "discord" / "GPUCache"
    discord_gpu_cache.mkdir(parents=True)
    (discord_gpu_cache / "shader.bin").write_text("discord", encoding="utf-8")
    vscode_gpu_cache = roaming / "Code" / "GPUCache"
    vscode_gpu_cache.mkdir(parents=True)
    (vscode_gpu_cache / "shader.bin").write_text("code", encoding="utf-8")
    vscode_user_data = roaming / "Code" / "User"
    vscode_user_data.mkdir(parents=True)
    (vscode_user_data / "settings.json").write_text("{}", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["app-leftovers.teams-classic.gpu-cache"]["path"] == str(teams_gpu_cache)
    assert by_rule["app-leftovers.discord.gpu-cache"]["path"] == str(discord_gpu_cache)
    assert by_rule["app-leftovers.vscode.gpu-cache"]["path"] == str(vscode_gpu_cache)
    assert str(vscode_user_data) not in {candidate["path"] for candidate in payload["candidates"]}

def test_app_leftovers_skips_when_active_install_marker_exists(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    slack_cache = roaming / "Slack" / "Cache"
    slack_cache.mkdir(parents=True)
    (slack_cache / "entry").write_text("slack", encoding="utf-8")

    active_marker = local / "slack" / "slack.exe"
    active_marker.parent.mkdir(parents=True)
    active_marker.write_text("exe", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    assert payload["summary"]["candidate_count"] == 0

def test_app_leftovers_skips_globbed_active_install_markers(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
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

    payload = cleanwin_json(
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
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert str(discord_cache) not in paths
    assert str(jetbrains_log) not in paths

def test_app_leftovers_scans_more_common_app_cache_and_logs(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
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

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["app-leftovers.notion.cache"]["path"] == str(notion_cache)
    assert by_rule["app-leftovers.figma.logs"]["path"] == str(figma_logs)
    assert by_rule["app-leftovers.obs-studio.logs"]["path"] == str(obs_logs)
    assert by_rule["app-leftovers.spotify.browser-cache"]["path"] == str(spotify_cache)

def test_app_leftovers_scans_additional_vendor_cache_and_logs(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    adobe_logs = local / "Adobe" / "Creative Cloud" / "Logs"
    adobe_logs.mkdir(parents=True)
    (adobe_logs / "acc.log").write_text("adobe", encoding="utf-8")
    office_telemetry = local / "Microsoft" / "Office" / "16.0" / "Telemetry"
    office_telemetry.mkdir(parents=True)
    (office_telemetry / "telemetry.log").write_text("office", encoding="utf-8")
    steam_cache = local / "Steam" / "htmlcache"
    steam_cache.mkdir(parents=True)
    (steam_cache / "entry").write_text("steam", encoding="utf-8")
    epic_cache = local / "EpicGamesLauncher" / "Saved" / "webcache"
    epic_cache.mkdir(parents=True)
    (epic_cache / "entry").write_text("epic", encoding="utf-8")
    battlenet_cache = local / "Battle.net" / "Cache"
    battlenet_cache.mkdir(parents=True)
    (battlenet_cache / "entry").write_text("battle", encoding="utf-8")
    nvidia_cache = local / "NVIDIA" / "DXCache"
    nvidia_cache.mkdir(parents=True)
    (nvidia_cache / "shader.bin").write_text("nvidia", encoding="utf-8")
    amd_cache = local / "AMD" / "DxCache"
    amd_cache.mkdir(parents=True)
    (amd_cache / "shader.bin").write_text("amd", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(root / "Roaming"), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["app-leftovers.adobe.creative-cloud.logs"]["path"] == str(adobe_logs)
    assert by_rule["app-leftovers.office.telemetry-logs"]["path"] == str(office_telemetry)
    assert by_rule["app-leftovers.steam.htmlcache"]["path"] == str(steam_cache)
    assert by_rule["app-leftovers.epic.webcache"]["path"] == str(epic_cache)
    assert by_rule["app-leftovers.battlenet.cache"]["path"] == str(battlenet_cache)
    assert by_rule["app-leftovers.nvidia.dxcache"]["path"] == str(nvidia_cache)
    assert by_rule["app-leftovers.amd.dxcache"]["path"] == str(amd_cache)

def test_app_leftovers_skips_additional_vendor_rules_when_active_marker_exists(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"
    steam_cache = local / "Steam" / "htmlcache"
    steam_cache.mkdir(parents=True)
    (steam_cache / "entry").write_text("steam", encoding="utf-8")
    steam_marker = program_files / "Steam" / "steam.exe"
    steam_marker.parent.mkdir(parents=True)
    steam_marker.write_text("exe", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={
            "APPDATA": str(root / "Roaming"),
            "LOCALAPPDATA": str(local),
            "PROGRAMFILES": str(program_files),
            "USERPROFILE": str(root / "User"),
        },
    )
    assert "app-leftovers.steam.htmlcache" not in {candidate["rule_id"] for candidate in payload["candidates"]}

def test_app_leftovers_rule_filter_review_and_dry_run(
    tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
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

    plan_payload = cleanwin_plan_file(
        plan_file,
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        "--rule-id",
        "app-leftovers.vscode.cached-data",
        env=env,
    )
    assert plan_payload["summary"]["candidate_count"] == 1
    assert plan_payload["candidates"][0]["path"] == str(vscode_cache)
    assert plan_payload["candidates"][0]["rule_id"] == "app-leftovers.vscode.cached-data"

    review = cleanwin_json("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert review["rule_ids"] == ["app-leftovers.vscode.cached-data"]
    assert any("Uninstall Visual Studio Code" in command for command in review["cleanup_strategy"]["official_cleanup_commands"])

    dry_run_payload = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert dry_run_payload["results"] == [{"status": "dry-run", "path": str(vscode_cache), "mode": "recycle"}]
    assert vscode_cache.exists()
    assert slack_cache.exists()

def test_browser_cache_scans_cache_only_directories_without_profile_data(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    chrome_cache = local / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    chrome_cache.mkdir(parents=True)
    (chrome_cache / "entry").write_text("chrome", encoding="utf-8")
    edge_code_cache = local / "Microsoft" / "Edge" / "User Data" / "Profile 1" / "Code Cache"
    edge_code_cache.mkdir(parents=True)
    (edge_code_cache / "js").write_text("edge", encoding="utf-8")
    cookies = local / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
    cookies.write_text("do-not-touch", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "browser-cache",
        "--older-than-days",
        "0",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert payload["summary"]["candidate_count"] == 2
    assert str(chrome_cache) in paths
    assert str(edge_code_cache) in paths
    assert str(cookies) not in paths
    assert all(candidate["category"] == "browser-cache" for candidate in payload["candidates"])
    assert all("cookies" not in candidate["path"].lower() for candidate in payload["candidates"])

def test_browser_cache_discovers_additional_browser_profiles(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
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

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "browser-cache",
        "--older-than-days",
        "0",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert payload["summary"]["candidate_count"] == 3
    assert str(chrome_profile_cache) in paths
    assert str(edge_default_cache) in paths
    assert str(firefox_cache) in paths

def test_browser_cache_discovers_brave_profile_caches(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    brave_cache = local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache"
    brave_cache.mkdir(parents=True)
    (brave_cache / "entry").write_text("brave", encoding="utf-8")
    brave_code_cache = local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Profile 1" / "Code Cache"
    brave_code_cache.mkdir(parents=True)
    (brave_code_cache / "js").write_text("brave", encoding="utf-8")
    cookies = brave_cache.parent / "Cookies"
    cookies.write_text("do-not-touch", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "browser-cache",
        "--older-than-days",
        "0",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["browser-cache.brave.cache"]["path"] == str(brave_cache)
    assert by_rule["browser-cache.brave.code-cache"]["path"] == str(brave_code_cache)
    assert str(cookies) not in {candidate["path"] for candidate in payload["candidates"]}

def test_review_plan_for_browser_cache_reports_sensitive_exclusions(
    tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    chrome_cache = local / "Google" / "Chrome" / "User Data" / "Default" / "Cache"
    chrome_cache.mkdir(parents=True)
    (chrome_cache / "entry").write_text("chrome", encoding="utf-8")
    (chrome_cache.parent / "Cookies").write_text("secret", encoding="utf-8")
    plan_file = root / "browser-plan.json"
    env = {"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")}
    cleanwin_plan_file(plan_file, "--categories", "browser-cache", "--older-than-days", "0", env=env)

    review = cleanwin_json("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    exclusions = review["sensitive_exclusions"]
    assert exclusions
    assert exclusions[0]["category"] == "browser-cache"
    excluded_patterns = "\n".join(item["pattern"] for item in exclusions[0]["excluded_patterns"])
    assert "Cookies" in excluded_patterns
    assert "Login Data" in excluded_patterns
    assert "Extensions" in excluded_patterns
    strategy = review["cleanup_strategy"]
    assert strategy["preferred"] == "official-tool-or-app-ui"
    assert strategy["fallback"] == "cleanwin-recycle-execution"
    assert strategy["requires_review"]
    assert "Use Chrome > Clear browsing data" in strategy["official_cleanup_commands"]

def test_rule_id_precise_plan_review_and_dry_run_for_package_cache(
    tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    uv_cache = local / "uv" / "cache"
    uv_cache.mkdir(parents=True)
    (uv_cache / "wheel.whl").write_text("uv", encoding="utf-8")
    winget_cache = local / "Microsoft" / "WinGet" / "Packages"
    winget_cache.mkdir(parents=True)
    (winget_cache / "installer.msix").write_text("winget", encoding="utf-8")
    plan_file = root / "uv-plan.json"
    env = {"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User"), "CLEANWIN_TEST_MODE": "1"}

    plan_payload = cleanwin_plan_file(
        plan_file,
        "--categories",
        "package-cache",
        "--older-than-days",
        "0",
        "--rule-id",
        "package-cache.uv.cache",
        env=env,
    )
    assert plan_payload["summary"]["candidate_count"] == 1
    assert plan_payload["candidates"][0]["rule_id"] == "package-cache.uv.cache"

    review = cleanwin_json("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert review["rule_ids"] == ["package-cache.uv.cache"]
    assert "uv cache clean" in review["cleanup_strategy"]["official_cleanup_commands"]

    dry_run_payload = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert dry_run_payload["results"] == [{"status": "dry-run", "path": str(uv_cache), "mode": "recycle"}]
    assert uv_cache.exists()
    assert winget_cache.exists()

def test_package_cache_scans_additional_developer_package_caches(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    vcpkg_downloads = local / "vcpkg" / "downloads"
    vcpkg_downloads.mkdir(parents=True)
    (vcpkg_downloads / "archive.zip").write_text("vcpkg", encoding="utf-8")
    pipx_cache = local / "pipx" / ".cache"
    pipx_cache.mkdir(parents=True)
    (pipx_cache / "wheel.whl").write_text("pipx", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "package-cache",
        "--older-than-days",
        "0",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User"), "PROGRAMDATA": str(root / "ProgramData")},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["package-cache.vcpkg.downloads"]["path"] == str(vcpkg_downloads)
    assert by_rule["package-cache.pipx.cache"]["path"] == str(pipx_cache)

def test_inspect_rule_id_filters_dev_cache_candidates(tmp_path: Path, cleanwin_json: CleanWinJSON) -> None:
    root = tmp_path
    pip_cache = root / "LocalAppData" / "pip" / "Cache"
    pip_cache.mkdir(parents=True)
    (pip_cache / "http-v2").mkdir()
    ((pip_cache / "http-v2") / "entry").write_text("pip", encoding="utf-8")

    npm_cache = root / "npm-cache"
    npm_cache.mkdir()
    (npm_cache / "_cacache").mkdir()
    ((npm_cache / "_cacache") / "entry").write_text("npm", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        "--rule-id",
        "dev-cache.npm.cache",
        env={"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(root / "LocalAppData"), "USERPROFILE": str(root / "User")},
    )
    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["rule_id"] == "dev-cache.npm.cache"

def test_plan_rule_id_filters_candidates_before_write(tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile) -> None:
    root = tmp_path
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

    payload = cleanwin_plan_file(
        plan_file,
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        "--rule-id",
        "dev-cache.pip.cache",
        env={"NPM_CONFIG_CACHE": str(npm_cache), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["rule_id"] == "dev-cache.pip.cache"

def test_read_only_findings_include_structured_review_details(cleanwin_json: CleanWinJSON) -> None:
    payload = cleanwin_json("inspect", "--categories", "docker-report")
    finding = payload["findings"][0]
    assert "review_details" in finding
    assert "suggested_paths" in finding["review_details"]
    assert "risk_notes" in finding["review_details"]
    assert "manual_review_steps" in finding["review_details"]
    assert "path_evidence" in finding["review_details"]
    assert "evidence_summary" in finding["review_details"]

def test_read_only_findings_report_existing_path_evidence_without_candidates(
    tmp_path: Path, cleanwin_json: CleanWinJSON
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    docker_log = local / "Docker" / "log"
    docker_log.mkdir(parents=True)
    (docker_log / "service.log").write_text("docker", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "docker-report",
        env={"LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    assert payload["summary"]["candidate_count"] == 0

    details = payload["findings"][0]["review_details"]
    evidence = {item["path"]: item for item in details["path_evidence"]}
    assert evidence[str(docker_log)]["kind"] == "directory"
    assert evidence[str(docker_log)]["exists"]
    assert evidence[str(docker_log)]["child_count"] == 1
    assert details["evidence_summary"]["existing_path_count"] >= 1

def test_validate_plan_rejects_permanent_and_admin_candidates(tmp_path: Path, run_cleanwin: RunCleanWin) -> None:
    target = tmp_path / "candidate.tmp"
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
    assert not permanent_validation["valid"]
    assert "Unsupported plan delete_mode" in "\n".join(permanent_validation["errors"])

    admin_plan = Plan(
        candidates=[replace(permanent_plan.candidates[0], delete_mode="recycle", requires_admin=True)],
        categories=["temp"],
    )
    admin_raw = admin_plan.to_dict()
    admin_validation = validate_plan_payload(admin_plan, admin_raw, require_context=False)
    assert not admin_validation["valid"]
    assert "Admin-scoped candidate" in "\n".join(admin_validation["errors"])
