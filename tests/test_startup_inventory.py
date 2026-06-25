from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from pathlib import Path
from typing import Any

from cleanwincli.startup_inventory import STARTUP_SERVICE_INVENTORY_SCHEMA, startup_service_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteTextFile = Callable[[Path, str], Path]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertSafeToExecuteDisabled = Callable[[JSONPayload], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_report_is_non_destructive_and_gated(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = startup_service_inventory_report(raw_registry_values={}, raw_services=[], raw_tasks=[], env={})

    assert_readonly_report(report, STARTUP_SERVICE_INVENTORY_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "system_execution_enabled")
    assert_field_values(report["execution_gate"], {"requires_service_snapshot": True})
    assert_any_text_contains(report["non_goals"], "does not disable startup")


def test_registry_and_startup_folder_entries_are_inventory_only(
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
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
    assert_field_values(entries["Example"], {"target_exists": True})
    assert_field_values(entries["MissingTarget"], {"target_exists": False})
    assert_safe_to_execute_disabled(entries["Example"])
    assert_contains_all(entries, ["Example.lnk"])
    assert_summary_counts(report, {"startup_entry_count": 3, "missing_target_count": 1})


def test_service_and_scheduled_task_fixtures_are_report_only(
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    report = startup_service_inventory_report(
        raw_registry_values={},
        raw_services=[{"Name": "ExampleService", "DisplayName": "Example Service", "Status": "Running", "StartType": "Automatic"}],
        raw_tasks=[{"TaskName": r"\Example\Task", "Status": "Ready", "Task To Run": r"C:\Missing\task.exe", "Author": "Example"}],
        env={},
    )

    assert_summary_counts(report, {"service_count": 1, "scheduled_task_count": 1})
    assert_field_values(report["services"][0], {"risk": "high"})
    assert_safe_to_execute_disabled(report["services"][0])
    assert_safe_to_execute_disabled(report["scheduled_tasks"][0])
    assert_field_values(report["scheduled_tasks"][0], {"target_exists": False})


def test_cli_and_ai_provider_expose_inventory(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("startup-service-inventory", STARTUP_SERVICE_INVENTORY_SCHEMA)
