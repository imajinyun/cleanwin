from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.operation_log_readiness import (
    OPERATION_LOG_READINESS_SCHEMA,
    OPERATION_LOG_READINESS_VALIDATION_SCHEMA,
    operation_log_readiness_report,
    validate_operation_log_readiness,
)

JSONPayload = dict[str, Any]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]


def _operation_log_readiness_ref(**overrides: Any) -> JSONPayload:
    payload: JSONPayload = {
        "schema": OPERATION_LOG_READINESS_SCHEMA,
        "operation_log_ref": "operation-log://cleanwin/ops.jsonl",
        "dry_run_token_ref": "dry-run-token://cleanwin/token-1",
        "plan_fingerprint": "f" * 64,
        "delete_mode": "recycle",
        "operation_id": "op-001",
        "rule_id": "browser-cache.chrome.default.cache",
        "resolved_path": r"C:\Users\tester\AppData\Local\Google\Chrome\User Data\Default\Cache",
        "identity_before_ref": "identity://before/browser-cache",
        "recycle_ref": "recycle://cleanwin/op-001",
        "result_status": "prepared",
    }
    payload.update(overrides)
    return payload


def _proposed_action(**overrides: Any) -> JSONPayload:
    payload: JSONPayload = {
        "target_action": "browser-cache-delete",
        "operation_log_ref": "operation-log://cleanwin/ops.jsonl",
        "dry_run_token_ref": "dry-run-token://cleanwin/token-1",
        "plan_fingerprint": "f" * 64,
        "operation_log_readiness_ref": _operation_log_readiness_ref(),
    }
    payload.update(overrides)
    return payload


def test_operation_log_readiness_is_readonly_and_registered(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    report = assert_readonly_report(operation_log_readiness_report(), OPERATION_LOG_READINESS_SCHEMA)

    assert_execution_disabled(report, "execution_enabled")
    assert_summary_counts(report, {"required_field_count": 11, "control_count": 4, "execution_enabled_count": 0})
    assert_contains_all(
        report["required_fields"],
        ["operation_log_ref", "dry_run_token_ref", "plan_fingerprint", "delete_mode", "identity_before_ref", "recycle_ref"],
    )
    assert_contains_all(
        report["promotion_validator"]["violation_codes"],
        ["MISSING_OPERATION_LOG_READINESS_REF", "RECYCLE_MODE_REQUIRED", "PLAN_FINGERPRINT_MISMATCH", "DRY_RUN_TOKEN_REF_MISMATCH"],
    )
    assert_cli_provider_schema_sample("operation-log-readiness", OPERATION_LOG_READINESS_SCHEMA)


def test_operation_log_readiness_validation_requires_structured_ref(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    missing = validate_operation_log_readiness(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action={"target_action": "browser-cache-delete"},
    )
    unstructured = validate_operation_log_readiness(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action=_proposed_action(operation_log_readiness_ref="operation-log://cleanwin/ops.jsonl"),
    )

    assert_payload_schema(missing, OPERATION_LOG_READINESS_VALIDATION_SCHEMA)
    assert_field_values(missing, {"valid": False, "safe_to_execute": False})
    assert_contains_all(missing["missing_evidence"], ["operation_log_readiness_ref"])
    assert_contains_all({error["code"] for error in missing["errors"]}, ["MISSING_OPERATION_LOG_READINESS_REF"])
    assert_contains_all({error["code"] for error in unstructured["errors"]}, ["INVALID_OPERATION_LOG_READINESS_REF"])
    assert_execution_disabled(missing)
    assert_execution_disabled(unstructured)


def test_operation_log_readiness_validation_rejects_non_recycle_delete_mode(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_operation_log_readiness(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action=_proposed_action(operation_log_readiness_ref=_operation_log_readiness_ref(delete_mode="permanent")),
    )

    assert_payload_schema(validation, OPERATION_LOG_READINESS_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": False, "safe_to_execute": False})
    assert_contains_all({error["code"] for error in validation["errors"]}, ["RECYCLE_MODE_REQUIRED"])
    assert_execution_disabled(validation)


def test_operation_log_readiness_validation_binds_dry_run_token_and_plan_fingerprint(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_operation_log_readiness(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action=_proposed_action(
            dry_run_token_ref="dry-run-token://cleanwin/expected",
            plan_fingerprint="e" * 64,
            operation_log_readiness_ref=_operation_log_readiness_ref(
                dry_run_token_ref="dry-run-token://cleanwin/actual",
                plan_fingerprint="f" * 64,
            ),
        ),
    )

    assert_payload_schema(validation, OPERATION_LOG_READINESS_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": False, "safe_to_execute": False})
    assert_contains_all({error["code"] for error in validation["errors"]}, ["DRY_RUN_TOKEN_REF_MISMATCH", "PLAN_FINGERPRINT_MISMATCH"])
    assert_execution_disabled(validation)
