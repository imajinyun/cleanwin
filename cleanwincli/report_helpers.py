"""Shared report helpers used across inventory and validation modules."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from typing import Any


def get_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Resolve environment variables, defaulting to os.environ."""
    if env is None:
        return dict(os.environ)
    return dict(env)


def source_status(
    source_id: str,
    *,
    available: bool,
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a source-status entry for inventory reports."""
    return {"id": source_id, "available": available, "reason": reason, "evidence": evidence or {}}


def values_from_mapping(payload: Mapping[str, Any], key: str) -> set[str]:
    """Extract a set of string values from a mapping field.

    Accepts either a mapping (uses keys) or an iterable (uses items).
    """
    value = payload.get(key)
    if isinstance(value, Mapping):
        return {str(item) for item in value.keys()}
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return {str(item) for item in value}
    return set()


def quality_gate_from_payload(
    source_report: Mapping[str, Any],
    proposed_action: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Extract a quality_gate mapping from a report or proposed action.

    Search order:
    1. proposed_action.quality_gate
    2. source_report.quality_gate
    3. first candidate.quality_gate in source_report.candidates
    4. first item.quality_gate in source_report.review_queue
    5. empty dict
    """
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
