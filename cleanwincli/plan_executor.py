"""CleanWin plan execution — dry-run and real cleanup execution with safety gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cleanwincli.ai_schema import CONFIRMATION_PHRASE
from cleanwincli.delete_ops import safe_delete
from cleanwincli.models import Plan


def execution_result_summary(results: list[dict[str, str]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {"result_count": len(results), "status_counts": dict(sorted(status_counts.items()))}


def execute_plan(
    plan: Plan,
    *,
    execute: bool,
    yes: bool,
    require_context: bool,
    raw_payload: dict[str, Any],
    operation_log: Path | None,
    trash_root: Path | None,
    confirmation_phrase: str | None = None,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    from cleanwincli.core import confirmation_token_for_plan, validate_plan_payload

    validation = validate_plan_payload(plan, raw_payload, require_context=require_context)
    if not validation["valid"]:
        return {"schema": "cleanwin.execute.v1", "executed": False, "validation": validation, "results": []}
    if not execute:
        results = [
            safe_delete(
                candidate.path,
                dry_run=True,
                mode=candidate.delete_mode,
                allow_permanent=False,
                trash_root=trash_root,
                operation_log=None,
                expected_identity=candidate.identity,
            )
            for candidate in plan.candidates
        ]
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "dry_run": True,
            "validation": validation,
            "results": results,
            "summary": execution_result_summary(results),
            "confirmation": {
                "schema": "cleanwin.ai-confirmation-summary.v1",
                "required_phrase": CONFIRMATION_PHRASE,
                "confirmation_token": confirmation_token_for_plan(plan, raw_payload),
                "delete_mode": "recycle",
            },
        }
    if not yes:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires --yes",
        }
    if operation_log is None:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires --operation-log",
        }
    if confirmation_phrase != CONFIRMATION_PHRASE:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires exact confirmation phrase",
        }
    expected_token = confirmation_token_for_plan(plan, raw_payload)
    if confirmation_token != expected_token:
        return {
            "schema": "cleanwin.execute.v1",
            "executed": False,
            "validation": validation,
            "results": [],
            "error": "Execution requires matching dry-run confirmation token",
        }
    results = []
    for candidate in plan.candidates:
        results.append(
            safe_delete(
                candidate.path,
                dry_run=False,
                mode=candidate.delete_mode,
                allow_permanent=False,
                trash_root=trash_root,
                operation_log=operation_log,
                expected_identity=candidate.identity,
            )
        )
    return {"schema": "cleanwin.execute.v1", "executed": True, "validation": validation, "results": results, "summary": execution_result_summary(results)}
