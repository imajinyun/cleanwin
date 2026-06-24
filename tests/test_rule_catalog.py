from __future__ import annotations

import pytest

from cleanwincli.rule_catalog import CATALOG_SCHEMA, RuleCatalogError, cleanup_rule_catalog


def test_cleanup_rule_catalog_loads_versioned_rules() -> None:
    catalog = cleanup_rule_catalog()

    assert catalog["schema"] == CATALOG_SCHEMA
    assert catalog["version"] == "1"
    assert catalog["rule_count"] >= 20
    assert any(rule["rule_id"] == "dev-cache.npm.cache" for rule in catalog["dev_cache_rules"])
    assert any(rule["rule_id"] == "app-leftovers.vscode.cached-data" for rule in catalog["app_leftover_rules"])


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
