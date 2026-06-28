"""Read-only low-risk cache execution readiness contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

LOW_RISK_CACHE_EXECUTION_READINESS_SCHEMA = "cleanwin.low-risk-cache-execution-readiness.v1"
LOW_RISK_CACHE_EXECUTION_READINESS_VALIDATION_SCHEMA = "cleanwin.low-risk-cache-readiness-validation.v1"

CACHE_READINESS_REQUIRED_EVIDENCE = [
    "dry_run_token_ref",
    "operation_log_ref",
    "locked_state_ref",
    "identity_check_ref",
    "sensitive_exclusions",
    "rule_quality_gate",
    "recycle_mode",
    "confirmation_phrase",
]

CACHE_READINESS_REQUIRED_TESTS = [
    "fixture-locked-profile",
    "fixture-sensitive-data-excluded",
    "cache-layer-classification",
    "execution-promotion-readiness",
]

CACHE_READINESS_VIOLATION_CODES = [
    "MISSING_DRY_RUN_TOKEN_EVIDENCE",
    "MISSING_OPERATION_LOG_EVIDENCE",
    "MISSING_LOCKED_STATE_EVIDENCE",
    "MISSING_IDENTITY_CHECK_EVIDENCE",
    "MISSING_SENSITIVE_EXCLUSION_EVIDENCE",
    "MISSING_RULE_QUALITY_GATE_EVIDENCE",
    "RECYCLE_MODE_REQUIRED",
    "MISSING_CONFIRMATION_PHRASE_EVIDENCE",
    "RULE_QUALITY_BLOCKS_CACHE_PROMOTION",
    "LOCKED_STATE_BLOCKS_CACHE_PROMOTION",
]


def _values_from_mapping(payload: Mapping[str, Any], key: str) -> set[str]:
    value = payload.get(key)
    if isinstance(value, Mapping):
        return {str(item) for item in value.keys()}
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return {str(item) for item in value}
    return set()


def _quality_gate_from_payload(source_report: Mapping[str, Any], proposed_action: Mapping[str, Any]) -> Mapping[str, Any]:
    quality_gate = proposed_action.get("quality_gate")
    if isinstance(quality_gate, Mapping):
        return quality_gate
    quality_gate = source_report.get("quality_gate")
    if isinstance(quality_gate, Mapping):
        return quality_gate
    candidates = source_report.get("candidates")
    if isinstance(candidates, Iterable) and not isinstance(candidates, str | bytes):
        for candidate in candidates:
            if isinstance(candidate, Mapping) and isinstance(candidate.get("quality_gate"), Mapping):
                return candidate["quality_gate"]
    review_queue = source_report.get("review_queue")
    if isinstance(review_queue, Iterable) and not isinstance(review_queue, str | bytes):
        for item in review_queue:
            if isinstance(item, Mapping) and isinstance(item.get("quality_gate"), Mapping):
                return item["quality_gate"]
    return {}


def validate_low_risk_cache_readiness(
    *,
    source_report: Mapping[str, Any],
    proposed_action: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate readiness evidence without enabling cache execution."""
    provided_evidence = _values_from_mapping(proposed_action, "evidence")
    missing_evidence: list[str] = []
    errors: list[dict[str, str]] = []
    evidence_error_codes = {
        "dry_run_token_ref": "MISSING_DRY_RUN_TOKEN_EVIDENCE",
        "operation_log_ref": "MISSING_OPERATION_LOG_EVIDENCE",
        "locked_state_ref": "MISSING_LOCKED_STATE_EVIDENCE",
        "identity_check_ref": "MISSING_IDENTITY_CHECK_EVIDENCE",
        "sensitive_exclusions": "MISSING_SENSITIVE_EXCLUSION_EVIDENCE",
        "rule_quality_gate": "MISSING_RULE_QUALITY_GATE_EVIDENCE",
        "recycle_mode": "RECYCLE_MODE_REQUIRED",
        "confirmation_phrase": "MISSING_CONFIRMATION_PHRASE_EVIDENCE",
    }
    for evidence in CACHE_READINESS_REQUIRED_EVIDENCE:
        if evidence not in provided_evidence:
            missing_evidence.append(evidence)
            errors.append({"code": evidence_error_codes[evidence], "detail": evidence})

    quality_gate = _quality_gate_from_payload(source_report, proposed_action)
    quality_gate_blockers: list[str] = []
    if not quality_gate:
        if "rule_quality_gate" not in missing_evidence:
            missing_evidence.append("rule_quality_gate")
        errors.append({"code": "MISSING_RULE_QUALITY_GATE_EVIDENCE", "detail": "quality_gate"})
    else:
        promotion_blockers = quality_gate.get("promotion_blockers")
        if isinstance(promotion_blockers, Iterable) and not isinstance(promotion_blockers, str | bytes):
            quality_gate_blockers = [str(blocker) for blocker in promotion_blockers if str(blocker)]
        if quality_gate_blockers or quality_gate.get("promotion_allowed") is not False or quality_gate.get("execution_enabled") is not False:
            errors.append(
                {
                    "code": "RULE_QUALITY_BLOCKS_CACHE_PROMOTION",
                    "detail": ", ".join(quality_gate_blockers) or "rule quality gate must remain report-only",
                }
            )

    return {
        "schema": LOW_RISK_CACHE_EXECUTION_READINESS_VALIDATION_SCHEMA,
        "valid": not errors,
        "destructive": False,
        "dry_run": True,
        "execution_enabled": False,
        "target_action": str(proposed_action.get("target_action") or ""),
        "source_report_schema": str(source_report.get("schema") or proposed_action.get("source_report_schema") or ""),
        "provided_evidence": sorted(provided_evidence),
        "required_evidence": CACHE_READINESS_REQUIRED_EVIDENCE,
        "missing_evidence": sorted(set(missing_evidence)),
        "quality_gate_blockers": sorted(set(quality_gate_blockers)),
        "errors": errors,
        "safe_to_execute": False,
    }


