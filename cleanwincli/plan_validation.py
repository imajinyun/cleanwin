"""CleanWin plan validation — schema negotiation, identity verification, and safety gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cleanwincli.ai_versioning import negotiate_plan_schema
from cleanwincli.identity import capture_filesystem_identity, compare_identity
from cleanwincli.models import EXECUTABLE_CACHE_CATEGORIES, PLAN_SCHEMA, HostContext, Plan
from cleanwincli.protection import validate_filesystem_candidate


def validate_plan_payload(plan: Plan, raw: dict[str, Any], *, require_context: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    negotiation = negotiate_plan_schema(str(raw.get("schema") or ""))
    if raw.get("schema") != PLAN_SCHEMA:
        errors.append(f"Unsupported plan schema: {raw.get('schema')}")
    expected_fingerprint = plan.source_fingerprint()
    if raw.get("source_fingerprint") != expected_fingerprint:
        errors.append("Plan source_fingerprint does not match current payload")
    if require_context:
        current = HostContext.current()
        raw_context = plan.context
        if raw_context.home and raw_context.home != current.home:
            errors.append("Plan home context does not match current user home")
        if raw_context.user and raw_context.user != current.user:
            errors.append("Plan user context does not match current user")
    for candidate in plan.candidates:
        if not candidate.safe_to_delete:
            errors.append(f"Candidate is not marked safe_to_delete: {candidate.path}")
            continue
        if candidate.delete_mode != "recycle":
            errors.append(f"Unsupported plan delete_mode for MVP: {candidate.path} uses {candidate.delete_mode}")
            continue
        if candidate.requires_admin:
            errors.append(f"Admin-scoped candidate is not executable in MVP: {candidate.path}")
            continue
        if candidate.category not in EXECUTABLE_CACHE_CATEGORIES:
            errors.append(
                f"Category is not enabled for controlled low-risk cache execution: {candidate.path} uses {candidate.category}"
            )
            continue
        if candidate.risk != "low":
            errors.append(f"Only low-risk cache candidates are executable in MVP: {candidate.path} uses {candidate.risk}")
            continue
        if not candidate.safe_to_delete_rationale:
            errors.append(f"Low-risk cache execution requires a regeneration rationale: {candidate.path}")
            continue
        try:
            candidate_path = Path(candidate.path)
            validate_filesystem_candidate(candidate_path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        current_identity = capture_filesystem_identity(candidate_path)
        identity_mismatches = compare_identity(candidate.identity, current_identity)
        if identity_mismatches:
            errors.append(f"Filesystem identity mismatch for {candidate.path}: {'; '.join(identity_mismatches)}")
    return {
        "schema": "cleanwin.validate-plan.v1",
        "valid": not errors,
        "errors": errors,
        "candidate_count": len(plan.candidates),
        "plan_schema": negotiation,
    }


def confirmation_token_for_plan(plan: Plan, raw_payload: dict[str, Any]) -> str:
    fingerprint = str(raw_payload.get("source_fingerprint") or plan.source_fingerprint())
    token_context = {
        "schema": "cleanwin.ai-confirmation-token-context.v1",
        "plan_fingerprint": fingerprint,
        "delete_mode": "recycle",
        "candidate_count": len(plan.candidates),
        "categories": plan.categories,
    }
    encoded = json.dumps(token_context, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
