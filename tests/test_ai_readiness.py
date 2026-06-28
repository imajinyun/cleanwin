from __future__ import annotations

from collections.abc import Callable, Collection

import pytest

from cleanwincli import __version__
from cleanwincli.ai_readiness import ai_readiness_report, validate_ai_readiness
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.core import doctor_report
from cleanwincli.debloat_privacy import DEBLOAT_PRIVACY_REPORT_SCHEMA
from cleanwincli.environment_index import ENVIRONMENT_INDEX_SCHEMA, environment_index_report
from cleanwincli.installed_apps import INSTALLED_APP_INVENTORY_SCHEMA
from cleanwincli.official_commands import OFFICIAL_COMMAND_PLAN_SCHEMA
from cleanwincli.recovery import RECOVERY_READINESS_SCHEMA
from cleanwincli.startup_inventory import STARTUP_SERVICE_INVENTORY_SCHEMA
from cleanwincli.windows_inventory import WINDOWS_INVENTORY_SCHEMA
from cleanwincli.workflow_artifacts import (
    WORKFLOW_DECISION_SCHEMA,
    WORKFLOW_TRACE_SCHEMA,
    workflow_decision_report,
    workflow_trace_report,
)
from cleanwincli.workflow_router import WORKFLOW_ROUTER_SCHEMA, workflow_router_report

JSONPayload = dict[str, object]
CleanWinJSON = Callable[..., JSONPayload]
FieldValues = dict[str, object]
AssertSchemasRegistered = Callable[[list[str]], None]
AssertCliProviderSchema = Callable[[str, str], None]
AssertCliProviderSchemas = Callable[[list[tuple[str, str]]], None]
AssertAIProviderSchemas = Callable[[list[tuple[str, str]]], None]
AssertCommandSequence = Callable[[list[str] | list[list[str]], list[str] | list[list[str]]], None]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyPayload = Callable[[JSONPayload], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
AssertContainsAll = Callable[[set[str] | list[str], list[str]], None]
AssertAnyTextContains = Callable[[list[str], str], None]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]
AssertExactSequence = Callable[[list[str], list[str]], list[str]]
AssertOneOf = Callable[[object, Collection[object]], object]

EXPECTED_DOCTOR_COMMANDS = [
    ["make", "pytest"],
    ["python3", "-m", "pytest", "-q"],
    ["python3", "-m", "ruff", "check", "cleanwin.py", "cleanwincli", "tests"],
    ["python3", "-m", "mypy", "cleanwin.py", "cleanwincli", "tests"],
    ["python3", "-m", "build", "--sdist", "--wheel"],
    ["make", "package-install-smoke"],
    ["make", "sdist-install-smoke"],
    ["make", "mcp-install-smoke"],
    ["make", "docs-smoke"],
    ["make", "ai-smoke"],
    ["make", "mcp-smoke"],
    ["make", "version-smoke"],
    ["make", "clean"],
    ["make", "quality"],
]

EXPECTED_READINESS_PROVIDERS = [
    ("readiness", "cleanwin.ai-readiness.v1"),
    ("self-test", "cleanwin.ai-self-test.v1"),
    ("runbook", "cleanwin.ai-runbook.v1"),
    ("workflow-router", WORKFLOW_ROUTER_SCHEMA),
    ("environment-index", ENVIRONMENT_INDEX_SCHEMA),
    ("workflow-decision", WORKFLOW_DECISION_SCHEMA),
    ("workflow-trace", WORKFLOW_TRACE_SCHEMA),
    ("doctor", "cleanwin.doctor.v1"),
    ("recovery-readiness", RECOVERY_READINESS_SCHEMA),
    ("installed-app-inventory", INSTALLED_APP_INVENTORY_SCHEMA),
    ("windows-inventory", WINDOWS_INVENTORY_SCHEMA),
    ("official-command-plan", OFFICIAL_COMMAND_PLAN_SCHEMA),
    ("debloat-privacy-report", DEBLOAT_PRIVACY_REPORT_SCHEMA),
    ("startup-service-inventory", STARTUP_SERVICE_INVENTORY_SCHEMA),
]


