from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cleanwincli.browser_inventory import BROWSER_PROFILE_INVENTORY_SCHEMA, browser_profile_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def test_browser_inventory_reports_profiles_cache_layers_and_locks(tmp_path: Path) -> None:
    local = tmp_path / "LocalAppData"
    chrome_default = local / "Google" / "Chrome" / "User Data" / "Default"
    cache = chrome_default / "Cache"
    code_cache = chrome_default / "Code Cache"
    cache.mkdir(parents=True)
    code_cache.mkdir()
    (cache / "entry").write_text("cache", encoding="utf-8")
    (code_cache / "bytecode").write_text("code", encoding="utf-8")
    (chrome_default / "SingletonLock").write_text("locked", encoding="utf-8")

    report = browser_profile_inventory_report(env={"LOCALAPPDATA": str(local), "APPDATA": str(tmp_path / "Roaming")})

    assert report["schema"] == BROWSER_PROFILE_INVENTORY_SCHEMA
    assert report["destructive"] is False
    assert report["executes_system_commands"] is False
    assert report["summary"]["profile_count"] == 1
    assert report["summary"]["locked_profile_count"] == 1
    profile = report["profiles"][0]
    assert profile["browser"] == "chrome"
    assert profile["profile_name"] == "Default"
    assert profile["locked_profile"]["state"] == "locked-or-running"
    layers = {layer["name"]: layer for layer in profile["cache_layers"]}
    assert layers["Cache"]["type"] == "http-cache"
    assert layers["Cache"]["exists"] is True
    assert layers["Cache"]["promotable"] is True
    assert layers["Code Cache"]["type"] == "code-cache"
    assert all(layer["safe_to_execute"] is False for layer in profile["cache_layers"])


def test_browser_inventory_excludes_sensitive_profile_data(tmp_path: Path) -> None:
    roaming = tmp_path / "Roaming"
    firefox_profile = roaming / "Mozilla" / "Firefox" / "Profiles" / "abc.default-release"
    cache2 = firefox_profile / "cache2"
    cache2.mkdir(parents=True)
    (firefox_profile / "cookies.sqlite").write_text("cookie", encoding="utf-8")
    (firefox_profile / "logins.json").write_text("login", encoding="utf-8")

    report = browser_profile_inventory_report(env={"APPDATA": str(roaming), "LOCALAPPDATA": str(tmp_path / "Local")})

    profile = next(profile for profile in report["profiles"] if profile["browser"] == "firefox")
    assert "cookies.sqlite" in profile["sensitive_exclusions"]
    assert "logins.json" in profile["sensitive_exclusions"]
    layer_paths = [layer["path"] for layer in profile["cache_layers"]]
    assert all("cookies.sqlite" not in path for path in layer_paths)
    assert all("logins.json" not in path for path in layer_paths)
    assert report["execution_gate"]["cache_execution_enabled"] is False
    assert any("never promotes cookies" in item for item in report["non_goals"])


def test_cli_ai_provider_and_schema_registry_expose_browser_inventory(tmp_path, cleanwin_json: CleanWinJSON) -> None:
    local = tmp_path / "LocalAppData"
    edge_default = local / "Microsoft" / "Edge" / "User Data" / "Default"
    (edge_default / "GPUCache").mkdir(parents=True)
    env = {"LOCALAPPDATA": str(local), "APPDATA": str(tmp_path / "Roaming")}

    cli = cleanwin_json("browser-profile-inventory", env=env)
    assert cli["schema"] == BROWSER_PROFILE_INVENTORY_SCHEMA
    assert cli["summary"]["profile_count"] == 1

    provider = cleanwin_json("ai-tools", "--provider", "browser-profile-inventory", env=env)
    assert provider["schema"] == BROWSER_PROFILE_INVENTORY_SCHEMA

    registry = cleanwin_json("schema-registry")
    names = {entry["name"] for entry in registry["entries"]}
    assert BROWSER_PROFILE_INVENTORY_SCHEMA in names
    assert registry["samples"][BROWSER_PROFILE_INVENTORY_SCHEMA]["schema"] == BROWSER_PROFILE_INVENTORY_SCHEMA
