from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.windows_native_artifacts import (
    WINDOWS_NATIVE_ARTIFACT_CONTRACT_SCHEMA,
    WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA,
    WINDOWS_NATIVE_ARTIFACTS_SCHEMA,
    parse_chocolatey_list_output,
    parse_dism_feature_table,
    parse_registry_export_metadata,
    parse_sc_qc_output,
    parse_scheduled_tasks_csv_output,
    parse_scoop_list_output,
    parse_winget_list_output,
    windows_native_artifacts_report,
)

JSONPayload = dict[str, Any]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[Sequence[str]], dict[str, JSONPayload]]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]


def test_windows_native_artifact_contracts_are_report_only(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    report = windows_native_artifacts_report()
    contracts = {contract["id"]: contract for contract in report["contracts"]}

    assert_readonly_report(report, WINDOWS_NATIVE_ARTIFACTS_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "artifact_collection_execution_enabled", "ai_auto_call_allowed")
    assert_summary_counts(report, {"contract_count": 12, "requires_admin_count": 4, "execution_enabled_count": 0})
    assert_contains_all(
        set(contracts),
        [
            "powershell-appx-packages",
            "powershell-provisioned-appx",
            "registry-export",
            "scheduled-task-xml",
            "service-query-config",
            "winget-list",
            "scoop-list",
            "chocolatey-list",
            "dism-features",
            "dism-component-store",
        ],
    )
    for contract in contracts.values():
        assert_payload_schema(contract, WINDOWS_NATIVE_ARTIFACT_CONTRACT_SCHEMA)
        assert_execution_disabled(contract)


def test_windows_native_artifact_contracts_describe_protected_surfaces(
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    contracts = {contract["id"]: contract for contract in windows_native_artifacts_report()["contracts"]}

    assert_field_values(
        contracts["winget-list"],
        {"parser": "winget-list", "output_schema": "cleanwin.winget-list-artifact.v1"},
    )
    assert_contains_all(contracts["registry-export"]["protected_surfaces"], ["registry values", "rollback metadata"])
    assert_contains_all(contracts["service-query-config"]["protected_surfaces"], ["service binary path", "start type"])
    assert_contains_all(contracts["scheduled-task-xml"]["protected_surfaces"], ["task triggers", "task actions"])
    assert_contains_all(contracts["dism-component-store"]["protected_surfaces"], ["WinSxS", "servicing stack"])


def test_winget_scoop_and_chocolatey_parsers_normalize_package_identity(
    assert_field_values: AssertFieldValues,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    winget = parse_winget_list_output(
        """
Name               Id                         Version     Source
---------------------------------------------------------------
PowerToys          Microsoft.PowerToys        0.82.0      winget
Visual Studio Code Microsoft.VisualStudioCode 1.90.0      winget
""".strip()
    )
    scoop = parse_scoop_list_output(
        """
Name    Version Source
git     2.45.1  main
nodejs  22.1.0  main
""".strip()
    )
    chocolatey = parse_chocolatey_list_output("git 2.45.1\nvscode 1.90.0\n2 packages installed.")

    assert_payload_schema(winget, WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA)
    assert_field_values(winget["packages"][0], {"name": "PowerToys", "package_id": "Microsoft.PowerToys", "source": "winget"})
    assert_field_values(scoop["summary"], {"package_count": 2})
    assert_field_values(chocolatey["packages"][1], {"name": "vscode", "version": "1.90.0", "source": "chocolatey"})


def test_service_task_registry_and_dism_parsers_extract_fixture_metadata(
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
) -> None:
    service = parse_sc_qc_output(
        """
[SC] QueryServiceConfig SUCCESS

SERVICE_NAME: ExampleSvc
        START_TYPE         : 2   AUTO_START
        BINARY_PATH_NAME   : C:\\Program Files\\Example\\example.exe
        DEPENDENCIES       : RpcSs
        SERVICE_START_NAME : LocalSystem
""".strip()
    )
    tasks = parse_scheduled_tasks_csv_output(
        '"TaskName","Status","Last Run Time","Task To Run"\n'
        '"\\Example\\Updater","Ready","6/27/2026 10:00:00 AM","C:\\Program Files\\Example\\updater.exe"'
    )
    registry = parse_registry_export_metadata(
        """
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\Software\\Example]
"Enabled"=dword:00000001
""".strip()
    )
    features = parse_dism_feature_table(
        """
Feature Name                          | State
------------------------------------------------
Microsoft-Hyper-V-All                 | Disabled
Printing-Foundation-Features          | Enabled
""".strip()
    )

    assert_field_values(service["service"], {"name": "ExampleSvc", "start_type": "2   AUTO_START"})
    assert_field_values(tasks["tasks"][0], {"task_name": r"\Example\Updater", "status": "Ready"})
    assert_contains_all(registry["registry_keys"], [r"HKEY_LOCAL_MACHINE\Software\Example"])
    assert_field_values(registry["summary"], {"key_count": 1, "value_count": 1})
    assert_field_values(features["features"][0], {"name": "Microsoft-Hyper-V-All", "state": "Disabled"})


def test_cli_provider_and_schema_registry_expose_native_artifacts(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    assert_cli_provider_schema_sample("windows-native-artifacts", WINDOWS_NATIVE_ARTIFACTS_SCHEMA)
    assert_schema_samples([WINDOWS_NATIVE_ARTIFACT_CONTRACT_SCHEMA, WINDOWS_NATIVE_ARTIFACT_PARSE_SCHEMA])
