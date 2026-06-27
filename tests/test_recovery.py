from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.recovery import RECOVERY_READINESS_SCHEMA, recovery_readiness_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyPayload = Callable[[JSONPayload], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertNoneMatch = Callable[[Sequence[JSONPayload], Callable[[JSONPayload], bool]], Sequence[JSONPayload]]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_recovery_readiness_is_non_destructive_and_declares_gates(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_field_values: AssertFieldValues,
) -> None:
    report = recovery_readiness_report()

    assert_readonly_report(report, RECOVERY_READINESS_SCHEMA)
    assert_field_values(
        report,
        {
            "ready_for_recovery_planning": True,
            "ready_for_system_execution": False,
            "execution_gate.requires_recovery_snapshot": True,
        },
    )
    assert_execution_disabled(report["execution_gate"], "system_execution_enabled")


def test_recovery_readiness_declares_snapshot_specs(
    assert_contains_all: AssertContainsAll,
    assert_none_match: AssertNoneMatch,
) -> None:
    report = recovery_readiness_report()
    specs = {item["id"]: item for item in report["snapshot_specs"]}

    assert_contains_all(
        specs,
        [
            "system-restore-point",
            "registry-export",
            "service-state",
            "service-registry-export",
            "scheduled-task-state",
            "scheduled-task-xml-export",
            "appx-inventory",
            "installed-app-inventory",
        ],
    )
    assert_none_match(list(specs.values()), lambda spec: spec["executed_by_report"])
    assert_contains_all(specs["registry-export"]["required_before"], ["registry-change"])
    assert_contains_all(specs["service-registry-export"]["required_before"], ["service-change"])
    assert_contains_all(specs["scheduled-task-xml-export"]["required_before"], ["scheduled-task-change"])


def test_recovery_readiness_declares_service_and_task_export_capabilities(
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = recovery_readiness_report()
    capabilities = {item["id"]: item for item in report["capabilities"]}

    assert_contains_all(
        capabilities,
        [
            "service_registry_export_supported",
            "scheduled_task_xml_export_supported",
        ],
    )
    assert_field_values(
        capabilities["service_registry_export_supported"],
        {"evidence.command": r"reg export HKLM\SYSTEM\CurrentControlSet\Services\<service-name>"},
    )
    assert_field_values(
        capabilities["scheduled_task_xml_export_supported"],
        {"evidence.command": "schtasks /Query /TN <task-name> /XML"},
    )


def test_cli_and_ai_provider_expose_recovery_readiness(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_readonly_payload: AssertReadonlyPayload,
) -> None:
    sample = assert_cli_provider_schema_sample("recovery-readiness", RECOVERY_READINESS_SCHEMA)
    assert_readonly_payload(sample)
