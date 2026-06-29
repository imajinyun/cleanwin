"""Read-only operation log readiness contract for cache execution review."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

OPERATION_LOG_READINESS_SCHEMA = "cleanwin.operation-log-readiness.v1"
OPERATION_LOG_READINESS_VALIDATION_SCHEMA = "cleanwin.operation-log-readiness-validation.v1"

OPERATION_LOG_READINESS_REQUIRED_FIELDS = [
    "schema",
    "operation_log_ref",
    "dry_run_token_ref",
    "plan_fingerprint",
    "delete_mode",
    "operation_id",
    "rule_id",
    "resolved_path",
    "identity_before_ref",
    "recycle_ref",
    "result_status",
]

OPERATION_LOG_READINESS_VIOLATION_CODES = [
    "MISSING_OPERATION_LOG_READINESS_REF",
    "INVALID_OPERATION_LOG_READINESS_REF",
    "OPERATION_LOG_READINESS_SCHEMA_REQUIRED",
    "MISSING_OPERATION_LOG_FIELD",
    "RECYCLE_MODE_REQUIRED",
    "PLAN_FINGERPRINT_MISMATCH",
    "DRY_RUN_TOKEN_REF_MISMATCH",
    "OPERATION_LOG_REF_MISMATCH",
]


def _operation_log_readiness_ref(source_report: Mapping[str, Any], proposed_action: Mapping[str, Any]) -> Any:
    if "operation_log_readiness_ref" in proposed_action:
        return proposed_action["operation_log_readiness_ref"]
    return source_report.get("operation_log_readiness_ref")


def _expected_value(source_report: Mapping[str, Any], proposed_action: Mapping[str, Any], key: str) -> str:
    value = proposed_action.get(key)
    if value is None:
        value = source_report.get(key)
    return str(value or "")


def validate_operation_log_readiness(
    *,
    source_report: Mapping[str, Any],
    proposed_action: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a structured operation log readiness artifact without executing cleanup."""
    readiness = _operation_log_readiness_ref(source_report, proposed_action)
    missing_evidence: list[str] = []
    errors: list[dict[str, str]] = []
    provided_fields: list[str] = []

    if readiness is None:
        missing_evidence.append("operation_log_readiness_ref")
        errors.append({"code": "MISSING_OPERATION_LOG_READINESS_REF", "detail": "operation_log_readiness_ref"})
    elif not isinstance(readiness, Mapping):
        errors.append({"code": "INVALID_OPERATION_LOG_READINESS_REF", "detail": "operation_log_readiness_ref must be a structured object"})
    else:
        provided_fields = sorted(str(key) for key in readiness.keys())
        if readiness.get("schema") != OPERATION_LOG_READINESS_SCHEMA:
            errors.append({"code": "OPERATION_LOG_READINESS_SCHEMA_REQUIRED", "detail": str(readiness.get("schema") or "missing schema")})
        for field in OPERATION_LOG_READINESS_REQUIRED_FIELDS:
            if readiness.get(field) in (None, ""):
                errors.append({"code": "MISSING_OPERATION_LOG_FIELD", "detail": field})
        if readiness.get("delete_mode") != "recycle":
            errors.append({"code": "RECYCLE_MODE_REQUIRED", "detail": "operation_log_readiness_ref.delete_mode"})

        expected_plan_fingerprint = _expected_value(source_report, proposed_action, "plan_fingerprint")
        if expected_plan_fingerprint and str(readiness.get("plan_fingerprint") or "") != expected_plan_fingerprint:
            errors.append({"code": "PLAN_FINGERPRINT_MISMATCH", "detail": "operation_log_readiness_ref.plan_fingerprint"})

        expected_dry_run_token_ref = _expected_value(source_report, proposed_action, "dry_run_token_ref")
        if expected_dry_run_token_ref and str(readiness.get("dry_run_token_ref") or "") != expected_dry_run_token_ref:
            errors.append({"code": "DRY_RUN_TOKEN_REF_MISMATCH", "detail": "operation_log_readiness_ref.dry_run_token_ref"})

        expected_operation_log_ref = _expected_value(source_report, proposed_action, "operation_log_ref")
        if expected_operation_log_ref and str(readiness.get("operation_log_ref") or "") != expected_operation_log_ref:
            errors.append({"code": "OPERATION_LOG_REF_MISMATCH", "detail": "operation_log_readiness_ref.operation_log_ref"})

    return {
        "schema": OPERATION_LOG_READINESS_VALIDATION_SCHEMA,
        "valid": not errors,
        "destructive": False,
        "dry_run": True,
        "execution_enabled": False,
        "target_action": str(proposed_action.get("target_action") or ""),
        "source_report_schema": str(source_report.get("schema") or proposed_action.get("source_report_schema") or ""),
        "required_schema": OPERATION_LOG_READINESS_SCHEMA,
        "required_fields": OPERATION_LOG_READINESS_REQUIRED_FIELDS,
        "provided_fields": provided_fields,
        "missing_evidence": sorted(set(missing_evidence)),
        "errors": errors,
        "safe_to_execute": False,
    }


def operation_log_readiness_report() -> dict[str, Any]:
    """Return the report-only contract for structured operation log readiness."""
    controls = [
        {
            "id": "operation-log-readiness.structured-ref",
            "required_evidence": ["operation_log_readiness_ref"],
            "violation_code": "MISSING_OPERATION_LOG_READINESS_REF",
            "rationale": "Low-risk cache promotion must bind to a structured operation log readiness artifact, not just a path string.",
        },
        {
            "id": "operation-log-readiness.recycle-mode",
            "required_evidence": ["delete_mode"],
            "violation_code": "RECYCLE_MODE_REQUIRED",
            "rationale": "The operation log readiness chain is valid only for recycle-mode cleanup.",
        },
        {
            "id": "operation-log-readiness.plan-fingerprint",
            "required_evidence": ["plan_fingerprint"],
            "violation_code": "PLAN_FINGERPRINT_MISMATCH",
            "rationale": "The readiness artifact must bind to the exact reviewed plan fingerprint.",
        },
        {
            "id": "operation-log-readiness.dry-run-token",
            "required_evidence": ["dry_run_token_ref"],
            "violation_code": "DRY_RUN_TOKEN_REF_MISMATCH",
            "rationale": "The readiness artifact must bind to the exact dry-run token reference for the reviewed plan.",
        },
    ]
    return {
        "schema": OPERATION_LOG_READINESS_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "execution_enabled": False,
        "target_action": "browser-cache-delete",
        "source_refs": [
            "cleanwin.plan.v1",
            "cleanwin.review.v1",
            "cleanwin.ai-confirmation-summary.v1",
            "cleanwin.low-risk-cache-readiness-validation.v1",
        ],
        "required_fields": OPERATION_LOG_READINESS_REQUIRED_FIELDS,
        "controls": controls,
        "promotion_validator": {
            "schema": OPERATION_LOG_READINESS_VALIDATION_SCHEMA,
            "safe_to_execute": False,
            "violation_codes": OPERATION_LOG_READINESS_VIOLATION_CODES,
        },
        "summary": {
            "required_field_count": len(OPERATION_LOG_READINESS_REQUIRED_FIELDS),
            "control_count": len(controls),
            "execution_enabled_count": 0,
        },
        "non_goals": [
            "This report does not write an operation log.",
            "This report does not execute cleanup.",
            "This report does not allow permanent delete or bypass dry-run token checks.",
        ],
    }
