from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.contract_exposure import (
    CONTRACT_EXPOSURE_MATRIX_SCHEMA,
    CONTRACT_EXPOSURE_VALIDATION_SCHEMA,
    MISSING_AI_TOOLS_PROVIDER,
    MISSING_CLI_COMMAND,
    MISSING_DOCS_REFERENCE,
    MISSING_EVIDENCE_BUNDLE_REFERENCE,
    MISSING_MCP_RESOURCE,
    MISSING_SCHEMA_REGISTRY_ENTRY,
    MISSING_WORKFLOW_TRACE_REFERENCE,
    contract_exposure_matrix,
    validate_contract_exposure_matrix,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertPayloadStatus = Callable[..., JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]
AssertAllMatch = Callable[[Sequence[Any], Callable[[Any], bool]], Sequence[Any]]
AssertExactCount = Callable[[Sequence[Any], int], Sequence[Any]]


def _row_by_id(matrix: JSONPayload) -> dict[str, JSONPayload]:
    return {row["contract_id"]: row for row in matrix["rows"]}


def _missing_row() -> JSONPayload:
    return {
        "contract_id": "fixture-contract",
        "schemas": [{"name": "cleanwin.fixture.v1", "status": "missing", "present": False}],
        "cli_command": {"name": "fixture-command", "status": "missing", "present": False},
        "ai_tools_provider": {"name": "fixture-provider", "status": "missing", "present": False},
        "mcp_resource": {"name": "cleanwin://fixture/missing", "status": "missing", "present": False},
        "workflow_trace": {"name": "cleanwin.fixture-trace.v1", "status": "missing", "present": False},
        "evidence_bundle": {"name": "cleanwin.fixture-evidence.v1", "status": "missing", "present": False},
        "docs": {"name": "fixture docs ref", "status": "missing", "present": False},
    }


def test_contract_exposure_matrix_covers_governance_contracts(
    assert_readonly_report: AssertReadonlyReport,
    assert_payload_status_true: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_summary_counts: AssertSummaryCounts,
    assert_all_match: AssertAllMatch,
    assert_exact_count: AssertExactCount,
) -> None:
    matrix = assert_readonly_report(contract_exposure_matrix(), CONTRACT_EXPOSURE_MATRIX_SCHEMA)
    rows = _row_by_id(matrix)

    assert_payload_status_true(matrix, "valid")
    assert_summary_counts(matrix, {"contract_count": 7, "missing_exposure_count": 0})
    assert_exact_count(matrix["rows"], 7)
    assert_contains_all(
        rows,
        [
            "low-risk-cache-readiness",
            "promotion-gates",
            "workflow-decision",
            "workflow-trace",
            "windows-evidence-bundle",
            "external-rule-quality",
            "native-collector-artifact-validation",
        ],
    )
    assert_field_values(
        rows["low-risk-cache-readiness"],
        {
            "cli_command.status": "present",
            "ai_tools_provider.status": "present",
            "mcp_resource.status": "present",
            "workflow_trace.status": "present",
            "evidence_bundle.status": "present",
            "docs.status": "present",
        },
    )
    assert_all_match(matrix["rows"], lambda row: all(schema["status"] == "present" for schema in row["schemas"]))


def test_contract_exposure_validation_reports_missing_exposure_codes(
    assert_payload_schema: AssertPayloadSchema,
    assert_payload_status_false: AssertPayloadStatus,
    assert_contains_all: AssertContainsAll,
) -> None:
    validation = assert_payload_schema(
        validate_contract_exposure_matrix({"schema": CONTRACT_EXPOSURE_MATRIX_SCHEMA, "rows": [_missing_row()]}),
        CONTRACT_EXPOSURE_VALIDATION_SCHEMA,
    )

    assert_payload_status_false(validation, "valid")
    codes = {error["code"] for error in validation["errors"]}
    assert_contains_all(
        codes,
        [
            MISSING_SCHEMA_REGISTRY_ENTRY,
            MISSING_CLI_COMMAND,
            MISSING_AI_TOOLS_PROVIDER,
            MISSING_MCP_RESOURCE,
            MISSING_DOCS_REFERENCE,
            MISSING_WORKFLOW_TRACE_REFERENCE,
            MISSING_EVIDENCE_BUNDLE_REFERENCE,
        ],
    )


def test_contract_exposure_cli_provider_schema_and_validation(
    cleanwin_json: CleanWinJSON,
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_payload_status_true: AssertPayloadStatus,
    assert_readonly_report: AssertReadonlyReport,
) -> None:
    sample = assert_readonly_report(
        assert_cli_provider_schema_sample("contract-exposure-matrix", CONTRACT_EXPOSURE_MATRIX_SCHEMA),
        CONTRACT_EXPOSURE_MATRIX_SCHEMA,
    )
    assert_payload_status_true(sample, "valid")
    assert_payload_status_true(cleanwin_json("contract-exposure-matrix", "--validate"), "valid")
