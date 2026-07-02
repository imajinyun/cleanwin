"""Plan I/O: inspect, build_plan, load_plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cleanwincli.collectors import collect_candidates, collect_findings
from cleanwincli.models import Plan, plan_from_dict


def inspect(
    categories: list[str],
    *,
    older_than_days: int,
    max_items: int,
    rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    candidates = collect_candidates(
        categories,
        older_than_days_value=older_than_days,
        max_items=max_items,
        rule_ids=rule_ids,
    )
    findings = collect_findings(categories, rule_ids=rule_ids)
    return {
        "schema": "cleanwin.inspect.v1",
        "categories": categories,
        "filters": {"rule_ids": rule_ids or []},
        "candidates": [candidate.to_dict() for candidate in candidates],
        "findings": [finding.to_dict() for finding in findings],
        "summary": {
            "candidate_count": len(candidates),
            "finding_count": len(findings),
            "bytes_reclaimable": sum(
                candidate.size_bytes for candidate in candidates if candidate.safe_to_delete
            ),
        },
    }


def build_plan(
    categories: list[str],
    *,
    older_than_days: int,
    max_items: int,
    rule_ids: list[str] | None = None,
) -> Plan:
    candidates = collect_candidates(
        categories,
        older_than_days_value=older_than_days,
        max_items=max_items,
        rule_ids=rule_ids,
    )
    return Plan(candidates=candidates, categories=categories)


def load_plan(path: Path) -> tuple[Plan, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    plan = plan_from_dict(raw)
    return plan, raw