def test_ai_readiness_is_valid_and_registers_critical_schemas(
    assert_schemas_registered: AssertSchemasRegistered,
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
) -> None:
    report = ai_readiness_report()
    assert_payload_schema(report, "cleanwin.ai-readiness.v1")
    assert_payload_status_true(report, "ready_for_ai_host")
    assert_payload_status_true(report, "ready_for_mcp")
    validation = validate_ai_readiness(report)
    assert_payload_status_true(validation, "valid")

    assert_schemas_registered(
        [
            "cleanwin.ai-readiness.v1",
            "cleanwin.ai-readiness-validation.v1",
            "cleanwin.ai-self-test.v1",
            "cleanwin.ai-runbook.v1",
            WORKFLOW_ROUTER_SCHEMA,
            ENVIRONMENT_INDEX_SCHEMA,
            WORKFLOW_DECISION_SCHEMA,
            WORKFLOW_TRACE_SCHEMA,
            RECOVERY_READINESS_SCHEMA,
            INSTALLED_APP_INVENTORY_SCHEMA,
            "cleanwin.installed-app-leftover-evidence-link.v1",
            WINDOWS_INVENTORY_SCHEMA,
            "cleanwin.windows-inventory-collection-plan.v1",
            "cleanwin.appx-package-classification.v1",
            "cleanwin.appx-package-snapshot.v1",
            "cleanwin.provisioned-appx-package-snapshot.v1",
            OFFICIAL_COMMAND_PLAN_SCHEMA,
            DEBLOAT_PRIVACY_REPORT_SCHEMA,
            "cleanwin.promotion-gate-validation.v1",
            "cleanwin.system-health-evidence.v1",
            "cleanwin.dism-component-store-analysis.v1",
            "cleanwin.dism-health-evidence.v1",
            "cleanwin.pending-reboot-registry-evidence.v1",
            STARTUP_SERVICE_INVENTORY_SCHEMA,
            "cleanwin.external-rule-translation.v1",
            "cleanwin.external-rule-candidate.v1",
            "cleanwin.windows-native-artifacts.v1",
            "cleanwin.windows-native-artifact-contract.v1",
            "cleanwin.windows-native-collector-wrapper.v1",
            "cleanwin.windows-native-artifact-parse.v1",
            "cleanwin.windows-snapshot-artifact-matrix.v1",
        ]
    )


