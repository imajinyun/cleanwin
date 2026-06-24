from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cleanwincli.startup_inventory import STARTUP_SERVICE_INVENTORY_SCHEMA, startup_service_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]


def test_report_is_non_destructive_and_gated() -> None:
    report = startup_service_inventory_report(raw_registry_values={}, raw_services=[], raw_tasks=[], env={})

    assert report["schema"] == STARTUP_SERVICE_INVENTORY_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["execution_gate"]["system_execution_enabled"] is False
    assert report["execution_gate"]["requires_service_snapshot"] is True
    assert any("does not disable startup" in item for item in report["non_goals"])


def test_registry_and_startup_folder_entries_are_inventory_only(
    tmp_path: Path, write_text_file: WriteTextFile
) -> None:
    appdata = tmp_path / "Roaming"
    startup = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    write_text_file(startup / "Example.lnk", "shortcut")
    target = write_text_file(tmp_path / "Example.exe", "exe")

    report = startup_service_inventory_report(
        raw_registry_values={
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run": {
                "Example": f'"{target}" --background',
                "MissingTarget": r"C:\Missing\missing.exe",
            }
        },
        raw_services=[],
        raw_tasks=[],
        env={"APPDATA": str(appdata)},
    )

    entries = {entry["name"]: entry for entry in report["startup_entries"]}
    assert entries["Example"]["target_exists"] is True
    assert entries["MissingTarget"]["target_exists"] is False
    assert entries["Example"]["safe_to_execute"] is False
    assert "Example.lnk" in entries
    assert report["summary"]["startup_entry_count"] == 3
    assert report["summary"]["missing_target_count"] == 1


def test_service_and_scheduled_task_fixtures_are_report_only() -> None:
    report = startup_service_inventory_report(
        raw_registry_values={},
        raw_services=[{"Name": "ExampleService", "DisplayName": "Example Service", "Status": "Running", "StartType": "Automatic"}],
        raw_tasks=[{"TaskName": r"\Example\Task", "Status": "Ready", "Task To Run": r"C:\Missing\task.exe", "Author": "Example"}],
        env={},
    )

    assert report["summary"]["service_count"] == 1
    assert report["summary"]["scheduled_task_count"] == 1
    assert report["services"][0]["risk"] == "high"
    assert report["services"][0]["safe_to_execute"] is False
    assert report["scheduled_tasks"][0]["safe_to_execute"] is False
    assert report["scheduled_tasks"][0]["target_exists"] is False


@pytest.mark.parametrize(
    "args",
    [
        ("startup-service-inventory",),
        ("ai-tools", "--provider", "startup-service-inventory"),
    ],
)
def test_cli_and_ai_provider_expose_inventory(args: tuple[str, ...], cleanwin_json: CleanWinJSON) -> None:
    assert cleanwin_json(*args)["schema"] == STARTUP_SERVICE_INVENTORY_SCHEMA
