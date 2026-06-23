from __future__ import annotations

import unittest

from cleanwincli.rule_catalog import CATALOG_SCHEMA, RuleCatalogError, cleanup_rule_catalog


class RuleCatalogTests(unittest.TestCase):
    def test_cleanup_rule_catalog_loads_versioned_rules(self) -> None:
        catalog = cleanup_rule_catalog()

        self.assertEqual(catalog["schema"], CATALOG_SCHEMA)
        self.assertEqual(catalog["version"], "1")
        self.assertGreaterEqual(catalog["rule_count"], 20)
        self.assertTrue(any(rule["rule_id"] == "dev-cache.npm.cache" for rule in catalog["dev_cache_rules"]))
        self.assertTrue(any(rule["rule_id"] == "app-leftovers.vscode.cached-data" for rule in catalog["app_leftover_rules"]))

    def test_cleanup_rule_catalog_rule_ids_are_unique(self) -> None:
        catalog = cleanup_rule_catalog()
        rule_ids: list[str] = []
        for section in ("dev_cache_rules", "package_cache_rules", "browser_cache_rules", "app_leftover_rules"):
            rule_ids.extend(rule["rule_id"] for rule in catalog[section])
        rule_ids.extend(rule["rule_id"] for rule in catalog["browser_profile_cache_rules"].values())

        self.assertEqual(len(rule_ids), len(set(rule_ids)))

    def test_cleanup_rule_catalog_rejects_duplicate_rule_ids(self) -> None:
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

        with self.assertRaises(RuleCatalogError):
            _validate_catalog(payload)
