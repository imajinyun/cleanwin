from __future__ import annotations

from collections.abc import Callable

import pytest

from cleanwincli import __version__
from cleanwincli.ai_readiness import ai_readiness_report, validate_ai_readiness
from cleanwincli.ai_runbook import ai_runbook_report
from cleanwincli.ai_self_test import ai_self_test_report
from cleanwincli.ai_versioning import schema_registry
from cleanwincli.core import doctor_report
from cleanwincli.debloat_privacy import DEBLOAT_PRIVACY_REPORT_SCHEMA
from cleanwincli.installed_apps import INSTALLED_APP_INVENTORY_SCHEMA
from cleanwincli.official_commands import OFFICIAL_COMMAND_PLAN_SCHEMA
from cleanwincli.recovery import RECOVERY_READINESS_SCHEMA
from cleanwincli.startup_inventory import STARTUP_SERVICE_INVENTORY_SCHEMA

JSONPayload = dict[str, object]
CleanWinJSON = Callable[..., JSONPayload]


def test_ai_readiness_is_valid_and_registers_critical_schemas() -> None:
    report = ai_readiness_report()
    assert report["schema"] == "cleanwin.ai-readiness.v1"
    assert report["ready_for_ai_host"], report
    assert report["ready_for_mcp"], report
    validation = validate_ai_readiness(report)
    assert validation["valid"], validation

    names = {entry["name"] for entry in schema_registry()["entries"]}
    for required in [
        "cleanwin.ai-readiness.v1",
        "cleanwin.ai-readiness-validation.v1",
        "cleanwin.ai-self-test.v1",
        "cleanwin.ai-runbook.v1",
        RECOVERY_READINESS_SCHEMA,
        INSTALLED_APP_INVENTORY_SCHEMA,
        OFFICIAL_COMMAND_PLAN_SCHEMA,
        DEBLOAT_PRIVACY_REPORT_SCHEMA,
        STARTUP_SERVICE_INVENTORY_SCHEMA,
    ]:
        assert required in names


def test_ai_self_test_passes_expected_policy_checks() -> None:
    report = ai_self_test_report()
    assert report["schema"] == "cleanwin.ai-self-test.v1"
    assert report["passed"], report
    test_names = {test["name"] for test in report["tests"]}
    assert "raw_command_denied" in test_names
    assert "destructive_missing_gates_denied" in test_names
    assert "destructive_all_gates_allowed_by_policy" in test_names


def test_ai_runbook_documents_safe_execution_gates() -> None:
    report = ai_runbook_report()
    assert report["schema"] == "cleanwin.ai-runbook.v1"
    tools = [step["tool"] for step in report["workflow"]]
    assert tools[-1] == "cleanwin_execute_plan"
    assert report["workflow"][-1]["destructive"]
    required_args = report["required_execution_arguments"]
    assert required_args["delete_mode"] == "recycle"
    assert required_args["require_plan_context"]


def test_cli_exposes_readiness_self_test_and_runbook(
    cleanwin_json: CleanWinJSON,
) -> None:
    assert cleanwin_json("ai-readiness")["ready_for_ai_host"]
    assert cleanwin_json("ai-readiness", "--validate")["valid"]
    assert cleanwin_json("ai-self-test")["passed"]
    assert cleanwin_json("ai-runbook")["schema"] == "cleanwin.ai-runbook.v1"

    doctor_payload = cleanwin_json("doctor")
    assert doctor_payload["schema"] == "cleanwin.doctor.v1"
    assert doctor_payload["ready"], doctor_payload
    assert not doctor_payload["destructive"]

    expected_schemas = [
        ("recovery-readiness", RECOVERY_READINESS_SCHEMA),
        ("installed-app-inventory", INSTALLED_APP_INVENTORY_SCHEMA),
        ("official-command-plan", OFFICIAL_COMMAND_PLAN_SCHEMA),
        ("debloat-privacy-report", DEBLOAT_PRIVACY_REPORT_SCHEMA),
        ("startup-service-inventory", STARTUP_SERVICE_INVENTORY_SCHEMA),
    ]
    for command, schema in expected_schemas:
        assert cleanwin_json(command)["schema"] == schema


def test_doctor_report_checks_static_safety_and_contracts() -> None:
    report = doctor_report()
    assert report["schema"] == "cleanwin.doctor.v1"
    assert report["ready"], report
    assert not report["destructive"]
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
    assert ["python3", "-m", "pytest", "-q"] in report["recommended_commands"]
    assert ["python3", "-m", "ruff", "check", "cleanwin.py", "cleanwincli", "tests"] in report["recommended_commands"]
    assert ["python3", "-m", "mypy", "cleanwin.py", "cleanwincli", "tests"] in report["recommended_commands"]
    assert ["python3", "-m", "build", "--sdist", "--wheel"] in report["recommended_commands"]
    assert ["make", "package-install-smoke"] in report["recommended_commands"]
    assert ["make", "sdist-install-smoke"] in report["recommended_commands"]
    assert ["make", "mcp-install-smoke"] in report["recommended_commands"]
    assert ["make", "docs-smoke"] in report["recommended_commands"]
    assert ["make", "ai-smoke"] in report["recommended_commands"]
    assert ["make", "mcp-smoke"] in report["recommended_commands"]
    assert ["make", "version-smoke"] in report["recommended_commands"]
    assert ["make", "clean"] in report["recommended_commands"]
    assert ["make", "quality"] in report["recommended_commands"]


@pytest.mark.parametrize(
    ("provider", "schema"),
    [
        ("readiness", "cleanwin.ai-readiness.v1"),
        ("self-test", "cleanwin.ai-self-test.v1"),
        ("runbook", "cleanwin.ai-runbook.v1"),
        ("doctor", "cleanwin.doctor.v1"),
        ("recovery-readiness", RECOVERY_READINESS_SCHEMA),
        ("installed-app-inventory", INSTALLED_APP_INVENTORY_SCHEMA),
        ("official-command-plan", OFFICIAL_COMMAND_PLAN_SCHEMA),
        ("debloat-privacy-report", DEBLOAT_PRIVACY_REPORT_SCHEMA),
        ("startup-service-inventory", STARTUP_SERVICE_INVENTORY_SCHEMA),
    ],
)
def test_ai_tools_provider_aliases_readiness_reports(
    provider: str,
    schema: str,
    cleanwin_json: CleanWinJSON,
) -> None:
    assert cleanwin_json("ai-tools", "--provider", provider)["schema"] == schema
