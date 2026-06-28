"""Human-readable CLI output helpers."""

from __future__ import annotations

from typing import Any


def render_progress_bar(*, complete: bool, width: int = 48) -> str:
    percent = 100 if complete else 0
    filled = width if complete else 0
    empty = width - filled
    return f"[{'=' * filled}{'.' * empty}] {percent:>3}%"


def render_human_payload(payload: dict[str, Any]) -> str:
    schema = str(payload.get("schema") or "cleanwin.report")
    status = _payload_status(payload)
    lines = [
        f"CleanWin :: {schema}",
        f"| status   {status}",
        f"| progress {render_progress_bar(complete=status != 'failed')}",
    ]
    summary = _summary_line(payload)
    if summary:
        lines.append(f"| summary  {summary}")
    if payload.get("error"):
        lines.append(f"| error    {payload['error']}")
    lines.append("`- json     rerun with --json for machine-readable output")
    return "\n".join(lines)


def _payload_status(payload: dict[str, Any]) -> str:
    if payload.get("error"):
        return "failed"
    for field in ("valid", "ready", "passed", "allowed", "ready_for_ai_host"):
        if field in payload:
            return "ok" if payload[field] is True else "blocked"
    validation = payload.get("validation")
    if isinstance(validation, dict) and "valid" in validation:
        return "ok" if validation["valid"] is True else "blocked"
    return "ok"


def _summary_line(payload: dict[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        parts = [f"{key}={value}" for key, value in sorted(summary.items()) if isinstance(value, str | int | float | bool)]
        return ", ".join(parts[:8])
    count_fields = [
        "candidate_count",
        "finding_count",
        "contract_count",
        "plan_count",
        "error_count",
    ]
    parts = [f"{field}={payload[field]}" for field in count_fields if field in payload]
    return ", ".join(parts)
