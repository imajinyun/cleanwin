from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.scan_governance import SCAN_GOVERNANCE_SCHEMA, scan_governance_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[list[str]], dict[str, JSONPayload]]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_scan_governance_is_read_only_and_release_gated(
    assert_readonly_report: AssertReadonlyReport,
    assert_contains_all: AssertContainsAll,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = scan_governance_report()

    assert_readonly_report(report, SCAN_GOVERNANCE_SCHEMA)
    assert_field_values(report["release_gate"], {"requires_quality": True, "blocks_execution_expansion": True})
    assert_contains_all(report["release_gate"]["required_commands"], ["make quality"])
    assert_any_text_contains(report["non_goals"], "does not import external cleaner rules")


def test_scan_budgets_and_external_rule_contract_block_unsafe_imports(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = scan_governance_report()
    by_id = {budget["id"]: budget for budget in report["scan_budgets"]}

    assert_field_values(by_id["default-inspect"], {"max_items": 100})
    assert_field_values(
        by_id["file-report"],
        {
            "max_files_scanned": 2000,
            "max_hash_bytes_per_file": 1048576,
            "permission_error_policy": "aggregate-and-continue",
        },
    )

    contract = report["external_rule_contract"]
    assert_payload_schema(contract, "cleanwin.external-rule-review.v1")
    assert_field_values(contract, {"default_state": "report-only"})
    assert_execution_disabled(contract)
    assert_contains_all(contract["required_source_evidence"], ["license"])
    assert_contains_all(contract["required_safety_evidence"], ["sensitive_exclusions"])
    assert_contains_all(contract["blocked_patterns"], ["raw shell command strings"])
    assert_contains_all(contract["promotion_requirements"], ["promotion-gate approval"])


def test_cli_provider_and_schema_registry_expose_scan_governance(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    assert_cli_provider_schema_sample("scan-governance", SCAN_GOVERNANCE_SCHEMA)
    assert_schema_samples(["cleanwin.external-rule-review.v1"])
