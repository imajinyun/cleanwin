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
    tmp_path: Path,
    write_text_file: WriteTextFile,
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
) -> None:
    service_target = write_text_file(tmp_path / "service.exe", "exe")
    report = startup_service_inventory_report(
        raw_registry_values={},
        raw_services=[
            {
                "Name": "ExampleService",
                "DisplayName": "Example Service",
                "Status": "Running",
                "StartType": "Automatic",
                "PathName": f'"{service_target}" --service',
                "Dependencies": ["RpcSs"],
                "TriggerStart": True,
                "RecoveryActions": ["restart-service"],
            }
        ],
        raw_tasks=[
            {
                "TaskName": r"\Example\Task",
                "Status": "Ready",
                "Task To Run": r"C:\Missing\task.exe",
                "Author": "Example",
                "Run As User": "SYSTEM",
                "RunLevel": "Highest",
                "Schedule Type": "At logon time",
                "Last Result": "0",
            }
        ],
        env={},
    )

    assert_summary_counts(
        report,
        {
            "service_count": 1,
            "auto_start_service_count": 1,
            "scheduled_task_count": 1,
            "elevated_task_count": 1,
        },
    )
    assert_field_values(
        report["services"][0],
        {
            "risk": "high",
            "start_type_classification": "auto-start",
            "target_exists": True,
            "target_status": "exists",
            "dependencies": ["RpcSs"],
            "trigger_start": True,
            "recovery_actions": ["restart-service"],
        },
    )
    assert_contains_all(report["services"][0]["snapshot_requirements"], ["sc.exe qc", "Get-CimInstance Win32_Service"])
    assert_safe_to_execute_disabled(report["services"][0])
    assert_safe_to_execute_disabled(report["scheduled_tasks"][0])
    assert_field_values(
        report["scheduled_tasks"][0],
        {
            "task_path": r"\Example\Task",
            "task_folder": r"\Example",
            "target_exists": False,
            "target_status": "missing",
            "author": "Example",
            "run_as_user": "SYSTEM",
            "run_level": "Highest",
            "xml_snapshot_required": True,
        },
    )
    assert_contains_all(report["scheduled_tasks"][0]["snapshot_requirements"], ["schtasks /Query /XML"])


def test_registry_extension_and_driver_service_inventory_are_report_only(
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = startup_service_inventory_report(
        raw_registry_values={
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run": {
                "Teams": bytes.fromhex("020000000000000000000000"),
            },
            r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon": {
                "Shell": "explorer.exe",
            },
        },
        raw_services=[
            {
                "Name": "ExampleDriver",
                "DisplayName": "Example Driver",
                "Status": "Running",
                "StartType": "Manual",
                "ServiceType": "Kernel Driver",
                "PathName": r"C:\Windows\System32\drivers\example.sys",
            }
        ],
        raw_tasks=[],
        env={},
    )

    extensions = {entry["name"]: entry for entry in report["registry_extension_entries"]}
    assert_contains_all(extensions, ["Teams", "Shell"])
    assert_field_values(extensions["Teams"], {"entry_type": "startup-approved", "risk": "medium"})
    assert_field_values(extensions["Shell"], {"entry_type": "winlogon", "risk": "high"})
    assert_safe_to_execute_disabled(extensions["Shell"])
    assert_field_values(report["services"][0], {"service_type": "Kernel Driver", "risk": "high"})
    assert_safe_to_execute_disabled(report["services"][0])
    assert_summary_counts(report, {"registry_extension_entry_count": 2, "high_risk_extension_count": 1, "driver_service_count": 1})


def test_service_and_task_inventory_marks_unexpanded_targets_for_snapshot_review(
    assert_safe_to_execute_disabled: AssertSafeToExecuteDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_field_values: AssertFieldValues,
) -> None:
    report = startup_service_inventory_report(
        raw_registry_values={},
        raw_services=[
            {
                "Name": "EnvService",
                "DisplayName": "Env Service",
                "Status": "Stopped",
                "StartType": "Demand",
                "PathName": r"%SystemRoot%\System32\env-service.exe",
                "TriggerStart": False,
            }
        ],
        raw_tasks=[
            {
                "TaskName": "RootTask",
                "Status": "Disabled",
                "Task To Run": r"%SystemRoot%\System32\root-task.exe",
            }
        ],
        env={},
    )

    assert_summary_counts(report, {"missing_target_count": 1, "missing_service_target_count": 1})
    assert_field_values(
        report["services"][0],
        {
            "start_type_classification": "manual",
            "target_path": r"%SystemRoot%\System32\env-service.exe",
            "target_status": "environment-expansion-required",
            "trigger_start": False,
        },
    )
    assert_safe_to_execute_disabled(report["services"][0])
    assert_field_values(
        report["scheduled_tasks"][0],
        {
            "task_folder": "\\",
            "target_path": r"%SystemRoot%\System32\root-task.exe",
            "target_status": "environment-expansion-required",
        },
    )
    assert_safe_to_execute_disabled(report["scheduled_tasks"][0])


def test_cli_and_ai_provider_expose_inventory(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("startup-service-inventory", STARTUP_SERVICE_INVENTORY_SCHEMA)