def test_ai_self_test_passes_expected_policy_checks(
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_true: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = ai_self_test_report()
    assert_payload_schema(report, "cleanwin.ai-self-test.v1")
    assert_payload_status_true(report, "passed")
    test_names = {test["name"] for test in report["tests"]}
    assert_contains_all(
        test_names,
        [
            "raw_command_denied",
            "destructive_missing_gates_denied",
            "destructive_all_gates_allowed_by_policy",
        ],
    )


def test_ai_runbook_documents_safe_execution_gates(
    assert_payload_schema: AssertPayloadSchema,
    assert_field_values: AssertFieldValues,
    assert_exact_sequence: AssertExactSequence,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = ai_runbook_report()
    assert_payload_schema(report, "cleanwin.ai-runbook.v1")
    tools = [step["tool"] for step in report["workflow"]]
    assert_exact_sequence([tools[0], tools[-1]], ["cleanwin_workflow_router", "cleanwin_execute_plan"])
    assert_field_values(report["workflow"][-1], {"destructive": True})
    required_args = report["required_execution_arguments"]
    assert_field_values(required_args, {"delete_mode": "recycle", "require_plan_context": True})
    contract = report["low_risk_cache_execution_contract"]
    assert_field_values(
        contract,
        {
            "schema": "cleanwin.low-risk-cache-execution-contract.v1",
            "requires_exact_filesystem_identity": True,
            "requires_operation_log": True,
            "requires_matching_dry_run_token": True,
        },
    )
    assert_contains_all(contract["allowed_delete_modes"], ["recycle"])
    assert_contains_all(contract["forbidden_actions"], ["permanent-delete", "registry-mutation", "appx-removal", "process-kill"])


def test_workflow_router_routes_intents_without_enabling_execution(
    assert_readonly_report: AssertReadonlyReport,
    assert_readonly_payload: AssertReadonlyPayload,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = workflow_router_report()
    assert_readonly_report(report, WORKFLOW_ROUTER_SCHEMA)
    routes = {route["id"]: route for route in report["routes"]}
    assert_field_values(routes["read-only-inventory"], {"auto_call_allowed": True})
    assert_readonly_payload(routes["dry-run-execution"])
    assert_field_values(routes["recycle-execution"], {"destructive": True, "auto_call_allowed": False})
    assert_any_text_contains(routes["recycle-execution"]["required_previous_steps"], "dry-run-execution")
    assert_any_text_contains(routes["recycle-execution"]["blocked_actions"], "permanent delete")


def test_environment_index_is_readonly_and_reports_fail_closed_execution(
    assert_readonly_report: AssertReadonlyReport,
    assert_contains_all: AssertContainsAll,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = environment_index_report()
    assert_readonly_report(report, ENVIRONMENT_INDEX_SCHEMA)
    capabilities = {capability["id"]: capability for capability in report["capabilities"]}
    assert_field_values(capabilities["read-only-inventory"], {"available": True})
    assert_contains_all(set(capabilities), ["windows-recycle-execution"])
    assert_field_values(report, {"operation_log.write_checked": False})
    assert_any_text_contains(report["fail_closed"], "permanent delete route is not exposed")


def test_workflow_decision_blocks_destructive_route_without_artifacts(
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_false: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    decision = workflow_decision_report(route_id="recycle-execution", requested_tool="cleanwin_execute_plan")
    assert_payload_schema(decision, WORKFLOW_DECISION_SCHEMA)
    assert_payload_status_false(decision, "allowed")
    codes = {reason["code"] for reason in decision["blocking_reasons"]}
    assert_contains_all(codes, ["MISSING_REQUIRED_ARTIFACTS", "DESTRUCTIVE_ROUTE_REQUIRES_MANUAL_GATES"])
    assert_contains_all(decision["missing_artifacts"], ["low-risk cache readiness validation"])


def test_workflow_trace_documents_required_artifact_chain(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
) -> None:
    trace = workflow_trace_report()
    assert_readonly_report(trace, WORKFLOW_TRACE_SCHEMA)
    schemas = [item["artifact_schema"] for item in trace["artifact_chain"]]
    assert_contains_all(
        schemas,
        [
            "cleanwin.plan.v1",
            "cleanwin.review.v1",
            "cleanwin.ai-confirmation-summary.v1",
            "cleanwin.low-risk-cache-readiness-validation.v1",
            "cleanwin.operation-log.jsonl",
        ],
    )
    assert_execution_disabled(trace["execution_gate"], "ai_auto_call_allowed")


def test_cli_exposes_readiness_self_test_and_runbook(
    cleanwin_json: CleanWinJSON,
    assert_cli_provider_schemas: AssertCliProviderSchemas,
    assert_ai_provider_schemas: AssertAIProviderSchemas,
    assert_payload_schema: AssertPayloadSchema,
    assert_readonly_report: AssertReadonlyReport,
    assert_payload_status_true: AssertPayloadStatus,
    assert_field_values: AssertFieldValues,
) -> None:
    assert_field_values(cleanwin_json("ai-readiness"), {"ready_for_ai_host": True})
    assert_payload_status_true(cleanwin_json("ai-readiness", "--validate"), "valid")
    assert_payload_status_true(cleanwin_json("ai-self-test"), "passed")
    assert_payload_schema(cleanwin_json("ai-runbook"), "cleanwin.ai-runbook.v1")
    assert_payload_schema(cleanwin_json("workflow-router"), WORKFLOW_ROUTER_SCHEMA)
    assert_payload_schema(cleanwin_json("environment-index"), ENVIRONMENT_INDEX_SCHEMA)
    assert_payload_schema(cleanwin_json("workflow-decision", "--route-id", "recycle-execution"), WORKFLOW_DECISION_SCHEMA)
    assert_payload_schema(cleanwin_json("workflow-trace"), WORKFLOW_TRACE_SCHEMA)

    doctor_payload = cleanwin_json("doctor")
    assert_payload_schema(doctor_payload, "cleanwin.doctor.v1")
    assert_payload_status_true(doctor_payload, "ready")
    assert_readonly_report(doctor_payload, "cleanwin.doctor.v1")

    assert_cli_provider_schemas(EXPECTED_READINESS_PROVIDERS[8:])
    assert_ai_provider_schemas(EXPECTED_READINESS_PROVIDERS)


def test_doctor_report_checks_static_safety_and_contracts(
    assert_command_sequence: AssertCommandSequence,
    assert_readonly_report: AssertReadonlyReport,
    assert_payload_status_true: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_one_of: AssertOneOf,
) -> None:
    report = doctor_report()
    assert_readonly_report(report, "cleanwin.doctor.v1")
    assert_payload_status_true(report, "ready")
    check_ids = {check["id"] for check in report["checks"]}
    assert_contains_all(
        check_ids,
        [
            "single_destructive_exit",
            "delete_primitives_owned_by_delete_ops",
            "ai_contracts_valid",
            "version_consistency",
        ],
    )
    version_check = next(check for check in report["checks"] if check["id"] == "version_consistency")
    assert_payload_status_true(version_check, "passed")
    assert_field_values(
        version_check,
        {
            "evidence.package_version": __version__,
            "evidence.pyproject_version": __version__,
            "evidence.capabilities_version": __version__,
        },
    )
    assert_one_of(version_check["evidence"]["distribution_version"], {None, __version__})
    assert_command_sequence(report["recommended_commands"], [])


@pytest.mark.parametrize("command", EXPECTED_DOCTOR_COMMANDS)
def test_doctor_report_recommends_quality_command(command: list[str], assert_one_of: AssertOneOf) -> None:
    assert_one_of(command, doctor_report()["recommended_commands"])


def test_ai_readiness_release_gates_use_pytest_workflow(
    assert_command_sequence: AssertCommandSequence,
) -> None:
    report = ai_readiness_report()

    assert_command_sequence(report["release_gate_commands"], ["make pytest", "make lint", "make type", "make quality"])
