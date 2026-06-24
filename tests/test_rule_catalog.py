from __future__ import annotations

import pytest

from cleanwincli.rule_catalog import CATALOG_SCHEMA, RuleCatalogError, cleanup_rule_catalog


def test_cleanup_rule_catalog_loads_versioned_rules() -> None:
    catalog = cleanup_rule_catalog()

    assert catalog["schema"] == CATALOG_SCHEMA
    assert catalog["version"] == "1"
    assert catalog["rule_count"] >= 40
    assert any(rule["rule_id"] == "dev-cache.npm.cache" for rule in catalog["dev_cache_rules"])
    assert any(rule["rule_id"] == "dev-cache.poetry.cache" for rule in catalog["dev_cache_rules"])
    assert any(rule["rule_id"] == "app-leftovers.vscode.cached-data" for rule in catalog["app_leftover_rules"])


def test_cleanup_rule_catalog_expanded_rules_stay_low_risk_and_reviewable() -> None:
    catalog = cleanup_rule_catalog()
    rules = [
        *catalog["dev_cache_rules"],
        *catalog["package_cache_rules"],
        *catalog["browser_cache_rules"],
        *catalog["app_leftover_rules"],
        *catalog["browser_profile_cache_rules"].values(),
    ]
    by_rule = {rule["rule_id"]: rule for rule in rules}

    for rule_id in (
        "dev-cache.poetry.cache",
        "dev-cache.pipenv.cache",
        "dev-cache.pre-commit.cache",
        "dev-cache.node-gyp.cache",
        "app-leftovers.teams-classic.gpu-cache",
        "app-leftovers.discord.gpu-cache",
        "app-leftovers.vscode.gpu-cache",
    ):
        rule = by_rule[rule_id]
        assert rule["official_cleanup_command"]
        assert "regenerated" in rule["rationale"].lower() or "recreated" in rule["rationale"].lower()

    unsafe_segments = {"documents", "desktop", "cookies", "login data", "sessions", "extensions", "history"}
    for rule in rules:
        default_segments = {segment.strip().lower() for segment in str(rule.get("default", "")).replace("\\", "/").split("/")}
        assert not (default_segments & unsafe_segments), rule["rule_id"]


def test_cleanup_rule_catalog_rule_ids_are_unique() -> None:
    catalog = cleanup_rule_catalog()
    rule_ids: list[str] = []
    for section in ("dev_cache_rules", "package_cache_rules", "browser_cache_rules", "app_leftover_rules"):
        rule_ids.extend(rule["rule_id"] for rule in catalog[section])
    rule_ids.extend(rule["rule_id"] for rule in catalog["browser_profile_cache_rules"].values())

    assert len(rule_ids) == len(set(rule_ids))


def test_cleanup_rule_catalog_rejects_duplicate_rule_ids() -> None:
    from cleanwincli.rule_catalog import _validate_catalog

    payload = {
        "schema": CATALOG_SCHEMA,
        "version": "1",
        "dev_cache_rules": [
            {
                "rule_id": "duplicate.rule",
                "owner": "one",
                "env_key": "ONE_CACHE",
                "default": "local:one",
                "official_cleanup_command": "one clean",
                "rationale": "one",
            }
        ],
        "package_cache_rules": [
            {
                "rule_id": "duplicate.rule",
                "owner": "two",
                "default": "local:two",
                "official_cleanup_command": "two clean",
                "rationale": "two",
            }
        ],
        "browser_cache_rules": [],
        "browser_profile_cache_rules": {},
        "app_leftover_rules": [],
    }

    with pytest.raises(RuleCatalogError):
        _validate_catalog(payload)
