from __future__ import annotations

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
AssertPlanFileValid = Callable[[Path, dict[str, str]], JSONPayload]
AssertDryRunResult = Callable[[JSONPayload, Path], JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
WriteJSONFile = Callable[[Path, JSONPayload], Path]
MakeTempPlan = Callable[[Path, bool], tuple[Path, Path, dict[str, str]]]
MakeWindowsCacheEnv = Callable[[Path], dict[str, str]]


def test_capabilities_reports_dry_run_and_single_exit(cleanwin_json: CleanWinJSON) -> None:
    payload = cleanwin_json("capabilities")
    assert payload["default_dry_run"]
    assert payload["deletion_exit"] == "cleanwincli.delete_ops.safe_delete"
    assert "browser-cache" in payload["safe_categories"]
    assert "package-cache" in payload["safe_categories"]
    assert "registry-clean" in payload["never_auto_execute"]

def test_inspect_temp_finds_sandbox_candidate(
    tmp_path: Path, cleanwin_json: CleanWinJSON, make_temp_plan_fixture: MakeTempPlan
) -> None:
    _, stale_file, env = make_temp_plan_fixture(tmp_path, False)
    payload = cleanwin_json("inspect", "--categories", "temp", "--older-than-days", "0", env=env)
    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["path"] == str(stale_file)
    assert payload["candidates"][0]["identity"]["schema"] == "cleanwin.filesystem-identity.v1"

def test_plan_validate_round_trip(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    assert_plan_file_valid: AssertPlanFileValid,
    make_temp_plan_fixture: MakeTempPlan,
) -> None:
    _, _, env = make_temp_plan_fixture(tmp_path, False)
    plan_file = tmp_path / "plan.json"
    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)
    assert_plan_file_valid(plan_file, env)

def test_execute_plan_dry_run_reports_candidate_results_without_deleting(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
    assert_dry_run_result: AssertDryRunResult,
) -> None:
    _, stale_file, env = make_temp_plan_fixture(tmp_path, True)
    plan_file = tmp_path / "plan.json"

    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)
    payload = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert payload["schema"] == "cleanwin.execute.v1"
    assert not payload["executed"]
    assert payload["dry_run"]
    assert payload["validation"]["valid"]
    assert_dry_run_result(payload, stale_file)
    assert payload["summary"] == {"result_count": 1, "status_counts": {"dry-run": 1}}
    assert "confirmation_token" in payload["confirmation"]

def test_review_plan_summarizes_execution_handoff(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
) -> None:
    npm_cache = tmp_path / "npm-cache"
    write_text_file(npm_cache / "_cacache" / "index", "x")
    plan_file = tmp_path / "plan.json"
    env = make_windows_cache_env(tmp_path) | {"NPM_CONFIG_CACHE": str(npm_cache)}
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
    tmp_path: Path,
    run_cleanwin: RunCleanWin,
    cleanwin_result_json: CleanWinResultJSON,
    write_text_file: WriteTextFile,
    write_json_file: WriteJSONFile,
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
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
    write_json_file(plan_file, plan.to_dict())
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
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
) -> None:
    root = tmp_path
    npm_cache = root / "npm-cache"
    write_text_file(npm_cache / "_cacache" / "index", "x")
    env = make_windows_cache_env(root) | {"NPM_CONFIG_CACHE": str(npm_cache)}

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        env=env,
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
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    user = root / "User"
    for path, contents in [
        (local / "pypoetry" / "Cache" / "artifact.whl", "poetry"),
        (local / "pipenv" / "Cache" / "resolver.json", "pipenv"),
        (user / ".cache" / "pre-commit" / "repo.db", "precommit"),
        (local / "node-gyp" / "Cache" / "headers.tar.gz", "node-gyp"),
    ]:
        write_text_file(path, contents)

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert by_rule["dev-cache.poetry.cache"]["cache_owner"] == "Poetry"
    assert by_rule["dev-cache.pipenv.cache"]["cache_owner"] == "Pipenv"
    assert by_rule["dev-cache.pre-commit.cache"]["cache_owner"] == "pre-commit"
    assert by_rule["dev-cache.node-gyp.cache"]["cache_owner"] == "node-gyp"
    assert "poetry cache clear" in by_rule["dev-cache.poetry.cache"]["official_cleanup_command"]

