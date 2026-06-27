"""Versioned cleanup rule catalog loading and validation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_SCHEMA = "cleanwin.cleanup-rules.v1"
RULE_PACK_CATALOG_SCHEMA = "cleanwin.rule-pack-catalog.v1"
RULE_PACK_SCHEMA = "cleanwin.cleanup-rule-pack.v1"
RULE_QUALITY_SCORE_SCHEMA = "cleanwin.rule-quality-score.v1"
CATALOG_PATH = Path(__file__).with_name("rules") / "cleanup_rules.v1.json"

_SECTION_PACKS = {
    "dev_cache_rules": ("dev-cache", "Developer cache cleanup candidates"),
    "package_cache_rules": ("package-cache", "Package manager cache cleanup candidates"),
    "browser_cache_rules": ("browser-cache", "Browser cache cleanup candidates"),
    "browser_profile_cache_rules": ("browser-profile-cache", "Browser profile cache-layer cleanup candidates"),
    "app_leftover_rules": ("app-leftovers", "Application leftover cleanup candidates"),
}


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


def _rule_quality_score(rule: dict[str, Any], *, section: str) -> dict[str, Any]:
    default_path = str(rule.get("default") or "")
    active_markers = rule.get("active_markers")
    marker_count = len(active_markers) if isinstance(active_markers, list) else 0
    sensitive_exclusions = [
        "documents",
        "desktop",
        "downloads",
        "cookies",
        "login data",
        "sessions",
        "passwords",
        "extensions",
        "history",
    ]
    lowered_default = default_path.lower()
    excluded_matches = [item for item in sensitive_exclusions if item in lowered_default]
    has_owner = bool(str(rule.get("owner") or ""))
    has_official_command = bool(str(rule.get("official_cleanup_command") or ""))
    has_rationale = bool(str(rule.get("rationale") or ""))
    points = 0
    points += 20 if has_owner else 0
    points += 20 if has_official_command else 0
    points += 20 if has_rationale else 0
    points += 15 if default_path.startswith(("home:", "local:", "roaming:", "programdata:", "programfiles:")) else 0
    points += 15 if marker_count else 5 if section != "app_leftover_rules" else 0
    points += 10 if not excluded_matches else 0
    risk = "high" if excluded_matches else "medium" if section in {"app_leftover_rules", "browser_profile_cache_rules"} else "low"
    recoverability = "high" if any(token in lowered_default for token in ("cache", "logs", "crash", "temp")) else "medium"
    return {
        "schema": RULE_QUALITY_SCORE_SCHEMA,
        "score": min(points, 100),
        "risk": risk,
        "recoverability": recoverability,
        "owner_evidence": has_owner,
        "official_cleanup_evidence": has_official_command,
        "rationale_evidence": has_rationale,
        "active_install_marker_count": marker_count,
        "sensitive_exclusion_matches": excluded_matches,
        "test_coverage": "catalog-fixture",
        "provenance": "builtin",
        "review_status": "manual-reviewed",
    }


def _with_quality(rule: dict[str, Any], *, section: str) -> dict[str, Any]:
    enriched = dict(rule)
    enriched.setdefault("rule_pack", _SECTION_PACKS.get(section, (section, section))[0])
    enriched.setdefault("schema", "cleanwin.cleanup-rule.v1")
    enriched["quality_score"] = _rule_quality_score(enriched, section=section)
    return enriched


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
        rules.append(_with_quality(rule, section=section))
    return tuple(rules)


def _validate_profile_rule_map(payload: dict[str, Any], seen_rule_ids: set[str]) -> dict[str, dict[str, Any]]:
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
        rules[key] = _with_quality(rule, section=section)
    return rules


def _rule_list_for_pack(validated: dict[str, Any], section: str) -> list[dict[str, Any]]:
    value = validated[section]
    if isinstance(value, dict):
        return list(value.values())
    return list(value)


def _build_rule_packs(validated: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    packs: list[dict[str, Any]] = []
    for section, (pack_id, title) in _SECTION_PACKS.items():
        rules = _rule_list_for_pack(validated, section)
        quality_scores = [rule["quality_score"]["score"] for rule in rules if isinstance(rule.get("quality_score"), dict)]
        packs.append(
            {
                "schema": RULE_PACK_SCHEMA,
                "pack_id": pack_id,
                "title": title,
                "version": validated["version"],
                "source": "builtin",
                "review_status": "manual-reviewed",
                "rule_count": len(rules),
                "rule_ids": [str(rule["rule_id"]) for rule in rules],
                "quality": {
                    "schema": "cleanwin.rule-pack-quality-summary.v1",
                    "minimum_score": min(quality_scores) if quality_scores else 0,
                    "average_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0,
                    "high_risk_rule_count": sum(1 for rule in rules if rule.get("quality_score", {}).get("risk") == "high"),
                    "external_source_provenance": "builtin",
                },
            }
        )
    return tuple(packs)


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
    validated["rule_packs"] = _build_rule_packs(validated)
    validated["rule_pack_count"] = len(validated["rule_packs"])
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


def browser_profile_cache_rules() -> dict[str, dict[str, Any]]:
    value = cleanup_rule_catalog().get("browser_profile_cache_rules")
    if not isinstance(value, dict):
        raise RuleCatalogError("browser_profile_cache_rules is not a rule map")
    return value


def rule_pack_catalog_report() -> dict[str, Any]:
    catalog = cleanup_rule_catalog()
    packs = list(catalog["rule_packs"])
    return {
        "schema": RULE_PACK_CATALOG_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "catalog_schema": catalog["schema"],
        "version": catalog["version"],
        "packs": packs,
        "summary": {
            "pack_count": len(packs),
            "rule_count": catalog["rule_count"],
            "builtin_pack_count": sum(1 for pack in packs if pack["source"] == "builtin"),
            "manual_reviewed_pack_count": sum(1 for pack in packs if pack["review_status"] == "manual-reviewed"),
            "execution_enabled_count": 0,
        },
        "promotion_gate": {
            "external_rule_import_enabled": False,
            "requires_schema_validation": True,
            "requires_owner_review": True,
            "requires_quality_score": True,
            "requires_sensitive_exclusion_scan": True,
        },
        "non_goals": [
            "This report does not import external rule packs.",
            "This report does not execute cleanup rules.",
            "This report does not promote translated external candidates into builtin packs.",
        ],
    }
