from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from cleanwincli.installed_apps import INSTALLED_APP_INVENTORY_SCHEMA, installed_app_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[[JSONPayload], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]


def test_report_is_non_destructive_and_supports_non_windows(
    assert_readonly_report: AssertReadonlyReport,
) -> None:
    report = installed_app_inventory_report(raw_registry_entries=[], env={})

    assert_readonly_report(report, INSTALLED_APP_INVENTORY_SCHEMA)
    assert report["summary"]["application_count"] == 0
    assert any(source["id"] == "winget" and not source["available"] for source in report["sources"])
    assert any("does not uninstall" in item for item in report["non_goals"])


def test_registry_entries_are_normalized_without_uninstalling(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
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
    assert_payload_schema(app["uninstall_strategy"], "cleanwin.uninstall-strategy.v1")
    assert app["uninstall_strategy"]["strategy_id"] == "registry-uninstall-string"
    assert_execution_disabled(app["uninstall_strategy"])
    correlation = next(item for item in report["leftover_correlations"] if item["rule_id"] == "app-leftovers.slack.cache")
    assert correlation["state"] == "installed-application-present"
    assert correlation["recommendation"] == "skip-leftover-cleanup-until-uninstalled"


def test_filesystem_package_sources_and_leftover_correlation(
    tmp_path: Path, write_text_file: WriteTextFile
) -> None:
    local = tmp_path / "Local"
    profile = tmp_path / "Profile"
    program_data = tmp_path / "ProgramData"
    app_data = tmp_path / "Roaming"
    write_text_file(profile / "scoop" / "apps" / "git" / "manifest.json", "{}")
    choco_dir = program_data / "chocolatey" / "lib" / "nodejs"
    write_text_file(
        choco_dir / "nodejs.nuspec",
        "<package><metadata><id>nodejs</id><version>22.0.0</version></metadata></package>",
    )
    write_text_file(local / "Programs" / "PortableTool" / "PortableTool.exe", "exe")
    slack_cache = app_data / "Slack" / "Cache"
    write_text_file(slack_cache / "entry", "cache")

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
    by_source_name = {(app["source"], app["display_name"]): app for app in report["applications"]}
    assert by_source_name[("scoop", "git")]["uninstall_strategy"]["strategy_id"] == "scoop-uninstall"
    assert by_source_name[("chocolatey", "nodejs")]["uninstall_strategy"]["strategy_id"] == "chocolatey-uninstall"
    assert by_source_name[("portable-location", "PortableTool")]["uninstall_strategy"]["strategy_id"] == "portable-manual-review"
    slack_correlation = next(item for item in report["leftover_correlations"] if item["rule_id"] == "app-leftovers.slack.cache")
    assert slack_correlation["state"] == "potential-uninstall-leftover"
    assert slack_correlation["leftover_path"] == str(slack_cache)
    assert report["summary"]["uninstall_strategy_counts"]["scoop-uninstall"] == 1
    assert report["summary"]["manual_review_strategy_count"] == 1


def test_uninstall_strategy_classifies_msi_store_winget_steam_and_orphans(
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    report = installed_app_inventory_report(
        raw_registry_entries=[
            {
                "DisplayName": "MSI Tool",
                "WindowsInstaller": "1",
                "UninstallString": "MsiExec.exe /X{00000000-0000-0000-0000-000000000000}",
                "key_path": r"HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\MSITool",
            },
            {
                "DisplayName": "Store App",
                "source": "appx",
                "release_type": "appx",
                "key_path": "AppX/StoreApp",
            },
            {
                "DisplayName": "WinGet Tool",
                "source": "winget",
                "key_path": "winget/Example.Tool",
            },
            {
                "DisplayName": "Steam Game",
                "InstallLocation": r"D:\SteamLibrary\steamapps\common\Game",
                "key_path": r"HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 123",
            },
            {
                "DisplayName": "Orphaned Entry",
                "key_path": r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Orphaned",
            },
            {
                "DisplayName": "System Component",
                "SystemComponent": "1",
                "key_path": r"HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\Component",
            },
        ],
        env={},
    )

    by_name = {app["display_name"]: app["uninstall_strategy"] for app in report["applications"]}
    assert by_name["MSI Tool"]["strategy_id"] == "msi-uninstall"
    assert by_name["Store App"]["strategy_id"] == "store-app-review-only"
    assert by_name["WinGet Tool"]["strategy_id"] == "winget-uninstall"
    assert by_name["Steam Game"]["strategy_id"] == "steam-library-review"
    assert by_name["Orphaned Entry"]["strategy_id"] == "orphaned-entry-review"
    assert by_name["System Component"]["strategy_id"] == "system-component-review-only"
    for strategy in by_name.values():
        assert_execution_disabled(strategy)
    assert report["summary"]["uninstall_strategy_counts"]["winget-uninstall"] == 1

def test_cli_and_ai_provider_expose_inventory(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("installed-app-inventory", INSTALLED_APP_INVENTORY_SCHEMA)
