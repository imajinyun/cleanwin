from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

import pytest

from cleanwincli.rule_catalog import CATALOG_SCHEMA, RuleCatalogError, cleanup_rule_catalog

JSONPayload = dict[str, Any]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


@pytest.fixture
def rule_catalog() -> dict[str, Any]:
    return cleanup_rule_catalog()


def catalog_rules(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *catalog["dev_cache_rules"],
        *catalog["package_cache_rules"],
        *catalog["browser_cache_rules"],
        *catalog["app_leftover_rules"],
        *catalog["browser_profile_cache_rules"].values(),
    ]


def test_cleanup_rule_catalog_loads_versioned_rules(
    rule_catalog: dict[str, Any],
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    catalog = rule_catalog

    assert_payload_schema(catalog, CATALOG_SCHEMA)
    assert_field_values(catalog, {"version": "1"})
    assert catalog["rule_count"] >= 40
    assert_contains_all(
        {rule["rule_id"] for rule in catalog["dev_cache_rules"]},
        ["dev-cache.npm.cache", "dev-cache.poetry.cache"],
    )
    assert_contains_all(
        {rule["rule_id"] for rule in catalog["app_leftover_rules"]},
        ["app-leftovers.vscode.cached-data"],
    )


@pytest.mark.parametrize(
    "rule_id",
    [
        "dev-cache.poetry.cache",
        "dev-cache.pipenv.cache",
        "dev-cache.pre-commit.cache",
        "dev-cache.node-gyp.cache",
        "app-leftovers.teams-classic.gpu-cache",
        "app-leftovers.discord.gpu-cache",
        "app-leftovers.vscode.gpu-cache",
    ],
)
def test_cleanup_rule_catalog_regenerated_rules_have_reviewable_rationale(
    rule_id: str,
    rule_catalog: dict[str, Any],
) -> None:
    rule = {rule["rule_id"]: rule for rule in catalog_rules(rule_catalog)}[rule_id]
    assert rule["official_cleanup_command"]
    assert "regenerated" in rule["rationale"].lower() or "recreated" in rule["rationale"].lower()


def test_cleanup_rule_catalog_expanded_rules_avoid_unsafe_default_segments(rule_catalog: dict[str, Any]) -> None:
    rules = catalog_rules(rule_catalog)
    unsafe_segments = {"documents", "desktop", "cookies", "login data", "sessions", "extensions", "history"}
    for rule in rules:
        default_segments = {segment.strip().lower() for segment in str(rule.get("default", "")).replace("\\", "/").split("/")}
        assert not (default_segments & unsafe_segments), rule["rule_id"]


def test_cleanup_rule_catalog_rule_ids_are_unique(rule_catalog: dict[str, Any]) -> None:
    catalog = rule_catalog
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

    with pytest.raises(RuleCatalogError, match="duplicate cleanup rule_id"):
        _validate_catalog(payload)
