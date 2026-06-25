from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any

from cleanwincli.browser_inventory import BROWSER_PROFILE_INVENTORY_SCHEMA, browser_profile_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
AssertCliProviderSchemaWithEnv = Callable[[str, str, dict[str, str]], None]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertSchemaSamples = Callable[[list[str]], dict[str, JSONPayload]]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertSafeToExecuteDisabled = Callable[[JSONPayload], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
AssertNoneMatch = Callable[[Sequence[str], Callable[[str], bool]], Sequence[str]]


def test_browser_inventory_reports_profiles_cache_layers_and_locks(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_readonly_report: AssertReadonlyReport,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    local = tmp_path / "LocalAppData"
    chrome_default = local / "Google" / "Chrome" / "User Data" / "Default"
    cache = chrome_default / "Cache"
    code_cache = chrome_default / "Code Cache"
    write_text_file(cache / "entry", "cache")
    write_text_file(code_cache / "bytecode", "code")
    write_text_file(chrome_default / "SingletonLock", "locked")

    report = browser_profile_inventory_report(env={"LOCALAPPDATA": str(local), "APPDATA": str(tmp_path / "Roaming")})

    assert_readonly_report(report, BROWSER_PROFILE_INVENTORY_SCHEMA)
    assert_summary_counts(report, {"profile_count": 1, "locked_profile_count": 1})
    profile = report["profiles"][0]
    assert profile["browser"] == "chrome"
    assert profile["profile_name"] == "Default"
    assert profile["locked_profile"]["state"] == "locked-or-running"
    layers = {layer["name"]: layer for layer in profile["cache_layers"]}
    assert layers["Cache"]["type"] == "http-cache"
    assert layers["Cache"]["exists"] is True
    assert layers["Cache"]["promotable"] is True
    assert layers["Code Cache"]["type"] == "code-cache"
    for layer in profile["cache_layers"]:
        assert_safe_to_execute_disabled(layer)


def test_browser_inventory_excludes_sensitive_profile_data(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_any_text_contains: AssertAnyTextContains,
    assert_none_match: AssertNoneMatch,
) -> None:
    roaming = tmp_path / "Roaming"
    firefox_profile = roaming / "Mozilla" / "Firefox" / "Profiles" / "abc.default-release"
    write_text_file(firefox_profile / "cache2" / "entry", "cache")
    write_text_file(firefox_profile / "cookies.sqlite", "cookie")
    write_text_file(firefox_profile / "logins.json", "login")

    report = browser_profile_inventory_report(env={"APPDATA": str(roaming), "LOCALAPPDATA": str(tmp_path / "Local")})

    profile = next(profile for profile in report["profiles"] if profile["browser"] == "firefox")
    assert_contains_all(profile["sensitive_exclusions"], ["cookies.sqlite", "logins.json"])
    layer_paths = [layer["path"] for layer in profile["cache_layers"]]
    assert_none_match(layer_paths, lambda path: "cookies.sqlite" in path)
    assert_none_match(layer_paths, lambda path: "logins.json" in path)
    assert_execution_disabled(report["execution_gate"], "cache_execution_enabled")
    assert_any_text_contains(report["non_goals"], "never promotes cookies")


def test_cli_ai_provider_exposes_browser_inventory(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_cli_provider_schema_with_env: AssertCliProviderSchemaWithEnv,
) -> None:
    local = tmp_path / "LocalAppData"
    edge_default = local / "Microsoft" / "Edge" / "User Data" / "Default"
    write_text_file(edge_default / "GPUCache" / "entry", "cache")
    env = {"LOCALAPPDATA": str(local), "APPDATA": str(tmp_path / "Roaming")}

    assert_cli_provider_schema_with_env("browser-profile-inventory", BROWSER_PROFILE_INVENTORY_SCHEMA, env)


def test_schema_registry_exposes_browser_inventory(assert_schema_samples: AssertSchemaSamples) -> None:
    assert_schema_samples([BROWSER_PROFILE_INVENTORY_SCHEMA])