def test_package_cache_scans_common_windows_package_manager_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    for path, contents in [
        (local / "Microsoft" / "WinGet" / "Packages" / "installer.msix", "winget"),
        (root / "User" / "scoop" / "cache" / "app.zip", "scoop"),
        (root / "ProgramData" / "chocolatey" / "cache" / "pkg.nupkg", "choco"),
        (local / "uv" / "cache" / "wheel.whl", "uv"),
    ]:
        write_text_file(path, contents)

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "package-cache",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
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
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    cache_files = [
        (roaming / "Slack" / "Cache" / "entry", "slack"),
        (roaming / "Microsoft" / "Teams" / "logs" / "current.log", "teams"),
        (roaming / "Code" / "CachedData" / "cache.bin", "code"),
        (local / "JetBrains" / "PyCharm2024.1" / "log" / "idea.log", "jetbrains"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    slack_cache, teams_logs, vscode_cache, jetbrains_logs = [path.parent for path, _ in cache_files]

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

def test_app_leftovers_scans_expanded_electron_gpu_caches(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    cache_files = [
        (roaming / "Microsoft" / "Teams" / "GPUCache" / "shader.bin", "teams"),
        (roaming / "discord" / "GPUCache" / "shader.bin", "discord"),
        (roaming / "Code" / "GPUCache" / "shader.bin", "code"),
        (roaming / "Code" / "User" / "settings.json", "{}"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    teams_gpu_cache, discord_gpu_cache, vscode_gpu_cache, vscode_user_data = [path.parent for path, _ in cache_files]

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

def test_app_leftovers_skips_when_active_install_marker_exists(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    write_text_file(roaming / "Slack" / "Cache" / "entry", "slack")
    write_text_file(local / "slack" / "slack.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    assert payload["summary"]["candidate_count"] == 0

def test_app_leftovers_skips_globbed_active_install_markers(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    discord_cache = roaming / "discord" / "Cache"
    write_text_file(discord_cache / "entry", "discord")
    discord_marker = local / "Discord" / "app-1.2.3" / "Discord.exe"
    write_text_file(discord_marker, "exe")

    jetbrains_log = local / "JetBrains" / "PyCharm2024.1" / "log"
    write_text_file(jetbrains_log / "idea.log", "jetbrains")
    jetbrains_marker = program_files / "JetBrains" / "PyCharm 2024.1" / "bin" / "pycharm64.exe"
    write_text_file(jetbrains_marker, "exe")

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

def test_app_leftovers_scans_more_common_app_cache_and_logs(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    cache_files = [
        (roaming / "Notion" / "Cache" / "entry", "notion"),
        (roaming / "Figma" / "logs" / "figma.log", "figma"),
        (roaming / "obs-studio" / "logs" / "obs.log", "obs"),
        (local / "Spotify" / "Browser" / "Cache" / "entry", "spotify"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    notion_cache, figma_logs, obs_logs, spotify_cache = [path.parent for path, _ in cache_files]

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

def test_app_leftovers_scans_additional_vendor_cache_and_logs(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    cases = [
        ("app-leftovers.adobe.creative-cloud.logs", local / "Adobe" / "Creative Cloud" / "Logs", "acc.log", "adobe"),
        (
            "app-leftovers.office.telemetry-logs",
            local / "Microsoft" / "Office" / "16.0" / "Telemetry",
            "telemetry.log",
            "office",
        ),
        ("app-leftovers.steam.htmlcache", local / "Steam" / "htmlcache", "entry", "steam"),
        ("app-leftovers.epic.webcache", local / "EpicGamesLauncher" / "Saved" / "webcache", "entry", "epic"),
        ("app-leftovers.battlenet.cache", local / "Battle.net" / "Cache", "entry", "battle"),
        ("app-leftovers.nvidia.dxcache", local / "NVIDIA" / "DXCache", "shader.bin", "nvidia"),
        ("app-leftovers.amd.dxcache", local / "AMD" / "DxCache", "shader.bin", "amd"),
    ]
    for _, path, filename, contents in cases:
        write_text_file(path / filename, contents)

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(root / "Roaming"), "LOCALAPPDATA": str(local), "USERPROFILE": str(root / "User")},
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    for rule_id, path, _, _ in cases:
        assert by_rule[rule_id]["path"] == str(path)

def test_app_leftovers_skips_additional_vendor_rules_when_active_marker_exists(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"
    steam_cache = local / "Steam" / "htmlcache"
    write_text_file(steam_cache / "entry", "steam")
    steam_marker = program_files / "Steam" / "steam.exe"
    write_text_file(steam_marker, "exe")

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
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    assert_dry_run_result: AssertDryRunResult,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    slack_cache = write_text_file(roaming / "Slack" / "Cache" / "entry", "slack").parent
    vscode_cache = write_text_file(roaming / "Code" / "CachedData" / "cache.bin", "code").parent
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
    assert_dry_run_result(dry_run_payload, vscode_cache)
    assert slack_cache.exists()

def test_browser_cache_scans_cache_only_directories_without_profile_data(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    chrome_cache = write_text_file(
        local / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "entry", "chrome"
    ).parent
    edge_code_cache = write_text_file(
        local / "Microsoft" / "Edge" / "User Data" / "Profile 1" / "Code Cache" / "js", "edge"
    ).parent
    cookies = local / "Google" / "Chrome" / "User Data" / "Default" / "Cookies"
    write_text_file(cookies, "do-not-touch")

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

def test_browser_cache_discovers_additional_browser_profiles(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    cache_paths = [
        local / "Google" / "Chrome" / "User Data" / "Profile 2" / "Cache",
        local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache",
        local / "Mozilla" / "Firefox" / "Profiles" / "abcd1234.work" / "cache2",
    ]
    for path in cache_paths:
        write_text_file(path / "entry", path.parts[-4].lower())

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
    assert paths == {str(path) for path in cache_paths}

def test_browser_cache_discovers_brave_profile_caches(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    brave_cache = write_text_file(
        local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache" / "entry", "brave"
    ).parent
    brave_code_cache = write_text_file(
        local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Profile 1" / "Code Cache" / "js", "brave"
    ).parent
    cookies = brave_cache.parent / "Cookies"
    write_text_file(cookies, "do-not-touch")

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
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    chrome_cache = write_text_file(
        local / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "entry", "chrome"
    ).parent
    write_text_file(chrome_cache.parent / "Cookies", "secret")
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
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    assert_dry_run_result: AssertDryRunResult,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    uv_cache = write_text_file(local / "uv" / "cache" / "wheel.whl", "uv").parent
    winget_cache = write_text_file(local / "Microsoft" / "WinGet" / "Packages" / "installer.msix", "winget").parent
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
    assert_dry_run_result(dry_run_payload, uv_cache)
    assert winget_cache.exists()

def test_package_cache_scans_additional_developer_package_caches(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    vcpkg_downloads = write_text_file(local / "vcpkg" / "downloads" / "archive.zip", "vcpkg").parent
    pipx_cache = write_text_file(local / "pipx" / ".cache" / "wheel.whl", "pipx").parent

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

def test_inspect_rule_id_filters_dev_cache_candidates(
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    pip_cache = root / "LocalAppData" / "pip" / "Cache"
    write_text_file(pip_cache / "http-v2" / "entry", "pip")

    npm_cache = root / "npm-cache"
    write_text_file(npm_cache / "_cacache" / "entry", "npm")

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

def test_plan_rule_id_filters_candidates_before_write(
    tmp_path: Path, cleanwin_plan_file: CleanWinPlanFile, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    npm_cache = root / "npm-cache"
    write_text_file(npm_cache / "_cacache" / "entry", "npm")
    pip_cache = local / "pip" / "Cache"
    write_text_file(pip_cache / "wheels" / "entry", "pip")
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
    tmp_path: Path, cleanwin_json: CleanWinJSON, write_text_file: WriteTextFile
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    docker_log = write_text_file(local / "Docker" / "log" / "service.log", "docker").parent

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

def test_validate_plan_rejects_permanent_and_admin_candidates(
    tmp_path: Path, run_cleanwin: RunCleanWin, write_text_file: WriteTextFile
) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
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
