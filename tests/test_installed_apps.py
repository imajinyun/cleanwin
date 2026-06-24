from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cleanwincli.installed_apps import INSTALLED_APP_INVENTORY_SCHEMA, installed_app_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def test_report_is_non_destructive_and_supports_non_windows() -> None:
    report = installed_app_inventory_report(raw_registry_entries=[], env={})

    assert report["schema"] == INSTALLED_APP_INVENTORY_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["summary"]["application_count"] == 0
    assert any(source["id"] == "winget" and not source["available"] for source in report["sources"])
    assert any("does not uninstall" in item for item in report["non_goals"])


def test_registry_entries_are_normalized_without_uninstalling() -> None:
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

    assert report["summary"]["registry_application_count"] == 1
    app = report["applications"][0]
    assert app["display_name"] == "Slack"
    assert app["publisher"] == "Slack Technologies LLC"
    assert app["uninstall_string_present"] is True
    assert app["estimated_size_kb"] == 250000
    correlation = next(item for item in report["leftover_correlations"] if item["rule_id"] == "app-leftovers.slack.cache")
    assert correlation["state"] == "installed-application-present"
    assert correlation["recommendation"] == "skip-leftover-cleanup-until-uninstalled"


def test_filesystem_package_sources_and_leftover_correlation(tmp_path: Path) -> None:
    local = tmp_path / "Local"
    profile = tmp_path / "Profile"
    program_data = tmp_path / "ProgramData"
    app_data = tmp_path / "Roaming"
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
    assert ("scoop", "git") in apps
    assert ("chocolatey", "nodejs") in apps
    assert ("portable-location", "PortableTool") in apps
    slack_correlation = next(item for item in report["leftover_correlations"] if item["rule_id"] == "app-leftovers.slack.cache")
    assert slack_correlation["state"] == "potential-uninstall-leftover"
    assert slack_correlation["leftover_path"] == str(slack_cache)


def test_cli_and_ai_provider_expose_inventory(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("installed-app-inventory")
    assert cli["schema"] == INSTALLED_APP_INVENTORY_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "installed-app-inventory")
    assert provider["schema"] == INSTALLED_APP_INVENTORY_SCHEMA
