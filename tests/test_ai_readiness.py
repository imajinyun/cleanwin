from __future__ import annotations

from collections.abc import Callable

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
from cleanwincli.workflow_artifacts import (
    WORKFLOW_DECISION_SCHEMA,
    WORKFLOW_TRACE_SCHEMA,
    workflow_decision_report,
    workflow_trace_report,
)
from cleanwincli.workflow_router import WORKFLOW_ROUTER_SCHEMA, workflow_router_report

JSONPayload = dict[str, object]
CleanWinJSON = Callable[..., JSONPayload]
AssertSchemasRegistered = Callable[[list[str]], None]
AssertCliProviderSchema = Callable[[str, str], None]
AssertCliProviderSchemas = Callable[[list[tuple[str, str]]], None]
AssertAIProviderSchemas = Callable[[list[tuple[str, str]]], None]
AssertCommandSequence = Callable[[list[str] | list[list[str]], list[str] | list[list[str]]], None]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyPayload = Callable[[JSONPayload], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]

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
    ("official-command-plan", OFFICIAL_COMMAND_PLAN_SCHEMA),
    ("debloat-privacy-report", DEBLOAT_PRIVACY_REPORT_SCHEMA),
    ("startup-service-inventory", STARTUP_SERVICE_INVENTORY_SCHEMA),
]


def test_ai_readiness_is_valid_and_registers_critical_schemas(
    assert_schemas_registered: AssertSchemasRegistered,
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    report = ai_readiness_report()
    assert_payload_schema(report, "cleanwin.ai-readiness.v1")
    assert report["ready_for_ai_host"], report
    assert report["ready_for_mcp"], report
    validation = validate_ai_readiness(report)
    assert validation["valid"], validation

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
            OFFICIAL_COMMAND_PLAN_SCHEMA,
            DEBLOAT_PRIVACY_REPORT_SCHEMA,
            STARTUP_SERVICE_INVENTORY_SCHEMA,
        ]
    )


def test_ai_self_test_passes_expected_policy_checks(assert_payload_schema: AssertPayloadSchema) -> None:
    report = ai_self_test_report()
    assert_payload_schema(report, "cleanwin.ai-self-test.v1")
    assert report["passed"], report
    test_names = {test["name"] for test in report["tests"]}
    assert "raw_command_denied" in test_names
    assert "destructive_missing_gates_denied" in test_names
    assert "destructive_all_gates_allowed_by_policy" in test_names


def test_ai_runbook_documents_safe_execution_gates(assert_payload_schema: AssertPayloadSchema) -> None:
    report = ai_runbook_report()
    assert_payload_schema(report, "cleanwin.ai-runbook.v1")
    tools = [step["tool"] for step in report["workflow"]]
    assert tools[0] == "cleanwin_workflow_router"
    assert tools[-1] == "cleanwin_execute_plan"
    assert report["workflow"][-1]["destructive"]
    required_args = report["required_execution_arguments"]
    assert required_args["delete_mode"] == "recycle"
    assert required_args["require_plan_context"]


def test_workflow_router_routes_intents_without_enabling_execution(
    assert_readonly_report: AssertReadonlyReport,
    assert_readonly_payload: AssertReadonlyPayload,
) -> None:
    report = workflow_router_report()
    assert_readonly_report(report, WORKFLOW_ROUTER_SCHEMA)
    routes = {route["id"]: route for route in report["routes"]}
    assert routes["read-only-inventory"]["auto_call_allowed"] is True
    assert_readonly_payload(routes["dry-run-execution"])
    assert routes["recycle-execution"]["destructive"] is True
    assert routes["recycle-execution"]["auto_call_allowed"] is False
    assert "dry-run-execution" in routes["recycle-execution"]["required_previous_steps"]
    assert "permanent delete" in routes["recycle-execution"]["blocked_actions"]


def test_environment_index_is_readonly_and_reports_fail_closed_execution(
    assert_readonly_report: AssertReadonlyReport,
) -> None:
    report = environment_index_report()
    assert_readonly_report(report, ENVIRONMENT_INDEX_SCHEMA)
    capabilities = {capability["id"]: capability for capability in report["capabilities"]}
    assert capabilities["read-only-inventory"]["available"] is True
    assert "windows-recycle-execution" in capabilities
    assert report["operation_log"]["write_checked"] is False
    assert "permanent delete route is not exposed" in report["fail_closed"]


