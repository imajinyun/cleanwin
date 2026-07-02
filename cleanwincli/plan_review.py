"""CleanWin plan review — assess plan safety and produce execution handoff metadata."""

from __future__ import annotations

from typing import Any

from cleanwincli.ai_schema import CONFIRMATION_PHRASE
from cleanwincli.models import (
    CATEGORY_BROWSER_CACHE,
    EXECUTABLE_CACHE_CATEGORIES,
    Plan,
)


def review_plan(plan: Plan, raw_payload: dict[str, Any], *, require_context: bool) -> dict[str, Any]:
    from cleanwincli.core import capabilities, validate_plan_payload

    validation = validate_plan_payload(plan, raw_payload, require_context=require_context)
    candidates = list(plan.candidates)
    unique_rule_ids = sorted({candidate.rule_id for candidate in candidates if candidate.rule_id})
    official_cleanup_commands = sorted({candidate.official_cleanup_command for candidate in candidates if candidate.official_cleanup_command})
    category_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    rule_summary: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        category_counts[candidate.category] = category_counts.get(candidate.category, 0) + 1
        risk_counts[candidate.risk] = risk_counts.get(candidate.risk, 0) + 1
        if candidate.rule_id:
            entry = rule_summary.setdefault(
                candidate.rule_id,
                {
                    "rule_id": candidate.rule_id,
                    "cache_owner": candidate.cache_owner,
                    "candidate_count": 0,
                    "bytes_reclaimable": 0,
                    "official_cleanup_command": candidate.official_cleanup_command,
                },
            )
            entry["candidate_count"] += 1
            entry["bytes_reclaimable"] += candidate.size_bytes
    grouped_risks = [
        {"risk": risk, "candidate_count": count}
        for risk, count in sorted(risk_counts.items())
    ]
    read_only_categories = set(capabilities().get("read_only_categories", []))
    manual_only_categories = sorted(category for category in plan.categories if category in read_only_categories)
    candidate_categories = {candidate.category for candidate in candidates}
    strategy_cleanup_commands = set(official_cleanup_commands)
    browser_tool_commands = {
        "Google Chrome": "Use Chrome > Clear browsing data",
        "Microsoft Edge": "Use Edge > Clear browsing data",
        "Mozilla Firefox": "Use Firefox > Clear recent history",
    }
    for candidate in candidates:
        if candidate.category == CATEGORY_BROWSER_CACHE and candidate.cache_owner in browser_tool_commands:
            strategy_cleanup_commands.add(browser_tool_commands[candidate.cache_owner])
    cleanup_strategy = {
        "preferred": "official-tool-or-app-ui" if CATEGORY_BROWSER_CACHE in candidate_categories else "official-cli-command",
        "fallback": "cleanwin-recycle-execution",
        "requires_review": True,
        "official_cleanup_commands": sorted(strategy_cleanup_commands),
    }
    sensitive_exclusions = []
    if any(candidate.category == CATEGORY_BROWSER_CACHE for candidate in candidates):
        sensitive_exclusions.append(
            {
                "category": CATEGORY_BROWSER_CACHE,
                "reason": "Only browser cache directories are planned; profile databases, cookies, sessions, passwords, extensions, and sync state remain excluded.",
                "excluded_patterns": [
                    {"pattern": "Cookies", "risk": "authentication sessions and site state"},
                    {"pattern": "Login Data", "risk": "saved credentials database"},
                    {"pattern": "Local State", "risk": "browser profile and encryption metadata"},
                    {"pattern": "Sessions", "risk": "open tab and browser session state"},
                    {"pattern": "Extensions", "risk": "installed extension state and settings"},
                    {"pattern": "Firefox profile root", "risk": "mixed cookies, history, extension, and account data"},
                ],
            }
        )
    execution_handoff = {
        "safe_to_execute": bool(validation["valid"] and all(candidate.delete_mode == "recycle" and not candidate.requires_admin for candidate in candidates)),
        "execution_profile": "controlled-low-risk-cache-recycle",
        "allowed_candidate_categories": sorted(EXECUTABLE_CACHE_CATEGORIES),
        "allowed_delete_modes": ["recycle"],
        "required_readiness_schema": "cleanwin.low-risk-cache-execution-readiness.v1",
        "required_readiness_validation_schema": "cleanwin.low-risk-cache-readiness-validation.v1",
        "required_operation_log_readiness_schema": "cleanwin.operation-log-readiness.v1",
        "required_operation_log_readiness_validation_schema": "cleanwin.operation-log-readiness-validation.v1",
        "readiness_command": ["cleanwin", "--json", "low-risk-cache-readiness"],
        "operation_log_readiness_command": ["cleanwin", "--json", "operation-log-readiness"],
        "required_evidence_refs": [
            "dry_run_token_ref",
            "operation_log_ref",
            "operation_log_readiness_ref",
            "locked_state_ref",
            "identity_check_ref",
            "sensitive_exclusions",
            "rule_quality_gate",
            "recycle_mode",
            "confirmation_phrase",
        ],
        "requires_recycle_mode": True,
        "requires_human_confirmation": True,
        "requires_matching_dry_run_token": True,
        "requires_operation_log": True,
        "requires_operation_log_readiness": True,
        "requires_identity_match": True,
        "requires_regeneration_rationale": True,
        "requires_plan_context": require_context,
        "requires_confirmation_phrase": CONFIRMATION_PHRASE,
        "forbidden_actions": [
            "permanent-delete",
            "registry-mutation",
            "appx-removal",
            "service-disable",
            "scheduled-task-disable",
            "process-kill",
        ],
        "required_predecessor_tools": [
            "cleanwin_validate_plan",
            "cleanwin_policy_simulate",
            "cleanwin_dry_run_plan",
            "cleanwin_execute_plan",
        ],
        "blocked_reasons": list(validation["errors"]),
    }
    return {
        "schema": "cleanwin.review.v1",
        "destructive": False,
        "plan_schema": plan.schema,
        "plan_source_fingerprint": raw_payload.get("source_fingerprint"),
        "validation": validation,
        "summary": {
            "candidate_count": len(candidates),
            "bytes_reclaimable": sum(candidate.size_bytes for candidate in candidates if candidate.safe_to_delete),
            "safe_candidate_count": sum(1 for candidate in candidates if candidate.safe_to_delete),
        },
        "category_counts": [{"category": category, "candidate_count": count} for category, count in sorted(category_counts.items())],
        "risk_summary": grouped_risks,
        "rule_ids": unique_rule_ids,
        "rule_summary": [rule_summary[key] for key in sorted(rule_summary)],
        "official_cleanup_commands": official_cleanup_commands,
        "cleanup_strategy": cleanup_strategy,
        "manual_only_categories": manual_only_categories,
        "sensitive_exclusions": sensitive_exclusions,
        "execution_handoff": execution_handoff,
    }
