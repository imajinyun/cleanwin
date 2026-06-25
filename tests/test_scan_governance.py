from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.scan_governance import SCAN_GOVERNANCE_SCHEMA, scan_governance_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[list[str]], dict[str, JSONPayload]]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[[JSONPayload], JSONPayload]


def test_scan_governance_is_read_only_and_release_gated(assert_readonly_report: AssertReadonlyReport) -> None:
    report = scan_governance_report()

    assert_readonly_report(report, SCAN_GOVERNANCE_SCHEMA)
    assert report["release_gate"]["requires_quality"] is True
    assert "make quality" in report["release_gate"]["required_commands"]
    assert report["release_gate"]["blocks_execution_expansion"] is True
    assert any("does not import external cleaner rules" in item for item in report["non_goals"])


def test_scan_budgets_and_external_rule_contract_block_unsafe_imports(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    report = scan_governance_report()
    by_id = {budget["id"]: budget for budget in report["scan_budgets"]}

    assert by_id["default-inspect"]["max_items"] == 100
    assert by_id["file-report"]["max_files_scanned"] == 2000
    assert by_id["file-report"]["max_hash_bytes_per_file"] == 1048576
    assert by_id["file-report"]["permission_error_policy"] == "aggregate-and-continue"

    contract = report["external_rule_contract"]
    assert_payload_schema(contract, "cleanwin.external-rule-review.v1")
    assert contract["default_state"] == "report-only"
    assert_execution_disabled(contract)
    assert "license" in contract["required_source_evidence"]
    assert "sensitive_exclusions" in contract["required_safety_evidence"]
    assert "raw shell command strings" in contract["blocked_patterns"]
    assert "promotion-gate approval" in contract["promotion_requirements"]


def test_cli_provider_and_schema_registry_expose_scan_governance(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    assert_cli_provider_schema_sample("scan-governance", SCAN_GOVERNANCE_SCHEMA)
    assert_schema_samples(["cleanwin.external-rule-review.v1"])
