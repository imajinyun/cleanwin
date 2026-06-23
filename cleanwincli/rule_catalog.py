"""Versioned cleanup rule catalog loading and validation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_SCHEMA = "cleanwin.cleanup-rules.v1"
CATALOG_PATH = Path(__file__).with_name("rules") / "cleanup_rules.v1.json"


class RuleCatalogError(RuntimeError):
    """Raised when the cleanup rule catalog is missing or invalid."""


def _require_string(rule: dict[str, Any], field: str, *, section: str, rule_id: str) -> None:
    value = rule.get(field)
    if not isinstance(value, str) or not value:
        raise RuleCatalogError(f"{section} rule {rule_id} must define non-empty string field {field}")


def _validate_rule(rule: dict[str, Any], *, section: str, required_fields: tuple[str, ...]) -> str:
    rule_id = str(rule.get("rule_id") or "")
    if not rule_id:
        raise RuleCatalogError(f"{section} rule must define rule_id")
    for field in required_fields:
        _require_string(rule, field, section=section, rule_id=rule_id)
    active_markers = rule.get("active_markers")
    if active_markers is not None and (
        not isinstance(active_markers, list) or not all(isinstance(marker, str) and marker for marker in active_markers)
    ):
        raise RuleCatalogError(f"{section} rule {rule_id} active_markers must be a list of non-empty strings")
    return rule_id


def _validate_rule_list(
    payload: dict[str, Any],
    section: str,
    *,
    required_fields: tuple[str, ...],
    seen_rule_ids: set[str],
) -> tuple[dict[str, Any], ...]:
    raw_rules = payload.get(section)
    if not isinstance(raw_rules, list):
        raise RuleCatalogError(f"{section} must be a list")
    rules: list[dict[str, Any]] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise RuleCatalogError(f"{section} entries must be objects")
        rule = dict(raw_rule)
        rule_id = _validate_rule(rule, section=section, required_fields=required_fields)
        if rule_id in seen_rule_ids:
            raise RuleCatalogError(f"duplicate cleanup rule_id: {rule_id}")
        seen_rule_ids.add(rule_id)
        rules.append(rule)
    return tuple(rules)


def _validate_profile_rule_map(payload: dict[str, Any], seen_rule_ids: set[str]) -> dict[str, dict[str, str]]:
    section = "browser_profile_cache_rules"
    raw_rules = payload.get(section)
    if not isinstance(raw_rules, dict):
        raise RuleCatalogError(f"{section} must be an object")
    rules: dict[str, dict[str, str]] = {}
    for key, raw_rule in raw_rules.items():
        if not isinstance(key, str) or not key:
            raise RuleCatalogError(f"{section} keys must be non-empty strings")
        if not isinstance(raw_rule, dict):
            raise RuleCatalogError(f"{section}.{key} must be an object")
        rule = {str(field): str(value) for field, value in raw_rule.items()}
        rule_id = _validate_rule(
            rule,
            section=f"{section}.{key}",
            required_fields=("rule_id", "owner", "official_cleanup_command", "rationale"),
        )
        if rule_id in seen_rule_ids:
            raise RuleCatalogError(f"duplicate cleanup rule_id: {rule_id}")
        seen_rule_ids.add(rule_id)
        rules[key] = rule
    return rules


def _validate_catalog(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuleCatalogError("cleanup rule catalog must be a JSON object")
    if payload.get("schema") != CATALOG_SCHEMA:
        raise RuleCatalogError(f"cleanup rule catalog schema must be {CATALOG_SCHEMA}")
    seen_rule_ids: set[str] = set()
    validated = {
        "schema": payload["schema"],
        "version": str(payload.get("version") or "1"),
        "dev_cache_rules": _validate_rule_list(
            payload,
            "dev_cache_rules",
            required_fields=("rule_id", "owner", "env_key", "default", "official_cleanup_command", "rationale"),
            seen_rule_ids=seen_rule_ids,
        ),
        "package_cache_rules": _validate_rule_list(
            payload,
            "package_cache_rules",
            required_fields=("rule_id", "owner", "default", "official_cleanup_command", "rationale"),
            seen_rule_ids=seen_rule_ids,
        ),
        "browser_cache_rules": _validate_rule_list(
            payload,
            "browser_cache_rules",
            required_fields=("rule_id", "owner", "default", "official_cleanup_command", "rationale"),
            seen_rule_ids=seen_rule_ids,
        ),
        "browser_profile_cache_rules": _validate_profile_rule_map(payload, seen_rule_ids),
        "app_leftover_rules": _validate_rule_list(
            payload,
            "app_leftover_rules",
            required_fields=("rule_id", "owner", "default", "official_cleanup_command", "rationale"),
            seen_rule_ids=seen_rule_ids,
        ),
    }
    validated["rule_count"] = len(seen_rule_ids)
    return validated


@lru_cache(maxsize=1)
def cleanup_rule_catalog() -> dict[str, Any]:
    try:
        raw = CATALOG_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuleCatalogError(f"failed to read cleanup rule catalog: {CATALOG_PATH}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuleCatalogError(f"failed to parse cleanup rule catalog: {CATALOG_PATH}") from exc
    return _validate_catalog(payload)


def catalog_rules(section: str) -> tuple[dict[str, Any], ...]:
    value = cleanup_rule_catalog().get(section)
    if not isinstance(value, tuple):
        raise RuleCatalogError(f"{section} is not a rule list")
    return value


def browser_profile_cache_rules() -> dict[str, dict[str, str]]:
    value = cleanup_rule_catalog().get("browser_profile_cache_rules")
    if not isinstance(value, dict):
        raise RuleCatalogError("browser_profile_cache_rules is not a rule map")
    return value
