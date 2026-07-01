from __future__ import annotations

import subprocess
from collections.abc import Callable, Collection, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from cleanwincli.core import validate_plan_payload
from cleanwincli.identity import capture_filesystem_identity
from cleanwincli.models import Candidate, Plan

JSONPayload = dict[str, Any]
RunCleanWin = Callable[..., subprocess.CompletedProcess[str]]
CleanWinResultJSON = Callable[[subprocess.CompletedProcess[str]], JSONPayload]
CleanWinJSON = Callable[..., JSONPayload]
CleanWinPlanFile = Callable[..., JSONPayload]
AssertPlanFileValid = Callable[[Path, dict[str, str]], JSONPayload]
AssertDryRunResult = Callable[[JSONPayload, Path], JSONPayload]
AssertDryRunSummary = Callable[[JSONPayload, Path], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertSafeToExecuteDisabled = Callable[[JSONPayload], JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
WriteJSONFile = Callable[[Path, JSONPayload], Path]
MakeTempPlan = Callable[[Path, bool], tuple[Path, Path, dict[str, str]]]
MakeWindowsCacheEnv = Callable[[Path], dict[str, str]]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertContainsNone = Callable[[Collection[Any], Sequence[Any]], None]
AssertTextContainsAll = Callable[[str, Sequence[str]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
AssertAllMatch = Callable[[Sequence[JSONPayload], Callable[[JSONPayload], bool]], Sequence[JSONPayload]]
AssertNoneMatch = Callable[[Sequence[JSONPayload], Callable[[JSONPayload], bool]], Sequence[JSONPayload]]
AssertExactSet = Callable[[Collection[Any], Collection[Any]], set[Any]]
AssertNonEmpty = Callable[[Sequence[Any]], Sequence[Any]]
AssertAtLeast = Callable[[int, int], int]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertReturnCode = Callable[[subprocess.CompletedProcess[str], int], subprocess.CompletedProcess[str]]
AssertPathExists = Callable[[Path], Path]


def test_capabilities_reports_dry_run_and_single_exit(
    cleanwin_json: CleanWinJSON,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    payload = cleanwin_json("capabilities")
    assert_field_values(payload, {"default_dry_run": True, "deletion_exit": "cleanwincli.delete_ops.safe_delete"})
    assert_contains_all(payload["safe_categories"], ["browser-cache", "package-cache"])
    assert_contains_all(payload["executable_cache_categories"], ["temp", "dev-cache", "package-cache", "browser-cache"])
    assert_contains_all(payload["never_auto_execute"], ["registry-clean"])


def test_non_json_cli_output_uses_progress_summary(
    run_cleanwin_human: RunCleanWin,
    cleanwin_test_env: Callable[..., dict[str, str]],
    assert_returncode: AssertReturnCode,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    result = run_cleanwin_human("capabilities", env=cleanwin_test_env())

    assert_returncode(result, 0)
    assert_text_contains_all(
        result.stdout,
        [
            "CleanWin ::",
            "| status   ok",
            "| progress [",
            "] 100%",
            "`- json     rerun with --json",
        ],
    )


def test_json_cli_output_is_safe_for_legacy_windows_code_pages(
    run_cleanwin: RunCleanWin,
    cleanwin_result_json: CleanWinResultJSON,
    assert_returncode: AssertReturnCode,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    result = run_cleanwin("schema-registry", env={"PYTHONIOENCODING": "cp1252"})

    assert_returncode(result, 0)
    payload = cleanwin_result_json(result)
    assert_payload_schema(payload, "cleanwin.ai-schema-registry.v1")


def test_inspect_temp_finds_sandbox_candidate(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
    assert_payload_schema: AssertPayloadSchema,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    _, stale_file, env = make_temp_plan_fixture(tmp_path, False)
    payload = cleanwin_json("inspect", "--categories", "temp", "--older-than-days", "0", env=env)
    assert_summary_counts(payload, {"candidate_count": 1})
    assert_field_values(payload["candidates"][0], {"path": str(stale_file)})
    assert_payload_schema(payload["candidates"][0]["identity"], "cleanwin.filesystem-identity.v1")

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


def test_policy_simulate_dry_run_allowed_with_valid_plan(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
    assert_field_values: AssertFieldValues,
) -> None:
    _, _, env = make_temp_plan_fixture(tmp_path, False)
    plan_file = tmp_path / "plan.json"
    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)

    payload = cleanwin_json(
        "policy-simulate",
        "--plan-file", str(plan_file),
        "--no-require-plan-context",
        env=env,
    )
    assert_payload_schema(payload, "cleanwin.ai-policy-simulation.v1")
    assert_payload_status_true(payload, "validation", "valid")
    assert_field_values(
        payload,
        {
            "execute_intent": False,
            "delete_mode": "recycle",
            "safe_to_execute": False,
            "decision.tool": "cleanwin_dry_run_plan",
        },
    )
    assert_payload_status_true(payload, "decision", "allowed")


def test_policy_simulate_execute_denied_without_confirmation_token(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
    assert_payload_status_false: AssertPayloadStatus,
    assert_field_values: AssertFieldValues,
) -> None:
    _, _, env = make_temp_plan_fixture(tmp_path, False)
    plan_file = tmp_path / "plan.json"
    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)

    payload = cleanwin_json(
        "policy-simulate",
        "--plan-file", str(plan_file),
        "--execute",
        "--operation-log", str(tmp_path / "ops.jsonl"),
        "--require-confirmation-token",
        "--no-require-plan-context",
        env=env,
    )
    assert_payload_schema(payload, "cleanwin.ai-policy-simulation.v1")
    assert_payload_status_true(payload, "validation", "valid")
    assert_field_values(payload, {"execute_intent": True})
    assert_payload_status_false(payload, "decision", "allowed")
    assert_payload_status_false(payload, "safe_to_execute")


def test_policy_simulate_rejects_invalid_plan(
    tmp_path: Path,
    run_cleanwin: RunCleanWin,
    make_temp_plan_fixture: MakeTempPlan,
    write_text_file: WriteTextFile,
    assert_returncode: AssertReturnCode,
) -> None:
    _, _, env = make_temp_plan_fixture(tmp_path, False)
    plan_file = tmp_path / "plan.json"
    write_text_file(plan_file, '{"schema": "bogus"}')

    result = run_cleanwin(
        "policy-simulate",
        "--plan-file", str(plan_file),
        "--no-require-plan-context",
        env=env,
    )
    assert_returncode(result, 2)


def test_execute_plan_dry_run_reports_candidate_results_without_deleting(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    make_temp_plan_fixture: MakeTempPlan,
    assert_dry_run_summary: AssertDryRunSummary,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    _, stale_file, env = make_temp_plan_fixture(tmp_path, True)
    plan_file = tmp_path / "plan.json"

    cleanwin_plan_file(plan_file, "--categories", "temp", "--older-than-days", "0", env=env)
    payload = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert_payload_schema(payload, "cleanwin.execute.v1")
    assert_payload_status_true(payload, "validation", "valid")
    assert_dry_run_summary(payload, stale_file)
    assert_contains_all(payload["confirmation"], ["confirmation_token"])

def test_review_plan_summarizes_execution_handoff(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_readonly_report: AssertReadonlyReport,
    assert_payload_status_true: AssertPayloadStatus,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
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
    assert_readonly_report(review, "cleanwin.review.v1")
    assert_payload_status_true(review, "validation", "valid")
    assert_field_values(
        review["execution_handoff"],
        {
            "execution_profile": "controlled-low-risk-cache-recycle",
            "requires_recycle_mode": True,
            "requires_human_confirmation": True,
            "requires_matching_dry_run_token": True,
            "requires_operation_log": True,
            "requires_identity_match": True,
            "requires_regeneration_rationale": True,
            "required_readiness_schema": "cleanwin.low-risk-cache-execution-readiness.v1",
            "required_readiness_validation_schema": "cleanwin.low-risk-cache-readiness-validation.v1",
            "required_operation_log_readiness_schema": "cleanwin.operation-log-readiness.v1",
            "required_operation_log_readiness_validation_schema": "cleanwin.operation-log-readiness-validation.v1",
            "requires_operation_log_readiness": True,
        },
    )
    assert_contains_all(
        review["execution_handoff"]["required_evidence_refs"],
        ["dry_run_token_ref", "operation_log_ref", "operation_log_readiness_ref", "identity_check_ref", "rule_quality_gate"],
    )
    assert_field_values(review["execution_handoff"], {"readiness_command": ["cleanwin", "--json", "low-risk-cache-readiness"]})
    assert_field_values(review["execution_handoff"], {"operation_log_readiness_command": ["cleanwin", "--json", "operation-log-readiness"]})
    assert_summary_counts(review, {"candidate_count": 1})
    assert_field_values(
        review,
        {"rule_summary.0.rule_id": "dev-cache.npm.cache", "official_cleanup_commands": ["npm cache clean --force"]},
    )
    assert_contains_all(review["execution_handoff"]["required_predecessor_tools"], ["cleanwin_dry_run_plan"])
    assert_contains_all(review["execution_handoff"]["allowed_delete_modes"], ["recycle"])
    assert_contains_all(review["execution_handoff"]["forbidden_actions"], ["permanent-delete", "registry-mutation", "process-kill"])

def test_review_plan_rejects_invalid_plan_exit_code(
    tmp_path: Path,
    run_cleanwin: RunCleanWin,
    cleanwin_result_json: CleanWinResultJSON,
    write_text_file: WriteTextFile,
    write_json_file: WriteJSONFile,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_payload_status_false: AssertPayloadStatus,
    assert_returncode: AssertReturnCode,
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
    assert_returncode(result, 2)
    payload = cleanwin_result_json(result)
    assert_payload_status_false(payload, "validation", "valid")
    assert_safe_to_execute_disabled(payload["execution_handoff"])

def test_read_only_categories_do_not_create_candidates(
    cleanwin_json: CleanWinJSON,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_text_contains_all: AssertTextContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    payload = cleanwin_json(
        "inspect",
        "--categories",
        "registry-report,startup-report,windows-report,large-files,docker-report,wsl-report,visual-studio-report,browser-cache-report",
    )
    assert_summary_counts(payload, {"candidate_count": 0, "finding_count": 8})
    for finding in payload["findings"]:
        assert_safe_to_execute_disabled(finding)
    by_category = {finding["category"]: finding for finding in payload["findings"]}
    assert_field_values(by_category["docker-report"], {"rule_id": "report.docker.manual-cleanup"})
    assert_field_values(by_category["wsl-report"], {"owner": "WSL"})
    assert_text_contains_all(by_category["browser-cache-report"]["detail"].lower(), ["browser profiles"])

def test_dev_cache_candidates_include_rule_metadata_and_official_commands(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_payload_schema: AssertPayloadSchema,
    assert_summary_counts: AssertSummaryCounts,
    assert_text_contains_all: AssertTextContainsAll,
    assert_field_values: AssertFieldValues,
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
    assert_summary_counts(payload, {"candidate_count": 1})
    candidate = payload["candidates"][0]
    assert_field_values(
        candidate,
        {
            "category": "dev-cache",
            "rule_id": "dev-cache.npm.cache",
            "cache_owner": "npm",
            "official_cleanup_command": "npm cache clean --force",
        },
    )
    assert_text_contains_all(candidate["safe_to_delete_rationale"].lower(), ["regenerated"])
    assert_payload_schema(candidate["identity"], "cleanwin.filesystem-identity.v1")

def test_dev_cache_scans_expanded_python_and_node_tool_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_text_contains_all: AssertTextContainsAll,
    assert_field_values: AssertFieldValues,
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
    assert_field_values(by_rule["dev-cache.poetry.cache"], {"cache_owner": "Poetry"})
    assert_field_values(by_rule["dev-cache.pipenv.cache"], {"cache_owner": "Pipenv"})
    assert_field_values(by_rule["dev-cache.pre-commit.cache"], {"cache_owner": "pre-commit"})
    assert_field_values(by_rule["dev-cache.node-gyp.cache"], {"cache_owner": "node-gyp"})
    assert_text_contains_all(by_rule["dev-cache.poetry.cache"]["official_cleanup_command"], ["poetry cache clear"])

def test_package_cache_scans_common_windows_package_manager_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_text_contains_all: AssertTextContainsAll,
    assert_field_values: AssertFieldValues,
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
    assert_summary_counts(payload, {"candidate_count": 4})
    assert_contains_all(
        rule_ids,
        [
            "package-cache.winget.packages",
            "package-cache.scoop.cache",
            "package-cache.chocolatey.cache",
            "package-cache.uv.cache",
        ],
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["package-cache.winget.packages"], {"cache_owner": "WinGet"})
    assert_text_contains_all(by_rule["package-cache.winget.packages"]["official_cleanup_command"].lower(), ["winget"])
    assert_field_values(by_rule["package-cache.uv.cache"], {"cache_owner": "uv"})

def test_app_leftovers_scans_common_uninstalled_app_cache_and_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_all_match: AssertAllMatch,
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
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_summary_counts(payload, {"candidate_count": 4})
    assert_contains_all(paths, [str(slack_cache), str(teams_logs), str(vscode_cache), str(jetbrains_logs)])
    assert_all_match(payload["candidates"], lambda candidate: candidate["category"] == "app-leftovers")
    assert_all_match(payload["candidates"], lambda candidate: candidate["delete_mode"] == "recycle")

def test_app_leftovers_scans_expanded_electron_gpu_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
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
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.teams-classic.gpu-cache"], {"path": str(teams_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.discord.gpu-cache"], {"path": str(discord_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.vscode.gpu-cache"], {"path": str(vscode_gpu_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(vscode_user_data)])

def test_app_leftovers_skips_when_active_install_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
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
        env=make_windows_cache_env(root),
    )
    assert_summary_counts(payload, {"candidate_count": 0})

def test_app_leftovers_skips_globbed_active_install_markers(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
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
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(discord_cache), str(jetbrains_log)])

def test_app_leftovers_scans_more_common_app_cache_and_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_field_values: AssertFieldValues,
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
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.notion.cache"], {"path": str(notion_cache)})
    assert_field_values(by_rule["app-leftovers.figma.logs"], {"path": str(figma_logs)})
    assert_field_values(by_rule["app-leftovers.obs-studio.logs"], {"path": str(obs_logs)})
    assert_field_values(by_rule["app-leftovers.spotify.browser-cache"], {"path": str(spotify_cache)})

def test_app_leftovers_scans_additional_vendor_cache_and_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_field_values: AssertFieldValues,
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
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    for rule_id, path, _, _ in cases:
        assert_field_values(by_rule[rule_id], {"path": str(path)})

def test_app_leftovers_scans_additional_windows_software_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "Telegram Desktop" / "tdata" / "user_data" / "cache" / "thumb.bin", "telegram"),
        (roaming / "Signal" / "logs" / "main.log", "signal"),
        (roaming / "WhatsApp" / "GPUCache" / "shader.bin", "whatsapp"),
        (roaming / "Cursor" / "CachedData" / "cache.bin", "cursor"),
        (roaming / "Cursor" / "GPUCache" / "shader.bin", "cursor"),
        (local / "Google" / "AndroidStudio2025.1" / "log" / "idea.log", "android-studio"),
        (user / "VirtualBox VMs" / "ReviewVM" / "Logs" / "VBox.log", "virtualbox"),
        (roaming / "vlc" / "art" / "cover.jpg", "vlc"),
        (roaming / "Zoom" / "GPUCache" / "shader.bin", "zoom"),
        (local / "1Password" / "logs" / "1password.log", "1password"),
        (roaming / "Telegram Desktop" / "tdata" / "key_data", "sensitive"),
        (user / "VirtualBox VMs" / "ReviewVM" / "ReviewVM.vdi", "disk"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    (
        telegram_cache,
        signal_logs,
        whatsapp_gpu_cache,
        cursor_cached_data,
        cursor_gpu_cache,
        android_studio_logs,
        virtualbox_logs,
        vlc_art_cache,
        zoom_gpu_cache,
        onepassword_logs,
        telegram_key_data,
        virtualbox_disk,
    ) = [path.parent for path, _ in cache_files]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.telegram.cache"], {"path": str(telegram_cache)})
    assert_field_values(by_rule["app-leftovers.signal.logs"], {"path": str(signal_logs)})
    assert_field_values(by_rule["app-leftovers.whatsapp.gpu-cache"], {"path": str(whatsapp_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.cursor.cached-data"], {"path": str(cursor_cached_data)})
    assert_field_values(by_rule["app-leftovers.cursor.gpu-cache"], {"path": str(cursor_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.android-studio.logs"], {"path": str(android_studio_logs)})
    assert_field_values(by_rule["app-leftovers.virtualbox.logs"], {"path": str(virtualbox_logs)})
    assert_field_values(by_rule["app-leftovers.vlc.art-cache"], {"path": str(vlc_art_cache)})
    assert_field_values(by_rule["app-leftovers.zoom.gpu-cache"], {"path": str(zoom_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.1password.logs"], {"path": str(onepassword_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(telegram_key_data), str(virtualbox_disk)])

def test_app_leftovers_skips_additional_vendor_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
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
        env=make_windows_cache_env(root),
    )
    assert_contains_none({candidate["rule_id"] for candidate in payload["candidates"]}, ["app-leftovers.steam.htmlcache"])

def test_app_leftovers_skips_additional_globbed_active_install_markers(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"

    telegram_cache = roaming / "Telegram Desktop" / "tdata" / "user_data" / "cache"
    write_text_file(telegram_cache / "thumb.bin", "telegram")
    write_text_file(local / "Programs" / "Telegram Desktop" / "Telegram.exe", "exe")

    onepassword_logs = local / "1Password" / "logs"
    write_text_file(onepassword_logs / "1password.log", "1password")
    write_text_file(local / "1Password" / "app" / "8.10.0" / "1Password.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(telegram_cache), str(onepassword_logs)])

def test_app_leftovers_scans_more_desktop_and_launcher_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "GitHub Desktop" / "GPUCache" / "shader.bin", "github"),
        (roaming / "Obsidian" / "GPUCache" / "shader.bin", "obsidian"),
        (roaming / "UnityHub" / "logs" / "hub.log", "unity"),
        (local / "UnrealEngineLauncher" / "Saved" / "webcache" / "entry", "unreal"),
        (local / "Electronic Arts" / "EA Desktop" / "Cache" / "entry", "ea"),
        (local / "GOG.com" / "Galaxy" / "webcache" / "entry", "gog"),
        (local / "Ubisoft Game Launcher" / "cache" / "entry", "ubisoft"),
        (local / "Dropbox" / "logs" / "dropbox.log", "dropbox"),
        (local / "LGHUB" / "logs" / "lghub.log", "logitech"),
        (local / "Razer" / "Synapse" / "Logs" / "synapse.log", "razer"),
        (user / "Documents" / "ObsidianVault" / "note.md", "vault"),
        (user / "Saved Games" / "ExampleGame" / "save.dat", "save"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    (
        github_gpu_cache,
        obsidian_gpu_cache,
        unity_logs,
        unreal_webcache,
        ea_cache,
        gog_webcache,
        ubisoft_cache,
        dropbox_logs,
        logitech_logs,
        razer_logs,
        obsidian_vault,
        saved_game,
    ) = [path.parent for path, _ in cache_files]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.github-desktop.gpu-cache"], {"path": str(github_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.obsidian.gpu-cache"], {"path": str(obsidian_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.unity-hub.logs"], {"path": str(unity_logs)})
    assert_field_values(by_rule["app-leftovers.unreal-engine-launcher.webcache"], {"path": str(unreal_webcache)})
    assert_field_values(by_rule["app-leftovers.ea-app.cache"], {"path": str(ea_cache)})
    assert_field_values(by_rule["app-leftovers.gog-galaxy.webcache"], {"path": str(gog_webcache)})
    assert_field_values(by_rule["app-leftovers.ubisoft-connect.cache"], {"path": str(ubisoft_cache)})
    assert_field_values(by_rule["app-leftovers.dropbox.logs"], {"path": str(dropbox_logs)})
    assert_field_values(by_rule["app-leftovers.logitech-g-hub.logs"], {"path": str(logitech_logs)})
    assert_field_values(by_rule["app-leftovers.razer-synapse.logs"], {"path": str(razer_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(obsidian_vault), str(saved_game)])

def test_app_leftovers_skips_more_desktop_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    github_gpu_cache = roaming / "GitHub Desktop" / "GPUCache"
    write_text_file(github_gpu_cache / "shader.bin", "github")
    write_text_file(local / "GitHubDesktop" / "app-3.4.0" / "GitHubDesktop.exe", "exe")

    unity_logs = roaming / "UnityHub" / "logs"
    write_text_file(unity_logs / "hub.log", "unity")
    write_text_file(program_files / "Unity Hub" / "Unity Hub.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(github_gpu_cache), str(unity_logs)])

def test_app_leftovers_scans_collaboration_terminal_and_capture_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "Microsoft" / "Skype for Desktop" / "media_messaging" / "media_cache" / "thumb.bin", "skype"),
        (local / "CiscoSpark" / "Logs" / "webex.log", "webex"),
        (
            local
            / "Packages"
            / "MSTeams_8wekyb3d8bbwe"
            / "LocalCache"
            / "Microsoft"
            / "MSTeams"
            / "Logs"
            / "teams.log",
            "teams",
        ),
        (roaming / "Todoist" / "GPUCache" / "shader.bin", "todoist"),
        (roaming / "Linear" / "GPUCache" / "shader.bin", "linear"),
        (roaming / "Canva" / "GPUCache" / "shader.bin", "canva"),
        (local / "Microsoft" / "PowerShell" / "StartupProfileData-NonInteractive" / "cache.bin", "powershell"),
        (
            local
            / "Packages"
            / "Microsoft.WindowsTerminal_8wekyb3d8bbwe"
            / "LocalState"
            / "DiagOutputDir"
            / "diag.log",
            "terminal",
        ),
        (local / "TechSmith" / "Snagit" / "Logs" / "snagit.log", "snagit"),
        (local / "TechSmith" / "Camtasia Studio" / "Logs" / "camtasia.log", "camtasia"),
        (user / "Videos" / "Camtasia" / "project.tscproj", "project"),
        (user / "Pictures" / "Snagit" / "capture.snagx", "capture"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    (
        skype_media_cache,
        webex_logs,
        teams_logs,
        todoist_gpu_cache,
        linear_gpu_cache,
        canva_gpu_cache,
        powershell_startup_cache,
        terminal_diag,
        snagit_logs,
        camtasia_logs,
        camtasia_project,
        snagit_capture,
    ) = [path.parent for path, _ in cache_files]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.skype.media-cache"], {"path": str(skype_media_cache)})
    assert_field_values(by_rule["app-leftovers.webex.logs"], {"path": str(webex_logs)})
    assert_field_values(by_rule["app-leftovers.msteams-new.logs"], {"path": str(teams_logs)})
    assert_field_values(by_rule["app-leftovers.todoist.gpu-cache"], {"path": str(todoist_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.linear.gpu-cache"], {"path": str(linear_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.canva.gpu-cache"], {"path": str(canva_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.powershell.startup-cache"], {"path": str(powershell_startup_cache)})
    assert_field_values(by_rule["app-leftovers.windows-terminal.state-cache"], {"path": str(terminal_diag)})
    assert_field_values(by_rule["app-leftovers.snagit.logs"], {"path": str(snagit_logs)})
    assert_field_values(by_rule["app-leftovers.camtasia.logs"], {"path": str(camtasia_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(camtasia_project), str(snagit_capture)])

def test_app_leftovers_skips_collaboration_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    skype_cache = roaming / "Microsoft" / "Skype for Desktop" / "media_messaging" / "media_cache"
    write_text_file(skype_cache / "thumb.bin", "skype")
    write_text_file(program_files / "Microsoft" / "Skype for Desktop" / "Skype.exe", "exe")

    todoist_gpu_cache = roaming / "Todoist" / "GPUCache"
    write_text_file(todoist_gpu_cache / "shader.bin", "todoist")
    write_text_file(local / "Programs" / "Todoist" / "Todoist.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(skype_cache), str(todoist_gpu_cache)])

def test_app_leftovers_scans_remote_network_and_transfer_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    user = root / "User"
    cache_files = [
        (local / "Parsec" / "logs" / "parsec.log", "parsec"),
        (roaming / "AnyDesk" / "ad_svc.trace", "anydesk"),
        (program_data / "TeamViewer" / "Logs" / "TeamViewer.log", "teamviewer"),
        (local / "OpenVPN Connect" / "logs" / "ovpn.log", "openvpn"),
        (local / "Cloudflare" / "WARP" / "logs" / "warp.log", "warp"),
        (roaming / "Wireshark" / "recent_common", "recent"),
        (roaming / "FileZilla" / "logs" / "filezilla.log", "filezilla"),
        (local / "WinSCP" / "Logs" / "winscp.log", "winscp"),
        (local / "calibre-cache" / "metadata.db", "calibre"),
        (local / "qBittorrent" / "logs" / "qbittorrent.log", "qbittorrent"),
        (user / "Downloads" / "capture.pcapng", "pcap"),
        (user / "Books" / "library" / "metadata.db", "library"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    parsec_logs = cache_files[0][0].parent
    anydesk_trace = cache_files[1][0]
    teamviewer_logs = cache_files[2][0].parent
    openvpn_logs = cache_files[3][0].parent
    warp_logs = cache_files[4][0].parent
    wireshark_recent = cache_files[5][0]
    filezilla_logs = cache_files[6][0].parent
    winscp_logs = cache_files[7][0].parent
    calibre_cache = cache_files[8][0].parent
    qbittorrent_logs = cache_files[9][0].parent
    packet_capture = cache_files[10][0]
    calibre_library = cache_files[11][0].parent

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.parsec.logs"], {"path": str(parsec_logs)})
    assert_field_values(by_rule["app-leftovers.anydesk.logs"], {"path": str(anydesk_trace)})
    assert_field_values(by_rule["app-leftovers.teamviewer.logs"], {"path": str(teamviewer_logs)})
    assert_field_values(by_rule["app-leftovers.vpn-openvpn.logs"], {"path": str(openvpn_logs)})
    assert_field_values(by_rule["app-leftovers.warp.logs"], {"path": str(warp_logs)})
    assert_field_values(by_rule["app-leftovers.wireshark.recent-cache"], {"path": str(wireshark_recent)})
    assert_field_values(by_rule["app-leftovers.filezilla.logs"], {"path": str(filezilla_logs)})
    assert_field_values(by_rule["app-leftovers.winscp.logs"], {"path": str(winscp_logs)})
    assert_field_values(by_rule["app-leftovers.calibre.cache"], {"path": str(calibre_cache)})
    assert_field_values(by_rule["app-leftovers.qbittorrent.logs"], {"path": str(qbittorrent_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(packet_capture), str(calibre_library)])

def test_app_leftovers_skips_remote_access_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    parsec_logs = local / "Parsec" / "logs"
    write_text_file(parsec_logs / "parsec.log", "parsec")
    write_text_file(program_files / "Parsec" / "parsecd.exe", "exe")

    openvpn_logs = local / "OpenVPN Connect" / "logs"
    write_text_file(openvpn_logs / "ovpn.log", "openvpn")
    write_text_file(program_files / "OpenVPN Connect" / "OpenVPNConnect.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(parsec_logs), str(openvpn_logs)])

def test_app_leftovers_scans_database_api_design_and_printing_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "DBeaverData" / "workspace6" / ".metadata" / ".log", "dbeaver"),
        (local / "JetBrains" / "DataGrip2025.1" / "log" / "idea.log", "datagrip"),
        (roaming / "MySQL" / "Workbench" / "log" / "wb.log", "mysql"),
        (roaming / "azuredatastudio" / "CachedData" / "cache.bin", "ads"),
        (roaming / "Insomnia" / "GPUCache" / "shader.bin", "insomnia"),
        (roaming / "Bruno" / "logs" / "bruno.log", "bruno"),
        (local / "Tableau" / "Logs" / "tableau.log", "tableau"),
        (local / "Autodesk" / "Autodesk Desktop App" / "Logs" / "desktop.log", "autodesk"),
        (local / "Blender Foundation" / "Blender" / "Cache" / "preview.bin", "blender"),
        (local / "Packages" / "AD2F1837.HPPrinterControl_1.0.0" / "LocalState" / "Logs" / "hp.log", "hp"),
        (user / "Documents" / "SQL" / "query.sql", "sql"),
        (user / "Documents" / "Tableau" / "workbook.twbx", "tableau-workbook"),
        (user / "Documents" / "Blender" / "scene.blend", "blend"),
        (user / "Documents" / "Scans" / "scan.pdf", "scan"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    dbeaver_log = cache_files[0][0]
    datagrip_logs = cache_files[1][0].parent
    mysql_logs = cache_files[2][0].parent
    azure_data_studio_cached_data = cache_files[3][0].parent
    insomnia_gpu_cache = cache_files[4][0].parent
    bruno_logs = cache_files[5][0].parent
    tableau_logs = cache_files[6][0].parent
    autodesk_logs = cache_files[7][0].parent
    blender_cache = cache_files[8][0].parent
    hp_smart_logs = cache_files[9][0].parent
    sql_script = cache_files[10][0]
    tableau_workbook = cache_files[11][0]
    blender_scene = cache_files[12][0]
    scanned_document = cache_files[13][0]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.dbeaver.logs"], {"path": str(dbeaver_log)})
    assert_field_values(by_rule["app-leftovers.datagrip.logs"], {"path": str(datagrip_logs)})
    assert_field_values(by_rule["app-leftovers.mysql-workbench.logs"], {"path": str(mysql_logs)})
    assert_field_values(
        by_rule["app-leftovers.azure-data-studio.cached-data"], {"path": str(azure_data_studio_cached_data)}
    )
    assert_field_values(by_rule["app-leftovers.insomnia.gpu-cache"], {"path": str(insomnia_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.bruno.logs"], {"path": str(bruno_logs)})
    assert_field_values(by_rule["app-leftovers.tableau.logs"], {"path": str(tableau_logs)})
    assert_field_values(by_rule["app-leftovers.autodesk.logs"], {"path": str(autodesk_logs)})
    assert_field_values(by_rule["app-leftovers.blender.cache"], {"path": str(blender_cache)})
    assert_field_values(by_rule["app-leftovers.hp-smart.logs"], {"path": str(hp_smart_logs)})
    assert_contains_none(
        {candidate["path"] for candidate in payload["candidates"]},
        [str(sql_script), str(tableau_workbook), str(blender_scene), str(scanned_document)],
    )

def test_app_leftovers_skips_database_api_design_and_printing_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"
    program_files_x86 = root / "ProgramFiles(x86)"

    datagrip_logs = local / "JetBrains" / "DataGrip2025.1" / "log"
    write_text_file(datagrip_logs / "idea.log", "datagrip")
    write_text_file(program_files / "JetBrains" / "DataGrip 2025.1" / "bin" / "datagrip64.exe", "exe")

    mysql_logs = roaming / "MySQL" / "Workbench" / "log"
    write_text_file(mysql_logs / "wb.log", "mysql")
    write_text_file(program_files_x86 / "MySQL" / "MySQL Workbench 8.0" / "MySQLWorkbench.exe", "exe")

    insomnia_gpu_cache = roaming / "Insomnia" / "GPUCache"
    write_text_file(insomnia_gpu_cache / "shader.bin", "insomnia")
    write_text_file(local / "Programs" / "Insomnia" / "Insomnia.exe", "exe")

    blender_cache = local / "Blender Foundation" / "Blender" / "Cache"
    write_text_file(blender_cache / "preview.bin", "blender")
    write_text_file(program_files / "Blender Foundation" / "Blender 4.1" / "blender.exe", "exe")

    hp_smart_logs = local / "Packages" / "AD2F1837.HPPrinterControl_1.0.0" / "LocalState" / "Logs"
    write_text_file(hp_smart_logs / "hp.log", "hp")
    write_text_file(local / "Microsoft" / "WindowsApps" / "HP.Smart.exe", "exe")

    env = make_windows_cache_env(root) | {"ProgramFiles(x86)": str(program_files_x86)}
    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=env,
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(datagrip_logs), str(mysql_logs), str(insomnia_gpu_cache), str(blender_cache)])
    assert_contains_none({candidate["rule_id"] for candidate in payload["candidates"]}, ["app-leftovers.hp-smart.logs"])

def test_app_leftovers_scans_sync_media_and_peripheral_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "Microsoft" / "PowerToys" / "Logs" / "powertoys.log", "powertoys"),
        (local / "Microsoft" / "OneDrive" / "logs" / "sync.log", "onedrive"),
        (local / "Google" / "DriveFS" / "Logs" / "drive.log", "drive"),
        (local / "Apple Inc" / "iCloud" / "Logs" / "icloud.log", "icloud"),
        (local / "gegl-0.4" / "thumbnails" / "thumb.png", "gimp"),
        (local / "inkscape" / "cache" / "entry", "inkscape"),
        (local / "krita" / "cache" / "preview.bin", "krita"),
        (roaming / "audacity" / "SessionData" / "autosave.tmp", "audacity"),
        (roaming / "HandBrake" / "logs" / "encode.log", "handbrake"),
        (local / "Corsair" / "CUE" / "logs" / "icue.log", "icue"),
        (user / "OneDrive" / "Documents" / "synced.docx", "synced"),
        (user / "Google Drive" / "Work" / "sheet.xlsx", "drive-file"),
        (user / "iCloudDrive" / "Photos" / "photo.jpg", "icloud-file"),
        (user / "Pictures" / "artwork.xcf", "gimp-file"),
        (user / "Music" / "audacity-project.aup3", "audacity-project"),
        (user / "Videos" / "source.mkv", "video-source"),
        (user / "Documents" / "iCUE" / "profile.cueprofile", "icue-profile"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    powertoys_logs = cache_files[0][0].parent
    onedrive_logs = cache_files[1][0].parent
    google_drive_logs = cache_files[2][0].parent
    icloud_logs = cache_files[3][0].parent
    gimp_thumbnails = cache_files[4][0].parent
    inkscape_cache = cache_files[5][0].parent
    krita_cache = cache_files[6][0].parent
    audacity_session = cache_files[7][0].parent
    handbrake_logs = cache_files[8][0].parent
    corsair_logs = cache_files[9][0].parent
    protected_user_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.powertoys.logs"], {"path": str(powertoys_logs)})
    assert_field_values(by_rule["app-leftovers.onedrive.logs"], {"path": str(onedrive_logs)})
    assert_field_values(by_rule["app-leftovers.google-drivefs.logs"], {"path": str(google_drive_logs)})
    assert_field_values(by_rule["app-leftovers.icloud.logs"], {"path": str(icloud_logs)})
    assert_field_values(by_rule["app-leftovers.gimp.thumbnails"], {"path": str(gimp_thumbnails)})
    assert_field_values(by_rule["app-leftovers.inkscape.cache"], {"path": str(inkscape_cache)})
    assert_field_values(by_rule["app-leftovers.krita.cache"], {"path": str(krita_cache)})
    assert_field_values(by_rule["app-leftovers.audacity.logs"], {"path": str(audacity_session)})
    assert_field_values(by_rule["app-leftovers.handbrake.logs"], {"path": str(handbrake_logs)})
    assert_field_values(by_rule["app-leftovers.corsair-icue.logs"], {"path": str(corsair_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_user_files])

def test_app_leftovers_skips_sync_media_and_peripheral_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    powertoys_logs = local / "Microsoft" / "PowerToys" / "Logs"
    write_text_file(powertoys_logs / "powertoys.log", "powertoys")
    write_text_file(local / "Programs" / "PowerToys" / "PowerToys.exe", "exe")

    google_drive_logs = local / "Google" / "DriveFS" / "Logs"
    write_text_file(google_drive_logs / "drive.log", "drive")
    write_text_file(program_files / "Google" / "Drive File Stream" / "99.0" / "GoogleDriveFS.exe", "exe")

    gimp_thumbnails = local / "gegl-0.4" / "thumbnails"
    write_text_file(gimp_thumbnails / "thumb.png", "gimp")
    write_text_file(program_files / "GIMP 2" / "bin" / "gimp-2.10.exe", "exe")

    handbrake_logs = roaming / "HandBrake" / "logs"
    write_text_file(handbrake_logs / "encode.log", "handbrake")
    write_text_file(program_files / "HandBrake" / "HandBrake.exe", "exe")

    corsair_logs = local / "Corsair" / "CUE" / "logs"
    write_text_file(corsair_logs / "icue.log", "icue")
    write_text_file(program_files / "Corsair" / "Corsair iCUE5 Software" / "iCUE.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(powertoys_logs), str(google_drive_logs), str(gimp_thumbnails)])
    assert_contains_none(paths, [str(handbrake_logs), str(corsair_logs)])

def test_app_leftovers_scans_devops_database_and_markdown_tool_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "Atlassian" / "Sourcetree" / "sourcetree.log", "sourcetree"),
        (roaming / "GitKraken" / "GPUCache" / "shader.bin", "gitkraken"),
        (local / "CrashDumps" / "TortoiseGitProc.exe.1234.dmp", "tortoisegit"),
        (local / "Fork" / "logs" / "fork.log", "fork"),
        (roaming / "Lens" / "GPUCache" / "shader.bin", "lens"),
        (local / "rancher-desktop" / "logs" / "rancher.log", "rancher"),
        (roaming / "Podman Desktop" / "GPUCache" / "shader.bin", "podman"),
        (roaming / "HeidiSQL" / "logs" / "heidisql.log", "heidisql"),
        (roaming / "Microsoft" / "AppEnv" / "17.0" / "ActivityLog.xml", "ssms"),
        (roaming / "Typora" / "GPUCache" / "shader.bin", "typora"),
        (user / "src" / "repo" / ".git" / "config", "git-config"),
        (user / ".kube" / "config", "kubeconfig"),
        (user / ".ssh" / "id_ed25519", "ssh-key"),
        (user / "Documents" / "database.sql", "sql"),
        (user / "Documents" / "notes.md", "markdown"),
        (user / ".local" / "share" / "containers" / "storage" / "overlay" / "layer", "container-layer"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    sourcetree_log = cache_files[0][0]
    gitkraken_gpu_cache = cache_files[1][0].parent
    tortoisegit_dump = cache_files[2][0]
    fork_logs = cache_files[3][0].parent
    lens_gpu_cache = cache_files[4][0].parent
    rancher_logs = cache_files[5][0].parent
    podman_gpu_cache = cache_files[6][0].parent
    heidisql_logs = cache_files[7][0].parent
    ssms_activity_log = cache_files[8][0]
    typora_gpu_cache = cache_files[9][0].parent
    protected_user_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.sourcetree.logs"], {"path": str(sourcetree_log)})
    assert_field_values(by_rule["app-leftovers.gitkraken.gpu-cache"], {"path": str(gitkraken_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.tortoisegit.crashdumps"], {"path": str(tortoisegit_dump)})
    assert_field_values(by_rule["app-leftovers.fork.logs"], {"path": str(fork_logs)})
    assert_field_values(by_rule["app-leftovers.lens.gpu-cache"], {"path": str(lens_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.rancher-desktop.logs"], {"path": str(rancher_logs)})
    assert_field_values(by_rule["app-leftovers.podman-desktop.gpu-cache"], {"path": str(podman_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.heidisql.logs"], {"path": str(heidisql_logs)})
    assert_field_values(by_rule["app-leftovers.ssms.logs"], {"path": str(ssms_activity_log)})
    assert_field_values(by_rule["app-leftovers.typora.gpu-cache"], {"path": str(typora_gpu_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_user_files])

def test_app_leftovers_skips_devops_database_and_markdown_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    gitkraken_gpu_cache = roaming / "GitKraken" / "GPUCache"
    write_text_file(gitkraken_gpu_cache / "shader.bin", "gitkraken")
    write_text_file(local / "Programs" / "GitKraken" / "GitKraken.exe", "exe")

    tortoisegit_dump = local / "CrashDumps" / "TortoiseGitProc.exe.1234.dmp"
    write_text_file(tortoisegit_dump, "tortoisegit")
    write_text_file(program_files / "TortoiseGit" / "bin" / "TortoiseGitProc.exe", "exe")

    lens_gpu_cache = roaming / "Lens" / "GPUCache"
    write_text_file(lens_gpu_cache / "shader.bin", "lens")
    write_text_file(local / "Programs" / "Lens" / "Lens.exe", "exe")

    rancher_logs = local / "rancher-desktop" / "logs"
    write_text_file(rancher_logs / "rancher.log", "rancher")
    write_text_file(local / "Programs" / "Rancher Desktop" / "Rancher Desktop.exe", "exe")

    typora_gpu_cache = roaming / "Typora" / "GPUCache"
    write_text_file(typora_gpu_cache / "shader.bin", "typora")
    write_text_file(local / "Programs" / "Typora" / "Typora.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(gitkraken_gpu_cache), str(tortoisegit_dump), str(lens_gpu_cache)])
    assert_contains_none(paths, [str(rancher_logs), str(typora_gpu_cache)])

def test_app_leftovers_scans_oem_peripheral_and_creator_utility_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    user = root / "User"
    cache_files = [
        (program_data / "Dell" / "SupportAssist" / "Logs" / "supportassist.log", "dell"),
        (local / "Packages" / "E046963F.LenovoCompanion_1.0.0" / "LocalState" / "Logs" / "vantage.log", "lenovo"),
        (local / "ASUS" / "ARMOURY CRATE Service" / "Logs" / "armoury.log", "asus"),
        (local / "MSI" / "MSI Center" / "Log" / "msi.log", "msi"),
        (program_data / "SteelSeries" / "GG" / "logs" / "gg.log", "steelseries"),
        (local / "Elgato" / "Logs" / "elgato.log", "elgato"),
        (roaming / "Elgato" / "StreamDeck" / "logs" / "streamdeck.log", "streamdeck"),
        (local / "Packages" / "GoPro.GoProPlayer_1.0.0" / "LocalCache" / "GPUCache" / "shader.bin", "gopro"),
        (program_data / "Garmin" / "Logs" / "express.log", "garmin"),
        (program_data / "WTablet" / "Logs" / "tablet.log", "wacom"),
        (user / "Videos" / "Elgato" / "recording.mp4", "recording"),
        (user / "Videos" / "GoPro" / "clip.360", "gopro-media"),
        (user / "Documents" / "Stream Deck" / "profile.streamDeckProfile", "streamdeck-profile"),
        (user / "Documents" / "Wacom" / "pen-settings.json", "wacom-settings"),
        (user / "Garmin" / "Backups" / "device.fit", "garmin-backup"),
        (program_data / "Dell" / "Drivers" / "driver.cab", "dell-driver"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    dell_logs = cache_files[0][0].parent
    lenovo_logs = cache_files[1][0].parent
    armoury_logs = cache_files[2][0].parent
    msi_logs = cache_files[3][0].parent
    steelseries_logs = cache_files[4][0].parent
    elgato_logs = cache_files[5][0].parent
    stream_deck_logs = cache_files[6][0].parent
    gopro_gpu_cache = cache_files[7][0].parent
    garmin_logs = cache_files[8][0].parent
    wacom_logs = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.dell-supportassist.logs"], {"path": str(dell_logs)})
    assert_field_values(by_rule["app-leftovers.lenovo-vantage.logs"], {"path": str(lenovo_logs)})
    assert_field_values(by_rule["app-leftovers.armoury-crate.logs"], {"path": str(armoury_logs)})
    assert_field_values(by_rule["app-leftovers.msi-center.logs"], {"path": str(msi_logs)})
    assert_field_values(by_rule["app-leftovers.steelseries-gg.logs"], {"path": str(steelseries_logs)})
    assert_field_values(by_rule["app-leftovers.elgato.logs"], {"path": str(elgato_logs)})
    assert_field_values(by_rule["app-leftovers.stream-deck.logs"], {"path": str(stream_deck_logs)})
    assert_field_values(by_rule["app-leftovers.gopro-player.gpu-cache"], {"path": str(gopro_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.garmin-express.logs"], {"path": str(garmin_logs)})
    assert_field_values(by_rule["app-leftovers.wacom-tablet.logs"], {"path": str(wacom_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_oem_peripheral_and_creator_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    program_files = root / "ProgramFiles"

    armoury_logs = local / "ASUS" / "ARMOURY CRATE Service" / "Logs"
    write_text_file(armoury_logs / "armoury.log", "asus")
    write_text_file(program_files / "ASUS" / "ARMOURY CRATE Service" / "ArmouryCrate.Service.exe", "exe")

    steelseries_logs = program_data / "SteelSeries" / "GG" / "logs"
    write_text_file(steelseries_logs / "gg.log", "steelseries")
    write_text_file(program_files / "SteelSeries" / "GG" / "SteelSeriesGG.exe", "exe")

    elgato_logs = local / "Elgato" / "Logs"
    write_text_file(elgato_logs / "elgato.log", "elgato")
    write_text_file(program_files / "Elgato" / "Camera Hub" / "CameraHub.exe", "exe")

    garmin_logs = program_data / "Garmin" / "Logs"
    write_text_file(garmin_logs / "express.log", "garmin")
    write_text_file(program_files / "Garmin" / "Express" / "GarminExpress.exe", "exe")

    wacom_logs = program_data / "WTablet" / "Logs"
    write_text_file(wacom_logs / "tablet.log", "wacom")
    write_text_file(program_files / "Tablet" / "Wacom" / "Wacom_Tablet.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(armoury_logs), str(steelseries_logs), str(elgato_logs)])
    assert_contains_none(paths, [str(garmin_logs), str(wacom_logs)])

def test_app_leftovers_scans_sync_notes_screenshot_and_scanner_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "Box" / "Box" / "logs" / "box.log", "box"),
        (local / "MEGAsync" / "logs" / "mega.log", "mega"),
        (roaming / "Joplin" / "GPUCache" / "shader.bin", "joplin"),
        (roaming / "Standard Notes" / "GPUCache" / "shader.bin", "standard-notes"),
        (roaming / "Simplenote" / "GPUCache" / "shader.bin", "simplenote"),
        (user / "Documents" / "ShareX" / "Logs" / "sharex.log", "sharex"),
        (roaming / "Greenshot" / "Greenshot.log", "greenshot"),
        (local / "Skillbrains" / "lightshot" / "logs" / "lightshot.log", "lightshot"),
        (local / "ScreenToGif" / "Logs" / "screentogif.log", "screentogif"),
        (roaming / "NAPS2" / "logs" / "naps2.log", "naps2"),
        (user / "Box" / "Work" / "plan.docx", "box-file"),
        (user / "MEGA" / "Backup" / "archive.zip", "mega-file"),
        (user / "Documents" / "Joplin" / "note.md", "joplin-note"),
        (user / "Pictures" / "Screenshots" / "capture.png", "screenshot"),
        (user / "Videos" / "ScreenToGif" / "recording.gif", "gif"),
        (user / "Documents" / "Scans" / "scan.pdf", "scan"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    box_logs = cache_files[0][0].parent
    mega_logs = cache_files[1][0].parent
    joplin_gpu_cache = cache_files[2][0].parent
    standard_notes_gpu_cache = cache_files[3][0].parent
    simplenote_gpu_cache = cache_files[4][0].parent
    sharex_logs = cache_files[5][0].parent
    greenshot_log = cache_files[6][0]
    lightshot_logs = cache_files[7][0].parent
    screentogif_logs = cache_files[8][0].parent
    naps2_logs = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.box-drive.logs"], {"path": str(box_logs)})
    assert_field_values(by_rule["app-leftovers.mega.logs"], {"path": str(mega_logs)})
    assert_field_values(by_rule["app-leftovers.joplin.gpu-cache"], {"path": str(joplin_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.standard-notes.gpu-cache"], {"path": str(standard_notes_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.simplenote.gpu-cache"], {"path": str(simplenote_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.sharex.logs"], {"path": str(sharex_logs)})
    assert_field_values(by_rule["app-leftovers.greenshot.logs"], {"path": str(greenshot_log)})
    assert_field_values(by_rule["app-leftovers.lightshot.logs"], {"path": str(lightshot_logs)})
    assert_field_values(by_rule["app-leftovers.screentogif.logs"], {"path": str(screentogif_logs)})
    assert_field_values(by_rule["app-leftovers.naps2.logs"], {"path": str(naps2_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_sync_notes_screenshot_and_scanner_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    program_files = root / "ProgramFiles"

    box_logs = local / "Box" / "Box" / "logs"
    write_text_file(box_logs / "box.log", "box")
    write_text_file(program_files / "Box" / "Box" / "Box.exe", "exe")

    joplin_gpu_cache = roaming / "Joplin" / "GPUCache"
    write_text_file(joplin_gpu_cache / "shader.bin", "joplin")
    write_text_file(local / "Programs" / "Joplin" / "Joplin.exe", "exe")

    sharex_logs = user / "Documents" / "ShareX" / "Logs"
    write_text_file(sharex_logs / "sharex.log", "sharex")
    write_text_file(program_files / "ShareX" / "ShareX.exe", "exe")

    screentogif_logs = local / "ScreenToGif" / "Logs"
    write_text_file(screentogif_logs / "screentogif.log", "screentogif")
    write_text_file(local / "Programs" / "ScreenToGif" / "ScreenToGif.exe", "exe")

    naps2_logs = roaming / "NAPS2" / "logs"
    write_text_file(naps2_logs / "naps2.log", "naps2")
    write_text_file(program_files / "NAPS2" / "NAPS2.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(box_logs), str(joplin_gpu_cache), str(sharex_logs)])
    assert_contains_none(paths, [str(screentogif_logs), str(naps2_logs)])

def test_app_leftovers_scans_backup_search_password_pdf_and_chat_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (program_data / "Backblaze" / "bzdata" / "bzlogs" / "bztransmit.log", "backblaze"),
        (program_data / "Acronis" / "Logs" / "agent.log", "acronis"),
        (program_data / "Macrium" / "Reflect" / "Logs" / "reflect.log", "macrium"),
        (roaming / "FreeFileSync" / "Logs" / "freefilesync.log", "freefilesync"),
        (local / "CrashDumps" / "Everything.exe.1234.dmp", "everything"),
        (local / "CrashDumps" / "KeePassXC.exe.1234.dmp", "keepassxc"),
        (local / "CrashDumps" / "SumatraPDF.exe.1234.dmp", "sumatra"),
        (local / "Foxit Software" / "Foxit PDF Reader" / "Logs" / "reader.log", "foxit"),
        (roaming / "ViberPC" / "GPUCache" / "shader.bin", "viber"),
        (roaming / "Element" / "GPUCache" / "shader.bin", "element"),
        (user / "Backblaze" / "restore" / "restore.zip", "restore"),
        (user / "Backups" / "system.tib", "acronis-archive"),
        (user / "Backups" / "system.mrimg", "macrium-image"),
        (user / "Sync" / "source" / "report.xlsx", "sync-source"),
        (user / "Everything" / "Everything.db", "search-index"),
        (user / "Passwords" / "vault.kdbx", "password-db"),
        (user / "Books" / "manual.pdf", "pdf"),
        (user / "Documents" / "signed.pdf", "signature"),
        (user / "Pictures" / "Viber" / "photo.jpg", "viber-media"),
        (user / "Element" / "rooms" / "session.json", "element-room"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    backblaze_logs = cache_files[0][0].parent
    acronis_logs = cache_files[1][0].parent
    macrium_logs = cache_files[2][0].parent
    freefilesync_logs = cache_files[3][0].parent
    everything_dump = cache_files[4][0]
    keepassxc_dump = cache_files[5][0]
    sumatra_dump = cache_files[6][0]
    foxit_logs = cache_files[7][0].parent
    viber_gpu_cache = cache_files[8][0].parent
    element_gpu_cache = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.backblaze.logs"], {"path": str(backblaze_logs)})
    assert_field_values(by_rule["app-leftovers.acronis.logs"], {"path": str(acronis_logs)})
    assert_field_values(by_rule["app-leftovers.macrium.logs"], {"path": str(macrium_logs)})
    assert_field_values(by_rule["app-leftovers.freefilesync.logs"], {"path": str(freefilesync_logs)})
    assert_field_values(by_rule["app-leftovers.everything.crashdumps"], {"path": str(everything_dump)})
    assert_field_values(by_rule["app-leftovers.keepassxc.crashdumps"], {"path": str(keepassxc_dump)})
    assert_field_values(by_rule["app-leftovers.sumatrapdf.crashdumps"], {"path": str(sumatra_dump)})
    assert_field_values(by_rule["app-leftovers.foxit.logs"], {"path": str(foxit_logs)})
    assert_field_values(by_rule["app-leftovers.viber.gpu-cache"], {"path": str(viber_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.element.gpu-cache"], {"path": str(element_gpu_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_backup_search_password_pdf_and_chat_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    backblaze_logs = program_data / "Backblaze" / "bzdata" / "bzlogs"
    write_text_file(backblaze_logs / "bztransmit.log", "backblaze")
    write_text_file(program_files / "Backblaze" / "bzserv.exe", "exe")

    freefilesync_logs = roaming / "FreeFileSync" / "Logs"
    write_text_file(freefilesync_logs / "freefilesync.log", "freefilesync")
    write_text_file(program_files / "FreeFileSync" / "FreeFileSync.exe", "exe")

    keepassxc_dump = local / "CrashDumps" / "KeePassXC.exe.1234.dmp"
    write_text_file(keepassxc_dump, "keepassxc")
    write_text_file(program_files / "KeePassXC" / "KeePassXC.exe", "exe")

    foxit_logs = local / "Foxit Software" / "Foxit PDF Reader" / "Logs"
    write_text_file(foxit_logs / "reader.log", "foxit")
    write_text_file(program_files / "Foxit Software" / "Foxit PDF Reader" / "FoxitPDFReader.exe", "exe")

    element_gpu_cache = roaming / "Element" / "GPUCache"
    write_text_file(element_gpu_cache / "shader.bin", "element")
    write_text_file(local / "Programs" / "Element" / "Element.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(backblaze_logs), str(freefilesync_logs), str(keepassxc_dump)])
    assert_contains_none(paths, [str(foxit_logs), str(element_gpu_cache)])

def test_app_leftovers_scans_mail_reference_video_security_and_vpn_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "CrashDumps" / "thunderbird.exe.1234.dmp", "thunderbird"),
        (local / "Mailbird" / "logs" / "mailbird.log", "mailbird"),
        (roaming / "eM Client" / "logs" / "mailclient.log", "em-client"),
        (roaming / "Zotero" / "log" / "zotero.log", "zotero"),
        (local / "Mendeley Reference Manager" / "logs" / "mendeley.log", "mendeley"),
        (program_data / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "logs" / "resolve.log", "resolve"),
        (local / "Meltytech" / "Shotcut" / "logs" / "shotcut.log", "shotcut"),
        (local / "kdenlive" / "cache" / "preview.bin", "kdenlive"),
        (program_data / "Malwarebytes" / "MBAMService" / "logs" / "mbam.log", "malwarebytes"),
        (local / "NordVPN" / "logs" / "nordvpn.log", "nordvpn"),
        (roaming / "Thunderbird" / "Profiles" / "default" / "Mail" / "Inbox", "mailbox"),
        (local / "Mailbird" / "Store" / "mail.db", "mail-store"),
        (roaming / "eM Client" / "mail_data.dat", "em-database"),
        (user / "Zotero" / "storage" / "paper.pdf", "zotero-pdf"),
        (user / "Documents" / "Mendeley Desktop" / "library.sqlite", "mendeley-library"),
        (user / "Videos" / "Resolve" / "project.drp", "resolve-project"),
        (user / "Videos" / "source.mov", "source-media"),
        (user / "Videos" / "Kdenlive" / "timeline.kdenlive", "kdenlive-project"),
        (program_data / "Malwarebytes" / "MBAMService" / "Quarantine" / "quarantine.dat", "quarantine"),
        (local / "NordVPN" / "settings.dat", "vpn-settings"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    thunderbird_dump = cache_files[0][0]
    mailbird_logs = cache_files[1][0].parent
    em_client_logs = cache_files[2][0].parent
    zotero_logs = cache_files[3][0].parent
    mendeley_logs = cache_files[4][0].parent
    resolve_logs = cache_files[5][0].parent
    shotcut_logs = cache_files[6][0].parent
    kdenlive_cache = cache_files[7][0].parent
    malwarebytes_logs = cache_files[8][0].parent
    nordvpn_logs = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.thunderbird.crashdumps"], {"path": str(thunderbird_dump)})
    assert_field_values(by_rule["app-leftovers.mailbird.logs"], {"path": str(mailbird_logs)})
    assert_field_values(by_rule["app-leftovers.em-client.logs"], {"path": str(em_client_logs)})
    assert_field_values(by_rule["app-leftovers.zotero.logs"], {"path": str(zotero_logs)})
    assert_field_values(by_rule["app-leftovers.mendeley.logs"], {"path": str(mendeley_logs)})
    assert_field_values(by_rule["app-leftovers.davinci-resolve.logs"], {"path": str(resolve_logs)})
    assert_field_values(by_rule["app-leftovers.shotcut.logs"], {"path": str(shotcut_logs)})
    assert_field_values(by_rule["app-leftovers.kdenlive.cache"], {"path": str(kdenlive_cache)})
    assert_field_values(by_rule["app-leftovers.malwarebytes.logs"], {"path": str(malwarebytes_logs)})
    assert_field_values(by_rule["app-leftovers.nordvpn.logs"], {"path": str(nordvpn_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_mail_reference_video_security_and_vpn_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    mailbird_logs = local / "Mailbird" / "logs"
    write_text_file(mailbird_logs / "mailbird.log", "mailbird")
    write_text_file(program_files / "Mailbird" / "Mailbird.exe", "exe")

    zotero_logs = roaming / "Zotero" / "log"
    write_text_file(zotero_logs / "zotero.log", "zotero")
    write_text_file(program_files / "Zotero" / "zotero.exe", "exe")

    resolve_logs = program_data / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "logs"
    write_text_file(resolve_logs / "resolve.log", "resolve")
    write_text_file(program_files / "Blackmagic Design" / "DaVinci Resolve" / "Resolve.exe", "exe")

    malwarebytes_logs = program_data / "Malwarebytes" / "MBAMService" / "logs"
    write_text_file(malwarebytes_logs / "mbam.log", "malwarebytes")
    write_text_file(program_files / "Malwarebytes" / "Anti-Malware" / "mbam.exe", "exe")

    nordvpn_logs = local / "NordVPN" / "logs"
    write_text_file(nordvpn_logs / "nordvpn.log", "nordvpn")
    write_text_file(program_files / "NordVPN" / "NordVPN.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(mailbird_logs), str(zotero_logs), str(resolve_logs)])
    assert_contains_none(paths, [str(malwarebytes_logs), str(nordvpn_logs)])

def test_app_leftovers_scans_media_library_reader_meeting_password_and_vpn_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "Plex Media Server" / "Logs" / "plex.log", "plex"),
        (program_data / "Jellyfin" / "Server" / "log" / "server.log", "jellyfin"),
        (roaming / "Apple Computer" / "Logs" / "itunes.log", "itunes"),
        (local / "Amazon" / "Kindle" / "logs" / "kindle.log", "kindle"),
        (local / "Audible" / "Logs" / "audible.log", "audible"),
        (roaming / "RingCentral" / "logs" / "ringcentral.log", "ringcentral"),
        (local / "BlueJeans" / "logs" / "bluejeans.log", "bluejeans"),
        (roaming / "Bitwarden" / "GPUCache" / "shader.bin", "bitwarden"),
        (local / "ProtonVPN" / "Logs" / "protonvpn.log", "protonvpn"),
        (local / "Mullvad VPN" / "logs" / "mullvad.log", "mullvad"),
        (user / "Videos" / "Movies" / "film.mkv", "media"),
        (local / "Plex Media Server" / "Plug-in Support" / "Databases" / "library.db", "plex-db"),
        (program_data / "Jellyfin" / "Server" / "data" / "library.db", "jellyfin-db"),
        (user / "Music" / "iTunes" / "iTunes Library.itl", "itunes-library"),
        (roaming / "Apple Computer" / "MobileSync" / "Backup" / "manifest.db", "device-backup"),
        (user / "Documents" / "My Kindle Content" / "book.azw", "kindle-book"),
        (user / "Audiobooks" / "title.aax", "audiobook"),
        (user / "Videos" / "RingCentral" / "meeting.mp4", "recording"),
        (user / "Documents" / "BlueJeans" / "chat.txt", "meeting-chat"),
        (roaming / "Bitwarden" / "data.json", "vault"),
        (local / "ProtonVPN" / "settings.json", "proton-settings"),
        (local / "Mullvad VPN" / "settings.ini", "mullvad-settings"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    plex_logs = cache_files[0][0].parent
    jellyfin_logs = cache_files[1][0].parent
    itunes_logs = cache_files[2][0].parent
    kindle_logs = cache_files[3][0].parent
    audible_logs = cache_files[4][0].parent
    ringcentral_logs = cache_files[5][0].parent
    bluejeans_logs = cache_files[6][0].parent
    bitwarden_gpu_cache = cache_files[7][0].parent
    protonvpn_logs = cache_files[8][0].parent
    mullvad_logs = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.plex.logs"], {"path": str(plex_logs)})
    assert_field_values(by_rule["app-leftovers.jellyfin.logs"], {"path": str(jellyfin_logs)})
    assert_field_values(by_rule["app-leftovers.itunes.logs"], {"path": str(itunes_logs)})
    assert_field_values(by_rule["app-leftovers.kindle.logs"], {"path": str(kindle_logs)})
    assert_field_values(by_rule["app-leftovers.audible.logs"], {"path": str(audible_logs)})
    assert_field_values(by_rule["app-leftovers.ringcentral.logs"], {"path": str(ringcentral_logs)})
    assert_field_values(by_rule["app-leftovers.bluejeans.logs"], {"path": str(bluejeans_logs)})
    assert_field_values(by_rule["app-leftovers.bitwarden.gpu-cache"], {"path": str(bitwarden_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.protonvpn.logs"], {"path": str(protonvpn_logs)})
    assert_field_values(by_rule["app-leftovers.mullvad-vpn.logs"], {"path": str(mullvad_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_media_library_reader_meeting_password_and_vpn_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    plex_logs = local / "Plex Media Server" / "Logs"
    write_text_file(plex_logs / "plex.log", "plex")
    write_text_file(program_files / "Plex" / "Plex Media Server" / "Plex Media Server.exe", "exe")

    jellyfin_logs = program_data / "Jellyfin" / "Server" / "log"
    write_text_file(jellyfin_logs / "server.log", "jellyfin")
    write_text_file(program_files / "Jellyfin" / "Server" / "jellyfin.exe", "exe")

    bitwarden_gpu_cache = roaming / "Bitwarden" / "GPUCache"
    write_text_file(bitwarden_gpu_cache / "shader.bin", "bitwarden")
    write_text_file(local / "Programs" / "Bitwarden" / "Bitwarden.exe", "exe")

    protonvpn_logs = local / "ProtonVPN" / "Logs"
    write_text_file(protonvpn_logs / "protonvpn.log", "protonvpn")
    write_text_file(program_files / "Proton" / "VPN" / "ProtonVPN.exe", "exe")

    mullvad_logs = local / "Mullvad VPN" / "logs"
    write_text_file(mullvad_logs / "mullvad.log", "mullvad")
    write_text_file(program_files / "Mullvad VPN" / "Mullvad VPN.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(plex_logs), str(jellyfin_logs), str(bitwarden_gpu_cache)])
    assert_contains_none(paths, [str(protonvpn_logs), str(mullvad_logs)])

def test_app_leftovers_scans_cleaner_disk_hardware_and_viewer_logs(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (program_data / "CCleaner" / "LOG" / "ccleaner.log", "ccleaner"),
        (roaming / "VS Revo Group" / "Revo Uninstaller Pro" / "Logs" / "revo.log", "revo"),
        (local / "BleachBit" / "logs" / "bleachbit.log", "bleachbit"),
        (roaming / "windirstat.ini", "windirstat"),
        (local / "Antibody Software" / "WizTree" / "Logs" / "wiztree.log", "wiztree"),
        (local / "JAM Software" / "TreeSize Free" / "logs" / "treesize.log", "treesize"),
        (local / "HWiNFO64" / "Logs" / "hwinfo.log", "hwinfo"),
        (program_data / "CPUID" / "CPU-Z" / "logs" / "cpuz.log", "cpuz"),
        (local / "TechPowerUp" / "GPU-Z" / "logs" / "gpuz.log", "gpuz"),
        (roaming / "IrfanView" / "Thumbs" / "thumb.db", "irfanview"),
        (program_data / "CCleaner" / "Backups" / "registry.reg", "ccleaner-backup"),
        (roaming / "VS Revo Group" / "Revo Uninstaller Pro" / "Backups" / "backup.dat", "revo-backup"),
        (user / "Documents" / "BleachBit" / "custom-paths.txt", "bleachbit-custom"),
        (user / "Documents" / "WinDirStat" / "scan.csv", "windirstat-scan"),
        (user / "Documents" / "WizTree" / "export.csv", "wiztree-export"),
        (user / "Documents" / "TreeSize" / "report.xlsx", "treesize-report"),
        (user / "Documents" / "HWiNFO" / "sensors.csv", "hwinfo-report"),
        (user / "Documents" / "CPU-Z" / "validation.html", "cpuz-validation"),
        (user / "Documents" / "GPU-Z" / "bios.rom", "gpuz-bios"),
        (user / "Pictures" / "Photos" / "image.jpg", "image"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    ccleaner_logs = cache_files[0][0].parent
    revo_logs = cache_files[1][0].parent
    bleachbit_logs = cache_files[2][0].parent
    windirstat_ini = cache_files[3][0]
    wiztree_logs = cache_files[4][0].parent
    treesize_logs = cache_files[5][0].parent
    hwinfo_logs = cache_files[6][0].parent
    cpuz_logs = cache_files[7][0].parent
    gpuz_logs = cache_files[8][0].parent
    irfanview_thumbs = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.ccleaner.logs"], {"path": str(ccleaner_logs)})
    assert_field_values(by_rule["app-leftovers.revo-uninstaller.logs"], {"path": str(revo_logs)})
    assert_field_values(by_rule["app-leftovers.bleachbit.logs"], {"path": str(bleachbit_logs)})
    assert_field_values(by_rule["app-leftovers.windirstat.ini"], {"path": str(windirstat_ini)})
    assert_field_values(by_rule["app-leftovers.wiztree.logs"], {"path": str(wiztree_logs)})
    assert_field_values(by_rule["app-leftovers.treesize-free.logs"], {"path": str(treesize_logs)})
    assert_field_values(by_rule["app-leftovers.hwinfo.logs"], {"path": str(hwinfo_logs)})
    assert_field_values(by_rule["app-leftovers.cpu-z.logs"], {"path": str(cpuz_logs)})
    assert_field_values(by_rule["app-leftovers.gpu-z.logs"], {"path": str(gpuz_logs)})
    assert_field_values(by_rule["app-leftovers.irfanview.thumbnails"], {"path": str(irfanview_thumbs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_cleaner_disk_hardware_and_viewer_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    program_data = root / "ProgramData"
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    ccleaner_logs = program_data / "CCleaner" / "LOG"
    write_text_file(ccleaner_logs / "ccleaner.log", "ccleaner")
    write_text_file(program_files / "CCleaner" / "CCleaner64.exe", "exe")

    bleachbit_logs = local / "BleachBit" / "logs"
    write_text_file(bleachbit_logs / "bleachbit.log", "bleachbit")
    write_text_file(program_files / "BleachBit" / "bleachbit.exe", "exe")

    wiztree_logs = local / "Antibody Software" / "WizTree" / "Logs"
    write_text_file(wiztree_logs / "wiztree.log", "wiztree")
    write_text_file(program_files / "WizTree" / "WizTree64.exe", "exe")

    hwinfo_logs = local / "HWiNFO64" / "Logs"
    write_text_file(hwinfo_logs / "hwinfo.log", "hwinfo")
    write_text_file(program_files / "HWiNFO64" / "HWiNFO64.exe", "exe")

    irfanview_thumbs = roaming / "IrfanView" / "Thumbs"
    write_text_file(irfanview_thumbs / "thumb.db", "irfanview")
    write_text_file(program_files / "IrfanView" / "i_view64.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(ccleaner_logs), str(bleachbit_logs), str(wiztree_logs)])
    assert_contains_none(paths, [str(hwinfo_logs), str(irfanview_thumbs)])

def test_app_leftovers_scans_image_audio_media_and_editor_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "CrashDumps" / "paintdotnet.exe.1234.dmp", "paintdotnet"),
        (roaming / "XnViewMP" / "Thumbs" / "thumb.db", "xnview"),
        (local / "nomacs" / "cache" / "entry", "nomacs"),
        (roaming / "FastStone" / "FSViewer" / "Thumbs" / "thumb.db", "faststone"),
        (roaming / "foobar2000" / "logs" / "foobar.log", "foobar"),
        (roaming / "AIMP" / "Logs" / "aimp.log", "aimp"),
        (local / "mpv" / "cache" / "entry", "mpv"),
        (local / "MPC-HC" / "Logs" / "mpc-hc.log", "mpc"),
        (roaming / "PotPlayerMini64" / "Log" / "potplayer.log", "potplayer"),
        (roaming / "Notepad++" / "backup" / "new 1@2026-06-26.bak", "npp"),
        (local / "Sublime Text" / "Cache" / "entry", "sublime"),
        (user / "Pictures" / "Photos" / "image.jpg", "image"),
        (user / "Music" / "Library" / "song.flac", "music"),
        (user / "Videos" / "Movies" / "movie.mkv", "video"),
        (user / "Documents" / "Notes" / "draft.txt", "document"),
        (roaming / "Notepad++" / "plugins" / "plugin.dll", "npp-plugin"),
        (roaming / "foobar2000" / "playlists" / "library.fpl", "playlist"),
        (local / "Sublime Text" / "Packages" / "User" / "Preferences.sublime-settings", "settings"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    paintnet_dump = cache_files[0][0]
    xnview_thumbs = cache_files[1][0].parent
    nomacs_cache = cache_files[2][0].parent
    faststone_thumbs = cache_files[3][0].parent
    foobar_logs = cache_files[4][0].parent
    aimp_logs = cache_files[5][0].parent
    mpv_cache = cache_files[6][0].parent
    mpc_logs = cache_files[7][0].parent
    potplayer_logs = cache_files[8][0].parent
    notepad_backups = cache_files[9][0].parent
    sublime_cache = cache_files[10][0].parent
    protected_files = [path for path, _ in cache_files[11:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.paintdotnet.crashdumps"], {"path": str(paintnet_dump)})
    assert_field_values(by_rule["app-leftovers.xnviewmp.thumbnails"], {"path": str(xnview_thumbs)})
    assert_field_values(by_rule["app-leftovers.nomacs.cache"], {"path": str(nomacs_cache)})
    assert_field_values(by_rule["app-leftovers.faststone.thumbnails"], {"path": str(faststone_thumbs)})
    assert_field_values(by_rule["app-leftovers.foobar2000.logs"], {"path": str(foobar_logs)})
    assert_field_values(by_rule["app-leftovers.aimp.logs"], {"path": str(aimp_logs)})
    assert_field_values(by_rule["app-leftovers.mpv.cache"], {"path": str(mpv_cache)})
    assert_field_values(by_rule["app-leftovers.mpc-hc.logs"], {"path": str(mpc_logs)})
    assert_field_values(by_rule["app-leftovers.potplayer.logs"], {"path": str(potplayer_logs)})
    assert_field_values(by_rule["app-leftovers.notepad-plus-plus.backups"], {"path": str(notepad_backups)})
    assert_field_values(by_rule["app-leftovers.sublime-text.cache"], {"path": str(sublime_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_image_audio_media_and_editor_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    paintnet_dump = local / "CrashDumps" / "paintdotnet.exe.1234.dmp"
    write_text_file(paintnet_dump, "paintdotnet")
    write_text_file(program_files / "paint.net" / "paintdotnet.exe", "exe")

    xnview_thumbs = roaming / "XnViewMP" / "Thumbs"
    write_text_file(xnview_thumbs / "thumb.db", "xnview")
    write_text_file(program_files / "XnViewMP" / "xnviewmp.exe", "exe")

    nomacs_cache = local / "nomacs" / "cache"
    write_text_file(nomacs_cache / "entry", "nomacs")
    write_text_file(program_files / "nomacs" / "bin" / "nomacs.exe", "exe")

    faststone_thumbs = roaming / "FastStone" / "FSViewer" / "Thumbs"
    write_text_file(faststone_thumbs / "thumb.db", "faststone")
    write_text_file(program_files / "FastStone Image Viewer" / "FSViewer.exe", "exe")

    foobar_logs = roaming / "foobar2000" / "logs"
    write_text_file(foobar_logs / "foobar.log", "foobar")
    write_text_file(program_files / "foobar2000" / "foobar2000.exe", "exe")

    aimp_logs = roaming / "AIMP" / "Logs"
    write_text_file(aimp_logs / "aimp.log", "aimp")
    write_text_file(program_files / "AIMP" / "AIMP.exe", "exe")

    mpv_cache = local / "mpv" / "cache"
    write_text_file(mpv_cache / "entry", "mpv")
    write_text_file(program_files / "mpv" / "mpv.exe", "exe")

    mpc_logs = local / "MPC-HC" / "Logs"
    write_text_file(mpc_logs / "mpc-hc.log", "mpc")
    write_text_file(program_files / "MPC-HC" / "mpc-hc64.exe", "exe")

    potplayer_logs = roaming / "PotPlayerMini64" / "Log"
    write_text_file(potplayer_logs / "potplayer.log", "potplayer")
    write_text_file(program_files / "DAUM" / "PotPlayer" / "PotPlayerMini64.exe", "exe")

    notepad_backups = roaming / "Notepad++" / "backup"
    write_text_file(notepad_backups / "new 1@2026-06-26.bak", "npp")
    write_text_file(program_files / "Notepad++" / "notepad++.exe", "exe")

    sublime_cache = local / "Sublime Text" / "Cache"
    write_text_file(sublime_cache / "entry", "sublime")
    write_text_file(program_files / "Sublime Text" / "sublime_text.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(paintnet_dump), str(xnview_thumbs), str(nomacs_cache), str(faststone_thumbs)])
    assert_contains_none(paths, [str(foobar_logs), str(aimp_logs), str(mpv_cache), str(mpc_logs)])
    assert_contains_none(paths, [str(potplayer_logs), str(notepad_backups), str(sublime_cache)])

def test_app_leftovers_scans_archive_and_image_writer_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "CrashDumps" / "7zFM.exe.1234.dmp", "7zip"),
        (local / "CrashDumps" / "WinRAR.exe.1234.dmp", "winrar"),
        (local / "CrashDumps" / "peazip.exe.1234.dmp", "peazip"),
        (local / "CrashDumps" / "Bandizip.exe.1234.dmp", "bandizip"),
        (local / "CrashDumps" / "NanaZip.exe.1234.dmp", "nanazip"),
        (local / "CrashDumps" / "rufus.exe.1234.dmp", "rufus"),
        (roaming / "balenaEtcher" / "logs" / "etcher.log", "etcher"),
        (roaming / "Raspberry Pi Imager" / "logs" / "imager.log", "imager"),
        (local / "CrashDumps" / "Ventoy2Disk.exe.1234.dmp", "ventoy"),
        (local / "CrashDumps" / "Win32DiskImager.exe.1234.dmp", "diskimager"),
        (user / "Downloads" / "archives" / "backup.zip", "archive"),
        (user / "Downloads" / "archives" / "installer.rar", "rar"),
        (user / "Downloads" / "images" / "linux.iso", "iso"),
        (user / "Documents" / "boot" / "custom-config.toml", "config"),
        (roaming / "Raspberry Pi Imager" / "settings.json", "settings"),
        (roaming / "Raspberry Pi Imager" / "ssh" / "id_rsa", "key"),
        (roaming / "balenaEtcher" / "flash-results.json", "history"),
        (user / "Documents" / "Ventoy" / "persistence.dat", "persistence"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    sevenzip_dump = cache_files[0][0]
    winrar_dump = cache_files[1][0]
    peazip_dump = cache_files[2][0]
    bandizip_dump = cache_files[3][0]
    nanazip_dump = cache_files[4][0]
    rufus_dump = cache_files[5][0]
    etcher_logs = cache_files[6][0].parent
    imager_logs = cache_files[7][0].parent
    ventoy_dump = cache_files[8][0]
    win32diskimager_dump = cache_files[9][0]
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.7zip.crashdumps"], {"path": str(sevenzip_dump)})
    assert_field_values(by_rule["app-leftovers.winrar.crashdumps"], {"path": str(winrar_dump)})
    assert_field_values(by_rule["app-leftovers.peazip.crashdumps"], {"path": str(peazip_dump)})
    assert_field_values(by_rule["app-leftovers.bandizip.crashdumps"], {"path": str(bandizip_dump)})
    assert_field_values(by_rule["app-leftovers.nanazip.crashdumps"], {"path": str(nanazip_dump)})
    assert_field_values(by_rule["app-leftovers.rufus.crashdumps"], {"path": str(rufus_dump)})
    assert_field_values(by_rule["app-leftovers.balenaetcher.logs"], {"path": str(etcher_logs)})
    assert_field_values(by_rule["app-leftovers.raspberry-pi-imager.logs"], {"path": str(imager_logs)})
    assert_field_values(by_rule["app-leftovers.ventoy.crashdumps"], {"path": str(ventoy_dump)})
    assert_field_values(by_rule["app-leftovers.win32diskimager.crashdumps"], {"path": str(win32diskimager_dump)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_archive_and_image_writer_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    sevenzip_dump = local / "CrashDumps" / "7zFM.exe.1234.dmp"
    write_text_file(sevenzip_dump, "7zip")
    write_text_file(program_files / "7-Zip" / "7zFM.exe", "exe")

    winrar_dump = local / "CrashDumps" / "WinRAR.exe.1234.dmp"
    write_text_file(winrar_dump, "winrar")
    write_text_file(program_files / "WinRAR" / "WinRAR.exe", "exe")

    peazip_dump = local / "CrashDumps" / "peazip.exe.1234.dmp"
    write_text_file(peazip_dump, "peazip")
    write_text_file(program_files / "PeaZip" / "peazip.exe", "exe")

    bandizip_dump = local / "CrashDumps" / "Bandizip.exe.1234.dmp"
    write_text_file(bandizip_dump, "bandizip")
    write_text_file(program_files / "Bandizip" / "Bandizip.exe", "exe")

    nanazip_dump = local / "CrashDumps" / "NanaZip.exe.1234.dmp"
    write_text_file(nanazip_dump, "nanazip")
    write_text_file(local / "Microsoft" / "WindowsApps" / "NanaZip.exe", "exe")

    rufus_dump = local / "CrashDumps" / "rufus.exe.1234.dmp"
    write_text_file(rufus_dump, "rufus")
    write_text_file(program_files / "Rufus" / "rufus.exe", "exe")

    etcher_logs = roaming / "balenaEtcher" / "logs"
    write_text_file(etcher_logs / "etcher.log", "etcher")
    write_text_file(local / "Programs" / "balenaEtcher" / "balenaEtcher.exe", "exe")

    imager_logs = roaming / "Raspberry Pi Imager" / "logs"
    write_text_file(imager_logs / "imager.log", "imager")
    write_text_file(local / "Programs" / "Raspberry Pi Imager" / "rpi-imager.exe", "exe")

    ventoy_dump = local / "CrashDumps" / "Ventoy2Disk.exe.1234.dmp"
    write_text_file(ventoy_dump, "ventoy")
    write_text_file(program_files / "Ventoy" / "Ventoy2Disk.exe", "exe")

    win32diskimager_dump = local / "CrashDumps" / "Win32DiskImager.exe.1234.dmp"
    write_text_file(win32diskimager_dump, "diskimager")
    write_text_file(program_files / "Win32DiskImager" / "Win32DiskImager.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(sevenzip_dump), str(winrar_dump), str(peazip_dump), str(bandizip_dump)])
    assert_contains_none(paths, [str(nanazip_dump), str(rufus_dump), str(etcher_logs), str(imager_logs)])
    assert_contains_none(paths, [str(ventoy_dump), str(win32diskimager_dump)])

def test_app_leftovers_scans_terminal_and_ssh_client_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (local / "CrashDumps" / "putty.exe.1234.dmp", "putty"),
        (local / "SuperPuTTY" / "logs" / "superputty.log", "superputty"),
        (local / "mRemoteNG" / "logs" / "mremote.log", "mremote"),
        (roaming / "Termius" / "logs" / "termius.log", "termius"),
        (local / "Mobatek" / "MobaXterm" / "logs" / "moba.log", "mobaxterm"),
        (local / "code4ward" / "Royal TS" / "Logs" / "royalts.log", "royalts"),
        (local / "Bitvise" / "SSH Client" / "Logs" / "bitvise.log", "bitvise"),
        (local / "cygwin" / "setup.log", "cygwin"),
        (local / "msys2" / "setup.log", "msys2"),
        (local / "CrashDumps" / "alacritty.exe.1234.dmp", "alacritty"),
        (roaming / "PuTTY" / "sessions" / "prod", "session"),
        (roaming / "PuTTY" / "sshhostkeys", "hostkey"),
        (user / ".ssh" / "id_rsa", "private-key"),
        (user / ".ssh" / "known_hosts", "known-hosts"),
        (local / "mRemoteNG" / "confCons.xml", "connections"),
        (roaming / "Termius" / "vault" / "vault.db", "vault"),
        (user / "Documents" / "RoyalTS" / "connections.rtsz", "royalts-doc"),
        (user / ".bash_history", "history"),
        (user / "Downloads" / "session.log", "terminal-log"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    putty_dump = cache_files[0][0]
    superputty_logs = cache_files[1][0].parent
    mremoteng_logs = cache_files[2][0].parent
    termius_logs = cache_files[3][0].parent
    mobaxterm_logs = cache_files[4][0].parent
    royalts_logs = cache_files[5][0].parent
    bitvise_logs = cache_files[6][0].parent
    cygwin_setup_log = cache_files[7][0]
    msys2_setup_log = cache_files[8][0]
    alacritty_dump = cache_files[9][0]
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.putty.crashdumps"], {"path": str(putty_dump)})
    assert_field_values(by_rule["app-leftovers.superputty.logs"], {"path": str(superputty_logs)})
    assert_field_values(by_rule["app-leftovers.mremoteng.logs"], {"path": str(mremoteng_logs)})
    assert_field_values(by_rule["app-leftovers.termius.logs"], {"path": str(termius_logs)})
    assert_field_values(by_rule["app-leftovers.mobaxterm.logs"], {"path": str(mobaxterm_logs)})
    assert_field_values(by_rule["app-leftovers.royal-ts.logs"], {"path": str(royalts_logs)})
    assert_field_values(by_rule["app-leftovers.bitvise-ssh-client.logs"], {"path": str(bitvise_logs)})
    assert_field_values(by_rule["app-leftovers.cygwin-setup.logs"], {"path": str(cygwin_setup_log)})
    assert_field_values(by_rule["app-leftovers.msys2-setup.logs"], {"path": str(msys2_setup_log)})
    assert_field_values(by_rule["app-leftovers.alacritty.crashdumps"], {"path": str(alacritty_dump)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_terminal_and_ssh_client_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    putty_dump = local / "CrashDumps" / "putty.exe.1234.dmp"
    write_text_file(putty_dump, "putty")
    write_text_file(program_files / "PuTTY" / "putty.exe", "exe")

    superputty_logs = local / "SuperPuTTY" / "logs"
    write_text_file(superputty_logs / "superputty.log", "superputty")
    write_text_file(program_files / "SuperPuTTY" / "SuperPuTTY.exe", "exe")

    mremoteng_logs = local / "mRemoteNG" / "logs"
    write_text_file(mremoteng_logs / "mremote.log", "mremote")
    write_text_file(program_files / "mRemoteNG" / "mRemoteNG.exe", "exe")

    termius_logs = roaming / "Termius" / "logs"
    write_text_file(termius_logs / "termius.log", "termius")
    write_text_file(local / "Programs" / "Termius" / "Termius.exe", "exe")

    mobaxterm_logs = local / "Mobatek" / "MobaXterm" / "logs"
    write_text_file(mobaxterm_logs / "moba.log", "mobaxterm")
    write_text_file(program_files / "Mobatek" / "MobaXterm" / "MobaXterm.exe", "exe")

    royalts_logs = local / "code4ward" / "Royal TS" / "Logs"
    write_text_file(royalts_logs / "royalts.log", "royalts")
    write_text_file(program_files / "Royal TS V7" / "RoyalTS.exe", "exe")

    bitvise_logs = local / "Bitvise" / "SSH Client" / "Logs"
    write_text_file(bitvise_logs / "bitvise.log", "bitvise")
    write_text_file(program_files / "Bitvise SSH Client" / "BvSsh.exe", "exe")

    cygwin_setup_log = local / "cygwin" / "setup.log"
    write_text_file(cygwin_setup_log, "cygwin")
    write_text_file(program_files / "Cygwin" / "Cygwin.bat", "bat")

    msys2_setup_log = local / "msys2" / "setup.log"
    write_text_file(msys2_setup_log, "msys2")
    write_text_file(program_files / "msys64" / "msys2.exe", "exe")

    alacritty_dump = local / "CrashDumps" / "alacritty.exe.1234.dmp"
    write_text_file(alacritty_dump, "alacritty")
    write_text_file(program_files / "Alacritty" / "alacritty.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(putty_dump), str(superputty_logs), str(mremoteng_logs), str(termius_logs)])
    assert_contains_none(paths, [str(mobaxterm_logs), str(royalts_logs), str(bitvise_logs)])
    assert_contains_none(paths, [str(cygwin_setup_log), str(msys2_setup_log), str(alacritty_dump)])

def test_app_leftovers_scans_live_capture_and_audio_tool_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "slobs-client" / "node-obs" / "logs" / "streamlabs.log", "streamlabs"),
        (local / "SplitmediaLabs" / "XSplit" / "logs" / "xsplit.log", "xsplit"),
        (local / "Bandicam" / "logs" / "bandicam.log", "bandicam"),
        (local / "Mirillis" / "Action!" / "Logs" / "action.log", "action"),
        (roaming / "REAPER" / "CrashLogs" / "reaper-crash.log", "reaper"),
        (roaming / "Image-Line" / "FL Studio" / "Logs" / "fl.log", "fl"),
        (roaming / "Ableton" / "Live Reports" / "crash-report.zip", "ableton"),
        (local / "Steinberg" / "CrashDumps" / "cubase.dmp", "cubase"),
        (local / "VB" / "Voicemeeter" / "logs" / "voicemeeter.log", "voicemeeter"),
        (local / "Voicemod" / "logs" / "voicemod.log", "voicemod"),
        (user / "Videos" / "Captures" / "recording.mp4", "recording"),
        (user / "Pictures" / "Screenshots" / "capture.png", "screenshot"),
        (user / "Music" / "Projects" / "song.rpp", "reaper-project"),
        (user / "Music" / "Projects" / "track.flp", "fl-project"),
        (user / "Music" / "Ableton" / "set.als", "ableton-set"),
        (user / "Music" / "Samples" / "kick.wav", "sample"),
        (roaming / "obs-studio" / "basic" / "scenes" / "scene.json", "scene"),
        (roaming / "Image-Line" / "FL Studio" / "Presets" / "preset.fst", "preset"),
        (local / "VB" / "Voicemeeter" / "settings.xml", "voicemeeter-settings"),
        (local / "Voicemod" / "recordings" / "voice.wav", "voice-recording"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    streamlabs_logs = cache_files[0][0].parent
    xsplit_logs = cache_files[1][0].parent
    bandicam_logs = cache_files[2][0].parent
    action_logs = cache_files[3][0].parent
    reaper_logs = cache_files[4][0].parent
    fl_studio_logs = cache_files[5][0].parent
    ableton_reports = cache_files[6][0].parent
    cubase_dumps = cache_files[7][0].parent
    voicemeeter_logs = cache_files[8][0].parent
    voicemod_logs = cache_files[9][0].parent
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.streamlabs.logs"], {"path": str(streamlabs_logs)})
    assert_field_values(by_rule["app-leftovers.xsplit.logs"], {"path": str(xsplit_logs)})
    assert_field_values(by_rule["app-leftovers.bandicam.logs"], {"path": str(bandicam_logs)})
    assert_field_values(by_rule["app-leftovers.mirillis-action.logs"], {"path": str(action_logs)})
    assert_field_values(by_rule["app-leftovers.reaper.logs"], {"path": str(reaper_logs)})
    assert_field_values(by_rule["app-leftovers.fl-studio.logs"], {"path": str(fl_studio_logs)})
    assert_field_values(by_rule["app-leftovers.ableton-live.crashdumps"], {"path": str(ableton_reports)})
    assert_field_values(by_rule["app-leftovers.steinberg-cubase.logs"], {"path": str(cubase_dumps)})
    assert_field_values(by_rule["app-leftovers.voicemeeter.logs"], {"path": str(voicemeeter_logs)})
    assert_field_values(by_rule["app-leftovers.voicemod.logs"], {"path": str(voicemod_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_live_capture_and_audio_tool_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    streamlabs_logs = roaming / "slobs-client" / "node-obs" / "logs"
    write_text_file(streamlabs_logs / "streamlabs.log", "streamlabs")
    write_text_file(local / "Programs" / "streamlabs-desktop" / "Streamlabs Desktop.exe", "exe")

    xsplit_logs = local / "SplitmediaLabs" / "XSplit" / "logs"
    write_text_file(xsplit_logs / "xsplit.log", "xsplit")
    write_text_file(program_files / "SplitmediaLabs" / "XSplit Broadcaster" / "XSplit.Core.exe", "exe")

    bandicam_logs = local / "Bandicam" / "logs"
    write_text_file(bandicam_logs / "bandicam.log", "bandicam")
    write_text_file(program_files / "Bandicam" / "bdcam.exe", "exe")

    action_logs = local / "Mirillis" / "Action!" / "Logs"
    write_text_file(action_logs / "action.log", "action")
    write_text_file(program_files / "Mirillis" / "Action!" / "Action.exe", "exe")

    reaper_logs = roaming / "REAPER" / "CrashLogs"
    write_text_file(reaper_logs / "reaper-crash.log", "reaper")
    write_text_file(program_files / "REAPER (x64)" / "reaper.exe", "exe")

    fl_studio_logs = roaming / "Image-Line" / "FL Studio" / "Logs"
    write_text_file(fl_studio_logs / "fl.log", "fl")
    write_text_file(program_files / "Image-Line" / "FL Studio 21" / "FL64.exe", "exe")

    ableton_reports = roaming / "Ableton" / "Live Reports"
    write_text_file(ableton_reports / "crash-report.zip", "ableton")
    write_text_file(program_files / "Ableton" / "Live 12 Suite" / "Program" / "Ableton Live 12 Suite.exe", "exe")

    cubase_dumps = local / "Steinberg" / "CrashDumps"
    write_text_file(cubase_dumps / "cubase.dmp", "cubase")
    write_text_file(program_files / "Steinberg" / "Cubase 13" / "Cubase13.exe", "exe")

    voicemeeter_logs = local / "VB" / "Voicemeeter" / "logs"
    write_text_file(voicemeeter_logs / "voicemeeter.log", "voicemeeter")
    write_text_file(program_files / "VB" / "Voicemeeter" / "voicemeeter8.exe", "exe")

    voicemod_logs = local / "Voicemod" / "logs"
    write_text_file(voicemod_logs / "voicemod.log", "voicemod")
    write_text_file(local / "Programs" / "Voicemod Desktop" / "VoicemodDesktop.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(streamlabs_logs), str(xsplit_logs), str(bandicam_logs), str(action_logs)])
    assert_contains_none(paths, [str(reaper_logs), str(fl_studio_logs), str(ableton_reports), str(cubase_dumps)])
    assert_contains_none(paths, [str(voicemeeter_logs), str(voicemod_logs)])

def test_app_leftovers_scans_3d_printing_modeling_and_cad_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "cura" / "5.7" / "cura.log", "cura"),
        (roaming / "PrusaSlicer" / "logs" / "prusaslicer.log", "prusaslicer"),
        (roaming / "BambuStudio" / "log" / "bambu.log", "bambu"),
        (roaming / "OrcaSlicer" / "log" / "orca.log", "orca"),
        (roaming / "CHITUBOX" / "logs" / "chitubox.log", "chitubox"),
        (roaming / "LycheeSlicer" / "logs" / "lychee.log", "lychee"),
        (local / "CrashDumps" / "FreeCAD.exe.1234.dmp", "freecad"),
        (local / "OpenSCAD" / "logs" / "openscad.log", "openscad"),
        (local / "Autodesk" / "Autodesk Fusion 360" / "logs" / "fusion.log", "fusion"),
        (local / "CrashDumps" / "SLDWORKS.exe.1234.dmp", "solidworks"),
        (user / "Documents" / "3D Models" / "part.stl", "stl"),
        (user / "Documents" / "3D Models" / "slice.gcode", "gcode"),
        (user / "Documents" / "PrusaSlicer" / "project.3mf", "project"),
        (roaming / "cura" / "5.7" / "quality" / "profile.cfg", "cura-profile"),
        (roaming / "PrusaSlicer" / "printer" / "printer.ini", "printer-profile"),
        (roaming / "BambuStudio" / "system" / "network.json", "printer-network"),
        (roaming / "CHITUBOX" / "machine" / "resin.cfg", "resin-profile"),
        (user / "Documents" / "FreeCAD" / "assembly.FCStd", "freecad-doc"),
        (user / "Documents" / "OpenSCAD" / "model.scad", "openscad-script"),
        (user / "Documents" / "SOLIDWORKS" / "assembly.sldasm", "solidworks-assembly"),
        (local / "Autodesk" / "Autodesk Fusion 360" / "credentials.json", "fusion-credentials"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    cura_log = cache_files[0][0]
    prusaslicer_logs = cache_files[1][0].parent
    bambu_logs = cache_files[2][0].parent
    orca_logs = cache_files[3][0].parent
    chitubox_logs = cache_files[4][0].parent
    lychee_logs = cache_files[5][0].parent
    freecad_dump = cache_files[6][0]
    openscad_logs = cache_files[7][0].parent
    fusion_logs = cache_files[8][0].parent
    solidworks_dump = cache_files[9][0]
    protected_files = [path for path, _ in cache_files[10:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.ultimaker-cura.logs"], {"path": str(cura_log)})
    assert_field_values(by_rule["app-leftovers.prusaslicer.logs"], {"path": str(prusaslicer_logs)})
    assert_field_values(by_rule["app-leftovers.bambu-studio.logs"], {"path": str(bambu_logs)})
    assert_field_values(by_rule["app-leftovers.orca-slicer.logs"], {"path": str(orca_logs)})
    assert_field_values(by_rule["app-leftovers.chitubox.logs"], {"path": str(chitubox_logs)})
    assert_field_values(by_rule["app-leftovers.lychee-slicer.logs"], {"path": str(lychee_logs)})
    assert_field_values(by_rule["app-leftovers.freecad.crashdumps"], {"path": str(freecad_dump)})
    assert_field_values(by_rule["app-leftovers.openscad.logs"], {"path": str(openscad_logs)})
    assert_field_values(by_rule["app-leftovers.fusion360.logs"], {"path": str(fusion_logs)})
    assert_field_values(by_rule["app-leftovers.solidworks.crashdumps"], {"path": str(solidworks_dump)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_3d_printing_modeling_and_cad_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    cura_log = roaming / "cura" / "5.7" / "cura.log"
    write_text_file(cura_log, "cura")
    write_text_file(program_files / "UltiMaker Cura 5.7" / "UltiMaker-Cura.exe", "exe")

    prusaslicer_logs = roaming / "PrusaSlicer" / "logs"
    write_text_file(prusaslicer_logs / "prusaslicer.log", "prusaslicer")
    write_text_file(program_files / "Prusa3D" / "PrusaSlicer" / "prusa-slicer.exe", "exe")

    bambu_logs = roaming / "BambuStudio" / "log"
    write_text_file(bambu_logs / "bambu.log", "bambu")
    write_text_file(program_files / "Bambu Studio" / "bambu-studio.exe", "exe")

    orca_logs = roaming / "OrcaSlicer" / "log"
    write_text_file(orca_logs / "orca.log", "orca")
    write_text_file(program_files / "OrcaSlicer" / "orca-slicer.exe", "exe")

    chitubox_logs = roaming / "CHITUBOX" / "logs"
    write_text_file(chitubox_logs / "chitubox.log", "chitubox")
    write_text_file(program_files / "CHITUBOX" / "CHITUBOX.exe", "exe")

    lychee_logs = roaming / "LycheeSlicer" / "logs"
    write_text_file(lychee_logs / "lychee.log", "lychee")
    write_text_file(local / "Programs" / "LycheeSlicer" / "LycheeSlicer.exe", "exe")

    freecad_dump = local / "CrashDumps" / "FreeCAD.exe.1234.dmp"
    write_text_file(freecad_dump, "freecad")
    write_text_file(program_files / "FreeCAD 0.21" / "bin" / "FreeCAD.exe", "exe")

    openscad_logs = local / "OpenSCAD" / "logs"
    write_text_file(openscad_logs / "openscad.log", "openscad")
    write_text_file(program_files / "OpenSCAD" / "openscad.exe", "exe")

    fusion_logs = local / "Autodesk" / "Autodesk Fusion 360" / "logs"
    write_text_file(fusion_logs / "fusion.log", "fusion")
    write_text_file(local / "Autodesk" / "webdeploy" / "production" / "abc123" / "Fusion360.exe", "exe")

    solidworks_dump = local / "CrashDumps" / "SLDWORKS.exe.1234.dmp"
    write_text_file(solidworks_dump, "solidworks")
    write_text_file(program_files / "SOLIDWORKS Corp" / "SOLIDWORKS" / "SLDWORKS.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(cura_log), str(prusaslicer_logs), str(bambu_logs), str(orca_logs)])
    assert_contains_none(paths, [str(chitubox_logs), str(lychee_logs), str(freecad_dump), str(openscad_logs)])
    assert_contains_none(paths, [str(fusion_logs), str(solidworks_dump)])

def test_app_leftovers_scans_virtualization_emulator_and_local_ai_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    user = root / "User"
    cache_files = [
        (local / "VMware" / "vmware-ui-123.log", "vmware-workstation"),
        (local / "VMware" / "vmplayer-123.log", "vmware-player"),
        (local / "Genymobile" / "Genymotion" / "logs" / "genymotion.log", "genymotion"),
        (program_data / "BlueStacks_nxt" / "Logs" / "bluestacks.log", "bluestacks"),
        (local / "Nox" / "Logs" / "nox.log", "nox"),
        (local / "leidian" / "Log" / "ldplayer.log", "ldplayer"),
        (local / "Ollama" / "logs" / "ollama.log", "ollama"),
        (roaming / "LM Studio" / "logs" / "lmstudio.log", "lmstudio"),
        (roaming / "Jan" / "logs" / "jan.log", "jan"),
        (local / "nomic.ai" / "GPT4All" / "logs" / "gpt4all.log", "gpt4all"),
        (local / "Pinokio" / "cache" / "entry", "pinokio"),
        (user / "Virtual Machines" / "DevVM" / "disk.vmdk", "vmdk"),
        (user / "Virtual Machines" / "DevVM" / "config.vmx", "vmx"),
        (user / "Downloads" / "isos" / "installer.iso", "iso"),
        (program_data / "BlueStacks_nxt" / "Engine" / "Android" / "Data.vhdx", "android-disk"),
        (local / "Nox" / "bin" / "BignoxVMS" / "nox.vmdk", "nox-disk"),
        (local / "leidian" / "vms" / "leidian0" / "disk.vmdk", "ld-disk"),
        (user / ".ollama" / "models" / "blobs" / "sha256-model", "ollama-model"),
        (roaming / "LM Studio" / "models" / "model.gguf", "lm-model"),
        (roaming / "Jan" / "threads" / "chat.json", "jan-chat"),
        (local / "nomic.ai" / "GPT4All" / "LocalDocs" / "index.db", "localdocs"),
        (local / "Pinokio" / "api-keys.json", "api-keys"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    vmware_workstation_log = cache_files[0][0]
    vmware_player_log = cache_files[1][0]
    genymotion_logs = cache_files[2][0].parent
    bluestacks_logs = cache_files[3][0].parent
    nox_logs = cache_files[4][0].parent
    ldplayer_logs = cache_files[5][0].parent
    ollama_logs = cache_files[6][0].parent
    lm_studio_logs = cache_files[7][0].parent
    jan_logs = cache_files[8][0].parent
    gpt4all_logs = cache_files[9][0].parent
    pinokio_cache = cache_files[10][0].parent
    protected_files = [path for path, _ in cache_files[11:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.vmware-workstation.logs"], {"path": str(vmware_workstation_log)})
    assert_field_values(by_rule["app-leftovers.vmware-player.logs"], {"path": str(vmware_player_log)})
    assert_field_values(by_rule["app-leftovers.genymotion.logs"], {"path": str(genymotion_logs)})
    assert_field_values(by_rule["app-leftovers.bluestacks.logs"], {"path": str(bluestacks_logs)})
    assert_field_values(by_rule["app-leftovers.noxplayer.logs"], {"path": str(nox_logs)})
    assert_field_values(by_rule["app-leftovers.ldplayer.logs"], {"path": str(ldplayer_logs)})
    assert_field_values(by_rule["app-leftovers.ollama.logs"], {"path": str(ollama_logs)})
    assert_field_values(by_rule["app-leftovers.lm-studio.logs"], {"path": str(lm_studio_logs)})
    assert_field_values(by_rule["app-leftovers.jan.logs"], {"path": str(jan_logs)})
    assert_field_values(by_rule["app-leftovers.gpt4all.logs"], {"path": str(gpt4all_logs)})
    assert_field_values(by_rule["app-leftovers.pinokio.cache"], {"path": str(pinokio_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_virtualization_emulator_and_local_ai_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    program_files = root / "ProgramFiles"

    vmware_workstation_log = local / "VMware" / "vmware-ui-123.log"
    write_text_file(vmware_workstation_log, "vmware-workstation")
    write_text_file(program_files / "VMware" / "VMware Workstation" / "vmware.exe", "exe")

    vmware_player_log = local / "VMware" / "vmplayer-123.log"
    write_text_file(vmware_player_log, "vmware-player")
    write_text_file(program_files / "VMware" / "VMware Player" / "vmplayer.exe", "exe")

    genymotion_logs = local / "Genymobile" / "Genymotion" / "logs"
    write_text_file(genymotion_logs / "genymotion.log", "genymotion")
    write_text_file(program_files / "Genymobile" / "Genymotion" / "genymotion.exe", "exe")

    bluestacks_logs = program_data / "BlueStacks_nxt" / "Logs"
    write_text_file(bluestacks_logs / "bluestacks.log", "bluestacks")
    write_text_file(program_files / "BlueStacks_nxt" / "HD-Player.exe", "exe")

    nox_logs = local / "Nox" / "Logs"
    write_text_file(nox_logs / "nox.log", "nox")
    write_text_file(program_files / "Nox" / "bin" / "Nox.exe", "exe")

    ldplayer_logs = local / "leidian" / "Log"
    write_text_file(ldplayer_logs / "ldplayer.log", "ldplayer")
    write_text_file(program_files / "LDPlayer" / "LDPlayer9" / "dnplayer.exe", "exe")

    ollama_logs = local / "Ollama" / "logs"
    write_text_file(ollama_logs / "ollama.log", "ollama")
    write_text_file(local / "Programs" / "Ollama" / "ollama.exe", "exe")

    lm_studio_logs = roaming / "LM Studio" / "logs"
    write_text_file(lm_studio_logs / "lmstudio.log", "lmstudio")
    write_text_file(local / "Programs" / "LM Studio" / "LM Studio.exe", "exe")

    jan_logs = roaming / "Jan" / "logs"
    write_text_file(jan_logs / "jan.log", "jan")
    write_text_file(local / "Programs" / "Jan" / "Jan.exe", "exe")

    gpt4all_logs = local / "nomic.ai" / "GPT4All" / "logs"
    write_text_file(gpt4all_logs / "gpt4all.log", "gpt4all")
    write_text_file(local / "Programs" / "GPT4All" / "bin" / "chat.exe", "exe")

    pinokio_cache = local / "Pinokio" / "cache"
    write_text_file(pinokio_cache / "entry", "pinokio")
    write_text_file(local / "Programs" / "Pinokio" / "Pinokio.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(vmware_workstation_log), str(vmware_player_log), str(genymotion_logs)])
    assert_contains_none(paths, [str(bluestacks_logs), str(nox_logs), str(ldplayer_logs), str(ollama_logs)])
    assert_contains_none(paths, [str(lm_studio_logs), str(jan_logs), str(gpt4all_logs), str(pinokio_cache)])

def test_app_leftovers_scans_network_remote_and_dev_tool_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    user = root / "User"
    cache_files = [
        (roaming / "Fiddler Everywhere" / "logs" / "main.log", "fiddler"),
        (roaming / "Charles" / "logs" / "charles.log", "charles"),
        (roaming / "RustDesk" / "log" / "rustdesk.log", "rustdesk"),
        (local / "Tailscale" / "Logs" / "ipn.log", "tailscale"),
        (program_data / "ZeroTier" / "One" / "zerotier.log", "zerotier"),
        (local / "Moonlight Game Streaming Project" / "Moonlight" / "logs" / "moonlight.log", "moonlight"),
        (local / "Sunshine" / "logs" / "sunshine.log", "sunshine"),
        (local / "Microsoft" / "VisualStudio" / "17.0_abcd" / "ActivityLog.xml", "visual-studio"),
        (roaming / "GitExtensions" / "GitExtensions.log", "git-extensions"),
        (local / "GitAhead" / "logs" / "gitahead.log", "gitahead"),
        (roaming / "MongoDB Compass" / "GPUCache" / "data_0", "compass"),
        (roaming / "RedisInsight" / "GPUCache" / "data_0", "redisinsight"),
        (roaming / "Fiddler Everywhere" / "Sessions" / "capture.saz", "capture"),
        (roaming / "Charles" / "ca" / "charles-ssl-proxying-certificate.pem", "cert"),
        (roaming / "RustDesk" / "config" / "RustDesk.toml", "rustdesk-config"),
        (program_data / "ZeroTier" / "One" / "identity.secret", "zerotier-secret"),
        (local / "Tailscale" / "state" / "tailscaled.state", "tailscale-state"),
        (user / "source" / "repos" / "app" / "app.sln", "solution"),
        (user / "repos" / "project" / ".git" / "config", "git-config"),
        (roaming / "MongoDB Compass" / "Connections" / "connections.json", "mongo-connections"),
        (roaming / "RedisInsight" / "db" / "redisinsight.db", "redis-db"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    fiddler_logs = cache_files[0][0].parent
    charles_logs = cache_files[1][0].parent
    rustdesk_logs = cache_files[2][0].parent
    tailscale_logs = cache_files[3][0].parent
    zerotier_log = cache_files[4][0]
    moonlight_logs = cache_files[5][0].parent
    sunshine_logs = cache_files[6][0].parent
    visual_studio_log = cache_files[7][0]
    git_extensions_log = cache_files[8][0]
    gitahead_logs = cache_files[9][0].parent
    compass_gpu_cache = cache_files[10][0].parent
    redisinsight_gpu_cache = cache_files[11][0].parent
    protected_files = [path for path, _ in cache_files[12:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.fiddler-everywhere.logs"], {"path": str(fiddler_logs)})
    assert_field_values(by_rule["app-leftovers.charles.logs"], {"path": str(charles_logs)})
    assert_field_values(by_rule["app-leftovers.rustdesk.logs"], {"path": str(rustdesk_logs)})
    assert_field_values(by_rule["app-leftovers.tailscale.logs"], {"path": str(tailscale_logs)})
    assert_field_values(by_rule["app-leftovers.zerotier.logs"], {"path": str(zerotier_log)})
    assert_field_values(by_rule["app-leftovers.moonlight.logs"], {"path": str(moonlight_logs)})
    assert_field_values(by_rule["app-leftovers.sunshine.logs"], {"path": str(sunshine_logs)})
    assert_field_values(by_rule["app-leftovers.visual-studio.logs"], {"path": str(visual_studio_log)})
    assert_field_values(by_rule["app-leftovers.git-extensions.logs"], {"path": str(git_extensions_log)})
    assert_field_values(by_rule["app-leftovers.gitahead.logs"], {"path": str(gitahead_logs)})
    assert_field_values(by_rule["app-leftovers.mongodb-compass.gpu-cache"], {"path": str(compass_gpu_cache)})
    assert_field_values(by_rule["app-leftovers.redisinsight.gpu-cache"], {"path": str(redisinsight_gpu_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_network_remote_and_dev_tool_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_data = root / "ProgramData"
    program_files = root / "ProgramFiles"

    fiddler_logs = roaming / "Fiddler Everywhere" / "logs"
    write_text_file(fiddler_logs / "main.log", "fiddler")
    write_text_file(local / "Programs" / "Fiddler Everywhere" / "Fiddler Everywhere.exe", "exe")

    charles_logs = roaming / "Charles" / "logs"
    write_text_file(charles_logs / "charles.log", "charles")
    write_text_file(program_files / "Charles" / "Charles.exe", "exe")

    rustdesk_logs = roaming / "RustDesk" / "log"
    write_text_file(rustdesk_logs / "rustdesk.log", "rustdesk")
    write_text_file(program_files / "RustDesk" / "RustDesk.exe", "exe")

    tailscale_logs = local / "Tailscale" / "Logs"
    write_text_file(tailscale_logs / "ipn.log", "tailscale")
    write_text_file(program_files / "Tailscale" / "tailscale-ipn.exe", "exe")

    zerotier_log = program_data / "ZeroTier" / "One" / "zerotier.log"
    write_text_file(zerotier_log, "zerotier")
    write_text_file(program_files / "ZeroTier" / "One" / "zerotier_desktop_ui.exe", "exe")

    moonlight_logs = local / "Moonlight Game Streaming Project" / "Moonlight" / "logs"
    write_text_file(moonlight_logs / "moonlight.log", "moonlight")
    write_text_file(program_files / "Moonlight Game Streaming" / "Moonlight.exe", "exe")

    sunshine_logs = local / "Sunshine" / "logs"
    write_text_file(sunshine_logs / "sunshine.log", "sunshine")
    write_text_file(program_files / "Sunshine" / "sunshine.exe", "exe")

    visual_studio_log = local / "Microsoft" / "VisualStudio" / "17.0_abcd" / "ActivityLog.xml"
    write_text_file(visual_studio_log, "visual-studio")
    write_text_file(program_files / "Microsoft Visual Studio" / "2022" / "Community" / "Common7" / "IDE" / "devenv.exe", "exe")

    git_extensions_log = roaming / "GitExtensions" / "GitExtensions.log"
    write_text_file(git_extensions_log, "git-extensions")
    write_text_file(program_files / "GitExtensions" / "GitExtensions.exe", "exe")

    gitahead_logs = local / "GitAhead" / "logs"
    write_text_file(gitahead_logs / "gitahead.log", "gitahead")
    write_text_file(program_files / "GitAhead" / "GitAhead.exe", "exe")

    compass_gpu_cache = roaming / "MongoDB Compass" / "GPUCache"
    write_text_file(compass_gpu_cache / "data_0", "compass")
    write_text_file(local / "Programs" / "MongoDB Compass" / "MongoDBCompass.exe", "exe")

    redisinsight_gpu_cache = roaming / "RedisInsight" / "GPUCache"
    write_text_file(redisinsight_gpu_cache / "data_0", "redisinsight")
    write_text_file(local / "Programs" / "RedisInsight" / "RedisInsight.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(fiddler_logs), str(charles_logs), str(rustdesk_logs), str(tailscale_logs)])
    assert_contains_none(paths, [str(zerotier_log), str(moonlight_logs), str(sunshine_logs), str(visual_studio_log)])
    assert_contains_none(paths, [str(git_extensions_log), str(gitahead_logs), str(compass_gpu_cache)])
    assert_contains_none(paths, [str(redisinsight_gpu_cache)])

def test_app_leftovers_scans_sync_backup_and_transfer_cache_governance(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    user = root / "User"
    cache_files = [
        (roaming / "Nextcloud" / "logs" / "nextcloud.log", "nextcloud"),
        (roaming / "ownCloud" / "logs" / "owncloud.log", "owncloud"),
        (local / "pCloud" / "logs" / "pcloud.log", "pcloud"),
        (local / "Syncthing" / "syncthing.log", "syncthing"),
        (roaming / "Resilio Sync" / "sync.log", "resilio"),
        (roaming / "GoodSync" / "logs" / "goodsync.log", "goodsync"),
        (local / "Duplicati" / "logs" / "duplicati.log", "duplicati"),
        (roaming / "KopiaUI" / "logs" / "kopia.log", "kopia"),
        (roaming / "Cyberduck" / "Logs" / "cyberduck.log", "cyberduck"),
        (roaming / "Mountain Duck" / "Logs" / "mountain-duck.log", "mountain-duck"),
        (roaming / "TeraCopy" / "Logs" / "copy.log", "teracopy"),
        (local / "RcloneBrowser" / "logs" / "rclone.log", "rclone"),
        (user / "Nextcloud" / "Documents" / "contract.docx", "synced-file"),
        (roaming / "Nextcloud" / "nextcloud.cfg", "nextcloud-config"),
        (roaming / "ownCloud" / "owncloud.cfg", "owncloud-config"),
        (local / "pCloud" / "data.db", "pcloud-db"),
        (local / "Syncthing" / "cert.pem", "syncthing-cert"),
        (local / "Syncthing" / "index-v0.14.0.db", "syncthing-index"),
        (roaming / "Resilio Sync" / "settings.dat", "resilio-settings"),
        (roaming / "GoodSync" / "jobs.tic", "goodsync-jobs"),
        (local / "Duplicati" / "Duplicati-server.sqlite", "duplicati-db"),
        (roaming / "KopiaUI" / "repositories.config", "kopia-repos"),
        (roaming / "Cyberduck" / "Bookmarks" / "server.duck", "cyberduck-bookmark"),
        (roaming / "Mountain Duck" / "Bookmarks" / "drive.duck", "mountain-bookmark"),
        (roaming / "TeraCopy" / "history.db", "teracopy-history"),
        (user / ".config" / "rclone" / "rclone.conf", "rclone-config"),
    ]
    for path, contents in cache_files:
        write_text_file(path, contents)
    nextcloud_logs = cache_files[0][0].parent
    owncloud_logs = cache_files[1][0].parent
    pcloud_logs = cache_files[2][0].parent
    syncthing_log = cache_files[3][0]
    resilio_log = cache_files[4][0]
    goodsync_logs = cache_files[5][0].parent
    duplicati_logs = cache_files[6][0].parent
    kopia_logs = cache_files[7][0].parent
    cyberduck_logs = cache_files[8][0].parent
    mountain_duck_logs = cache_files[9][0].parent
    teracopy_logs = cache_files[10][0].parent
    rclone_logs = cache_files[11][0].parent
    protected_files = [path for path, _ in cache_files[12:]]

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["app-leftovers.nextcloud.logs"], {"path": str(nextcloud_logs)})
    assert_field_values(by_rule["app-leftovers.owncloud.logs"], {"path": str(owncloud_logs)})
    assert_field_values(by_rule["app-leftovers.pcloud.logs"], {"path": str(pcloud_logs)})
    assert_field_values(by_rule["app-leftovers.syncthing.logs"], {"path": str(syncthing_log)})
    assert_field_values(by_rule["app-leftovers.resilio-sync.logs"], {"path": str(resilio_log)})
    assert_field_values(by_rule["app-leftovers.goodsync.logs"], {"path": str(goodsync_logs)})
    assert_field_values(by_rule["app-leftovers.duplicati.logs"], {"path": str(duplicati_logs)})
    assert_field_values(by_rule["app-leftovers.kopiaui.logs"], {"path": str(kopia_logs)})
    assert_field_values(by_rule["app-leftovers.cyberduck.logs"], {"path": str(cyberduck_logs)})
    assert_field_values(by_rule["app-leftovers.mountain-duck.logs"], {"path": str(mountain_duck_logs)})
    assert_field_values(by_rule["app-leftovers.teracopy.logs"], {"path": str(teracopy_logs)})
    assert_field_values(by_rule["app-leftovers.rclone-browser.logs"], {"path": str(rclone_logs)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(path) for path in protected_files])

def test_app_leftovers_skips_sync_backup_and_transfer_rules_when_active_marker_exists(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    local = root / "LocalAppData"
    program_files = root / "ProgramFiles"

    nextcloud_logs = roaming / "Nextcloud" / "logs"
    write_text_file(nextcloud_logs / "nextcloud.log", "nextcloud")
    write_text_file(program_files / "Nextcloud" / "nextcloud.exe", "exe")

    owncloud_logs = roaming / "ownCloud" / "logs"
    write_text_file(owncloud_logs / "owncloud.log", "owncloud")
    write_text_file(program_files / "ownCloud" / "owncloud.exe", "exe")

    pcloud_logs = local / "pCloud" / "logs"
    write_text_file(pcloud_logs / "pcloud.log", "pcloud")
    write_text_file(local / "pCloud" / "pCloud.exe", "exe")

    syncthing_log = local / "Syncthing" / "syncthing.log"
    write_text_file(syncthing_log, "syncthing")
    write_text_file(program_files / "Syncthing" / "syncthing.exe", "exe")

    resilio_log = roaming / "Resilio Sync" / "sync.log"
    write_text_file(resilio_log, "resilio")
    write_text_file(program_files / "Resilio Sync" / "Resilio Sync.exe", "exe")

    goodsync_logs = roaming / "GoodSync" / "logs"
    write_text_file(goodsync_logs / "goodsync.log", "goodsync")
    write_text_file(program_files / "Siber Systems" / "GoodSync" / "GoodSync.exe", "exe")

    duplicati_logs = local / "Duplicati" / "logs"
    write_text_file(duplicati_logs / "duplicati.log", "duplicati")
    write_text_file(program_files / "Duplicati 2" / "Duplicati.GUI.TrayIcon.exe", "exe")

    kopia_logs = roaming / "KopiaUI" / "logs"
    write_text_file(kopia_logs / "kopia.log", "kopia")
    write_text_file(local / "Programs" / "KopiaUI" / "KopiaUI.exe", "exe")

    cyberduck_logs = roaming / "Cyberduck" / "Logs"
    write_text_file(cyberduck_logs / "cyberduck.log", "cyberduck")
    write_text_file(program_files / "Cyberduck" / "Cyberduck.exe", "exe")

    mountain_duck_logs = roaming / "Mountain Duck" / "Logs"
    write_text_file(mountain_duck_logs / "mountain-duck.log", "mountain-duck")
    write_text_file(program_files / "Mountain Duck" / "Mountain Duck.exe", "exe")

    teracopy_logs = roaming / "TeraCopy" / "Logs"
    write_text_file(teracopy_logs / "copy.log", "teracopy")
    write_text_file(program_files / "TeraCopy" / "TeraCopy.exe", "exe")

    rclone_logs = local / "RcloneBrowser" / "logs"
    write_text_file(rclone_logs / "rclone.log", "rclone")
    write_text_file(program_files / "Rclone Browser" / "RcloneBrowser.exe", "exe")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_contains_none(paths, [str(nextcloud_logs), str(owncloud_logs), str(pcloud_logs), str(syncthing_log)])
    assert_contains_none(paths, [str(resilio_log), str(goodsync_logs), str(duplicati_logs), str(kopia_logs)])
    assert_contains_none(paths, [str(cyberduck_logs), str(mountain_duck_logs), str(teracopy_logs), str(rclone_logs)])

def test_app_leftovers_rule_filter_review_and_dry_run(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    run_cleanwin: RunCleanWin,
    cleanwin_result_json: CleanWinResultJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
    assert_payload_status_false: AssertPayloadStatus,
    assert_returncode: AssertReturnCode,
    assert_path_exists: AssertPathExists,
) -> None:
    root = tmp_path
    roaming = root / "Roaming"
    slack_cache = write_text_file(roaming / "Slack" / "Cache" / "entry", "slack").parent
    vscode_cache = write_text_file(roaming / "Code" / "CachedData" / "cache.bin", "code").parent
    plan_file = root / "vscode-leftovers-plan.json"
    env = make_windows_cache_env(root) | {"CLEANWIN_TEST_MODE": "1"}

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
    assert_summary_counts(plan_payload, {"candidate_count": 1})
    assert_field_values(
        plan_payload["candidates"][0],
        {"path": str(vscode_cache), "rule_id": "app-leftovers.vscode.cached-data"},
    )

    review_result = run_cleanwin("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert_returncode(review_result, 2)
    review = cleanwin_result_json(review_result)
    assert_payload_status_false(review, "validation", "valid")
    assert_field_values(review, {"rule_ids": ["app-leftovers.vscode.cached-data"]})
    assert_any_text_contains(review["cleanup_strategy"]["official_cleanup_commands"], "Uninstall Visual Studio Code")
    assert_any_text_contains(review["execution_handoff"]["blocked_reasons"], "controlled low-risk cache execution")
    assert_path_exists(slack_cache)

def test_browser_cache_scans_cache_only_directories_without_profile_data(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_contains_none: AssertContainsNone,
    assert_all_match: AssertAllMatch,
    assert_none_match: AssertNoneMatch,
    assert_field_values: AssertFieldValues,
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
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_summary_counts(payload, {"candidate_count": 2})
    assert_contains_all(paths, [str(chrome_cache), str(edge_code_cache)])
    assert_contains_none(paths, [str(cookies)])
    assert_all_match(payload["candidates"], lambda candidate: candidate["category"] == "browser-cache")
    assert_none_match(payload["candidates"], lambda candidate: "cookies" in candidate["path"].lower())
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(
        by_rule["browser-cache.chrome.default.cache"],
        {"cache_layer": "http-cache", "cache_layer_family": "browser-cache"},
    )
    assert_field_values(
        by_rule["browser-cache.edge.profile1.code-cache"],
        {"cache_layer": "code-cache", "cache_layer_family": "browser-cache"},
    )

def test_browser_cache_discovers_additional_browser_profiles(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_exact_set: AssertExactSet,
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
        env=make_windows_cache_env(root),
    )
    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert_summary_counts(payload, {"candidate_count": 3})
    assert_exact_set(paths, {str(path) for path in cache_paths})

def test_browser_cache_discovers_brave_profile_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
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
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["browser-cache.brave.cache"], {"path": str(brave_cache)})
    assert_field_values(by_rule["browser-cache.brave.code-cache"], {"path": str(brave_code_cache)})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(cookies)])

def test_browser_cache_discovers_extended_cache_layers_without_profile_databases(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_none: AssertContainsNone,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    chrome_default = local / "Google" / "Chrome" / "User Data" / "Default"
    gpu_cache = write_text_file(chrome_default / "GPUCache" / "gpu.bin", "gpu").parent
    shader_cache = write_text_file(chrome_default / "ShaderCache" / "shader.bin", "shader").parent
    service_worker_cache = write_text_file(chrome_default / "Service Worker" / "CacheStorage" / "entry", "sw").parent
    crashpad_reports = write_text_file(chrome_default / "Crashpad" / "reports" / "crash.dmp", "crash").parent
    firefox_profile = local / "Mozilla" / "Firefox" / "Profiles" / "abcd1234.default-release"
    firefox_startup = write_text_file(firefox_profile / "startupCache" / "startup.bin", "startup").parent
    firefox_shader = write_text_file(firefox_profile / "shader-cache" / "shader.bin", "shader").parent
    login_data = chrome_default / "Login Data"
    places = firefox_profile / "places.sqlite"
    write_text_file(login_data, "do-not-touch")
    write_text_file(places, "do-not-touch")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "browser-cache",
        "--older-than-days",
        "0",
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}

    assert_summary_counts(payload, {"candidate_count": 6})
    assert_field_values(by_rule["browser-cache.chrome.gpu-cache"], {"path": str(gpu_cache), "cache_layer": "gpu-cache"})
    assert_field_values(by_rule["browser-cache.chrome.shader-cache"], {"path": str(shader_cache), "cache_layer": "shader-cache"})
    assert_field_values(
        by_rule["browser-cache.chrome.service-worker-cache"],
        {"path": str(service_worker_cache), "cache_layer": "service-worker-cache"},
    )
    assert_field_values(by_rule["browser-cache.chrome.crashpad-reports"], {"path": str(crashpad_reports), "cache_layer": "crash-reports"})
    assert_field_values(by_rule["browser-cache.firefox.startup-cache"], {"path": str(firefox_startup), "cache_layer": "startup-cache"})
    assert_field_values(by_rule["browser-cache.firefox.shader-cache"], {"path": str(firefox_shader), "cache_layer": "shader-cache"})
    assert_contains_none({candidate["path"] for candidate in payload["candidates"]}, [str(login_data), str(places)])

def test_review_plan_for_browser_cache_reports_sensitive_exclusions(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_text_contains_all: AssertTextContainsAll,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_non_empty: AssertNonEmpty,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    chrome_cache = write_text_file(
        local / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "entry", "chrome"
    ).parent
    write_text_file(chrome_cache.parent / "Cookies", "secret")
    plan_file = root / "browser-plan.json"
    env = make_windows_cache_env(root)
    cleanwin_plan_file(plan_file, "--categories", "browser-cache", "--older-than-days", "0", env=env)

    review = cleanwin_json("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    exclusions = review["sensitive_exclusions"]
    assert_non_empty(exclusions)
    assert_field_values(exclusions[0], {"category": "browser-cache"})
    excluded_patterns = "\n".join(item["pattern"] for item in exclusions[0]["excluded_patterns"])
    assert_text_contains_all(excluded_patterns, ["Cookies", "Login Data", "Extensions"])
    strategy = review["cleanup_strategy"]
    assert_field_values(
        strategy,
        {"preferred": "official-tool-or-app-ui", "fallback": "cleanwin-recycle-execution", "requires_review": True},
    )
    assert_contains_all(strategy["official_cleanup_commands"], ["Use Chrome > Clear browsing data"])

def test_rule_id_precise_plan_review_and_dry_run_for_package_cache(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    assert_dry_run_summary: AssertDryRunSummary,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_path_exists: AssertPathExists,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    uv_cache = write_text_file(local / "uv" / "cache" / "wheel.whl", "uv").parent
    winget_cache = write_text_file(local / "Microsoft" / "WinGet" / "Packages" / "installer.msix", "winget").parent
    plan_file = root / "uv-plan.json"
    env = make_windows_cache_env(root) | {"CLEANWIN_TEST_MODE": "1"}

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
    assert_summary_counts(plan_payload, {"candidate_count": 1})
    assert_field_values(plan_payload["candidates"][0], {"rule_id": "package-cache.uv.cache"})

    review = cleanwin_json("review-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert_field_values(review, {"rule_ids": ["package-cache.uv.cache"]})
    assert_contains_all(review["cleanup_strategy"]["official_cleanup_commands"], ["uv cache clean"])

    dry_run_payload = cleanwin_json("execute-plan", "--plan-file", str(plan_file), "--no-require-plan-context", env=env)
    assert_dry_run_summary(dry_run_payload, uv_cache)
    assert_path_exists(winget_cache)

def test_package_cache_scans_additional_developer_package_caches(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_field_values: AssertFieldValues,
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
        env=make_windows_cache_env(root),
    )
    by_rule = {candidate["rule_id"]: candidate for candidate in payload["candidates"]}
    assert_field_values(by_rule["package-cache.vcpkg.downloads"], {"path": str(vcpkg_downloads)})
    assert_field_values(
        by_rule["package-cache.vcpkg.downloads"],
        {"cache_layer": "package-download-cache", "cache_layer_family": "package-cache"},
    )
    assert_field_values(
        by_rule["package-cache.pipx.cache"],
        {"path": str(pipx_cache), "cache_layer": "package-install-cache", "cache_layer_family": "package-cache"},
    )

def test_inspect_rule_id_filters_dev_cache_candidates(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    pip_cache = root / "LocalAppData" / "pip" / "Cache"
    write_text_file(pip_cache / "http-v2" / "entry", "pip")

    npm_cache = root / "npm-cache"
    write_text_file(npm_cache / "_cacache" / "entry", "npm")
    env = make_windows_cache_env(root) | {"NPM_CONFIG_CACHE": str(npm_cache)}

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        "--rule-id",
        "dev-cache.npm.cache",
        env=env,
    )
    assert_summary_counts(payload, {"candidate_count": 1})
    assert_field_values(payload["candidates"][0], {"rule_id": "dev-cache.npm.cache"})

def test_plan_rule_id_filters_candidates_before_write(
    tmp_path: Path,
    cleanwin_plan_file: CleanWinPlanFile,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    npm_cache = root / "npm-cache"
    write_text_file(npm_cache / "_cacache" / "entry", "npm")
    pip_cache = local / "pip" / "Cache"
    write_text_file(pip_cache / "wheels" / "entry", "pip")
    plan_file = root / "plan.json"
    env = make_windows_cache_env(root) | {"NPM_CONFIG_CACHE": str(npm_cache)}

    payload = cleanwin_plan_file(
        plan_file,
        "--categories",
        "dev-cache",
        "--older-than-days",
        "0",
        "--rule-id",
        "dev-cache.pip.cache",
        env=env,
    )
    assert_summary_counts(payload, {"candidate_count": 1})
    assert_field_values(payload["candidates"][0], {"rule_id": "dev-cache.pip.cache"})

def test_read_only_findings_include_structured_review_details(
    cleanwin_json: CleanWinJSON,
    assert_contains_all: AssertContainsAll,
) -> None:
    payload = cleanwin_json("inspect", "--categories", "docker-report")
    finding = payload["findings"][0]
    assert_contains_all(finding, ["review_details"])
    assert_contains_all(
        finding["review_details"],
        ["suggested_paths", "risk_notes", "manual_review_steps", "path_evidence", "evidence_summary"],
    )

def test_read_only_findings_report_existing_path_evidence_without_candidates(
    tmp_path: Path,
    cleanwin_json: CleanWinJSON,
    write_text_file: WriteTextFile,
    make_windows_cache_env: MakeWindowsCacheEnv,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
    assert_at_least: AssertAtLeast,
) -> None:
    root = tmp_path
    local = root / "LocalAppData"
    docker_log = write_text_file(local / "Docker" / "log" / "service.log", "docker").parent

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "docker-report",
        env=make_windows_cache_env(root),
    )
    assert_summary_counts(payload, {"candidate_count": 0})

    details = payload["findings"][0]["review_details"]
    evidence = {item["path"]: item for item in details["path_evidence"]}
    assert_field_values(evidence[str(docker_log)], {"kind": "directory", "exists": True, "child_count": 1})
    assert_at_least(details["evidence_summary"]["existing_path_count"], 1)

def test_validate_plan_rejects_permanent_and_admin_candidates(
    tmp_path: Path,
    run_cleanwin: RunCleanWin,
    write_text_file: WriteTextFile,
    assert_payload_status_false: AssertPayloadStatus,
    assert_text_contains_all: AssertTextContainsAll,
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
    assert_payload_status_false(permanent_validation, "valid")
    assert_text_contains_all("\n".join(permanent_validation["errors"]), ["Unsupported plan delete_mode"])

    admin_plan = Plan(
        candidates=[replace(permanent_plan.candidates[0], delete_mode="recycle", requires_admin=True)],
        categories=["temp"],
    )
    admin_raw = admin_plan.to_dict()
    admin_validation = validate_plan_payload(admin_plan, admin_raw, require_context=False)
    assert_payload_status_false(admin_validation, "valid")
    assert_text_contains_all("\n".join(admin_validation["errors"]), ["Admin-scoped candidate"])


def test_validate_plan_allows_only_low_risk_regenerable_cache_candidates(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_payload_status_false: AssertPayloadStatus,
    assert_payload_status_true: AssertPayloadStatus,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    target = write_text_file(tmp_path / "npm-cache" / "_cacache" / "index", "x")
    base_candidate = Candidate(
        path=str(target),
        category="dev-cache",
        size_bytes=1,
        reason="test",
        safe_to_delete=True,
        delete_mode="recycle",
        risk="low",
        identity=capture_filesystem_identity(target),
        safe_to_delete_rationale="Regenerated by npm.",
    )

    valid_plan = Plan(candidates=[base_candidate], categories=["dev-cache"])
    assert_payload_status_true(validate_plan_payload(valid_plan, valid_plan.to_dict(), require_context=False), "valid")

    app_leftover_plan = Plan(candidates=[replace(base_candidate, category="app-leftovers")], categories=["app-leftovers"])
    app_leftover_validation = validate_plan_payload(app_leftover_plan, app_leftover_plan.to_dict(), require_context=False)
    assert_payload_status_false(app_leftover_validation, "valid")
    assert_text_contains_all("\n".join(app_leftover_validation["errors"]), ["not enabled for controlled low-risk cache execution"])

    medium_risk_plan = Plan(candidates=[replace(base_candidate, risk="medium")], categories=["dev-cache"])
    medium_risk_validation = validate_plan_payload(medium_risk_plan, medium_risk_plan.to_dict(), require_context=False)
    assert_payload_status_false(medium_risk_validation, "valid")
    assert_text_contains_all("\n".join(medium_risk_validation["errors"]), ["Only low-risk cache candidates"])

    missing_rationale_plan = Plan(
        candidates=[replace(base_candidate, safe_to_delete_rationale=None)],
        categories=["dev-cache"],
    )
    missing_rationale_validation = validate_plan_payload(
        missing_rationale_plan,
        missing_rationale_plan.to_dict(),
        require_context=False,
    )
    assert_payload_status_false(missing_rationale_validation, "valid")
    assert_text_contains_all("\n".join(missing_rationale_validation["errors"]), ["requires a regeneration rationale"])