def low_risk_cache_execution_readiness_report() -> dict[str, Any]:
    """Return the machine-readable readiness contract for cache promotion."""
    controls = [
        {
            "id": "cache-readiness.dry-run-token",
            "required_evidence": ["dry_run_token_ref"],
            "violation_code": "MISSING_DRY_RUN_TOKEN_EVIDENCE",
            "rationale": "Execution review must be tied to the exact dry-run token produced for the reviewed plan.",
        },
        {
            "id": "cache-readiness.operation-log",
            "required_evidence": ["operation_log_ref"],
            "violation_code": "MISSING_OPERATION_LOG_EVIDENCE",
            "rationale": "Any future recycle execution must have a JSONL operation log destination before promotion.",
        },
        {
            "id": "cache-readiness.locked-state",
            "required_evidence": ["locked_state_ref", "locked_profile_state"],
            "violation_code": "MISSING_LOCKED_STATE_EVIDENCE",
            "rationale": "Browser and app cache candidates must prove the owning profile or process is not locked or running.",
        },
        {
            "id": "cache-readiness.identity-check",
            "required_evidence": ["identity_check_ref"],
            "violation_code": "MISSING_IDENTITY_CHECK_EVIDENCE",
            "rationale": "The reviewed path identity must match immediately before any recycle handoff.",
        },
        {
            "id": "cache-readiness.sensitive-exclusions",
            "required_evidence": ["sensitive_exclusions"],
            "violation_code": "MISSING_SENSITIVE_EXCLUSION_EVIDENCE",
            "rationale": "Cookies, passwords, sessions, tokens, wallets, profile databases, and user documents stay excluded.",
        },
        {
            "id": "cache-readiness.rule-quality",
            "required_evidence": ["rule_quality_gate"],
            "violation_code": "MISSING_RULE_QUALITY_GATE_EVIDENCE",
            "rationale": "Every cache candidate must carry rule quality evidence before promotion review.",
        },
        {
            "id": "cache-readiness.recycle-mode",
            "required_evidence": ["recycle_mode"],
            "violation_code": "RECYCLE_MODE_REQUIRED",
            "rationale": "Low-risk cache cleanup remains recycle-only; permanent delete is outside this path.",
        },
        {
            "id": "cache-readiness.confirmation-phrase",
            "required_evidence": ["confirmation_phrase"],
            "violation_code": "MISSING_CONFIRMATION_PHRASE_EVIDENCE",
            "rationale": "Human confirmation must be explicit and separate from report generation.",
        },
    ]
    return {
        "schema": LOW_RISK_CACHE_EXECUTION_READINESS_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "execution_enabled": False,
        "target_action": "browser-cache-delete",
        "source_refs": [
            "cleanwin.browser-profile-inventory.v1",
            "cleanwin.locked-state.v1",
            "cleanwin.rule-quality-dashboard.v1",
            "cleanwin.external-rule-quality-summary.v1",
            "cleanwin.promotion-gate-validation.v1",
        ],
        "required_evidence": CACHE_READINESS_REQUIRED_EVIDENCE,
        "required_tests": CACHE_READINESS_REQUIRED_TESTS,
        "controls": controls,
        "promotion_validator": {
            "gate_id": "browser-profile-to-cache-plan",
            "safe_to_execute": False,
            "violation_codes": CACHE_READINESS_VIOLATION_CODES,
        },
        "summary": {
            "required_evidence_count": len(CACHE_READINESS_REQUIRED_EVIDENCE),
            "required_test_count": len(CACHE_READINESS_REQUIRED_TESTS),
            "control_count": len(controls),
            "execution_enabled_count": 0,
        },
        "execution_gate": {
            "low_risk_cache_execution_enabled": False,
            "requires_promotion_validation": True,
            "requires_locked_state_ref": True,
            "requires_dry_run_token_ref": True,
            "requires_operation_log_ref": True,
            "requires_identity_check_ref": True,
            "requires_rule_quality_gate": True,
            "requires_recycle_mode": True,
            "requires_confirmation_phrase": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not execute cleanup.",
            "This report does not bypass validate-plan, policy simulation, dry-run token confirmation, or operation logging.",
            "This report does not enable registry, AppX, service, scheduled task, official-command, or permanent-delete execution.",
        ],
    }