def test_workflow_decision_blocks_destructive_route_without_artifacts(
    assert_payload_schema: AssertPayloadSchema,
) -> None:
    decision = workflow_decision_report(route_id="recycle-execution", requested_tool="cleanwin_execute_plan")
    assert_payload_schema(decision, WORKFLOW_DECISION_SCHEMA)
    assert decision["allowed"] is False
    codes = {reason["code"] for reason in decision["blocking_reasons"]}
    assert "MISSING_REQUIRED_ARTIFACTS" in codes
    assert "DESTRUCTIVE_ROUTE_REQUIRES_MANUAL_GATES" in codes


def test_workflow_trace_documents_required_artifact_chain(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    trace = workflow_trace_report()
    assert_readonly_report(trace, WORKFLOW_TRACE_SCHEMA)
    schemas = [item["artifact_schema"] for item in trace["artifact_chain"]]
    assert "cleanwin.plan.v1" in schemas
    assert "cleanwin.review.v1" in schemas
    assert "cleanwin.ai-confirmation-summary.v1" in schemas
    assert_execution_disabled(trace["execution_gate"], "ai_auto_call_allowed")


def test_cli_exposes_readiness_self_test_and_runbook(
    cleanwin_json: CleanWinJSON,
    assert_cli_provider_schemas: AssertCliProviderSchemas,
    assert_ai_provider_schemas: AssertAIProviderSchemas,
    assert_payload_schema: AssertPayloadSchema,
    assert_readonly_report: AssertReadonlyReport,
) -> None:
    assert cleanwin_json("ai-readiness")["ready_for_ai_host"]
    assert cleanwin_json("ai-readiness", "--validate")["valid"]
    assert cleanwin_json("ai-self-test")["passed"]
    assert_payload_schema(cleanwin_json("ai-runbook"), "cleanwin.ai-runbook.v1")
    assert_payload_schema(cleanwin_json("workflow-router"), WORKFLOW_ROUTER_SCHEMA)
    assert_payload_schema(cleanwin_json("environment-index"), ENVIRONMENT_INDEX_SCHEMA)
    assert_payload_schema(cleanwin_json("workflow-decision", "--route-id", "recycle-execution"), WORKFLOW_DECISION_SCHEMA)
    assert_payload_schema(cleanwin_json("workflow-trace"), WORKFLOW_TRACE_SCHEMA)

    doctor_payload = cleanwin_json("doctor")
    assert_payload_schema(doctor_payload, "cleanwin.doctor.v1")
    assert doctor_payload["ready"], doctor_payload
    assert_readonly_report(doctor_payload, "cleanwin.doctor.v1")

    assert_cli_provider_schemas(EXPECTED_READINESS_PROVIDERS[8:])
    assert_ai_provider_schemas(EXPECTED_READINESS_PROVIDERS)


def test_doctor_report_checks_static_safety_and_contracts(
    assert_command_sequence: AssertCommandSequence,
    assert_readonly_report: AssertReadonlyReport,
) -> None:
    report = doctor_report()
    assert_readonly_report(report, "cleanwin.doctor.v1")
    assert report["ready"], report
    check_ids = {check["id"] for check in report["checks"]}
    assert "single_destructive_exit" in check_ids
    assert "delete_primitives_owned_by_delete_ops" in check_ids
    assert "ai_contracts_valid" in check_ids
    assert "version_consistency" in check_ids
    version_check = next(check for check in report["checks"] if check["id"] == "version_consistency")
    assert version_check["passed"], version_check
    assert version_check["evidence"]["package_version"] == __version__
    assert version_check["evidence"]["pyproject_version"] == __version__
    assert version_check["evidence"]["distribution_version"] in {None, __version__}
    assert version_check["evidence"]["capabilities_version"] == __version__
    assert_command_sequence(report["recommended_commands"], [])


@pytest.mark.parametrize("command", EXPECTED_DOCTOR_COMMANDS)
def test_doctor_report_recommends_quality_command(command: list[str]) -> None:
    assert command in doctor_report()["recommended_commands"]


def test_ai_readiness_release_gates_use_pytest_workflow(
    assert_command_sequence: AssertCommandSequence,
) -> None:
    report = ai_readiness_report()

    assert_command_sequence(report["release_gate_commands"], ["make pytest", "make lint", "make type", "make quality"])
