from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.ai_versioning import schema_registry, schema_sample
from cleanwincli.presets import PRESET_CATALOG_SCHEMA, preset_catalog_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def require_schema_sample(name: str) -> JSONPayload:
    sample = schema_sample(name)
    if sample is None:
        raise AssertionError(f"missing schema sample: {name}")
    return sample


def test_preset_catalog_is_read_only_and_non_executable() -> None:
    report = preset_catalog_report()

    assert report["schema"] == PRESET_CATALOG_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["execution_gate"]["preset_execution_enabled"] is False
    assert report["execution_gate"]["ai_auto_call_allowed"] is False
    assert report["summary"]["execution_enabled_count"] == 0
    assert all(not preset["plan_template"]["execution_enabled"] for preset in report["presets"])


def test_preset_catalog_contains_safe_templates_and_review_gates() -> None:
    report = preset_catalog_report()
    by_id = {preset["id"]: preset for preset in report["presets"]}

    assert "preset.daily-safe-cache" in by_id
    assert "preset.browser-cache-only" in by_id
    assert "preset.uninstalled-app-leftovers" in by_id
    browser = by_id["preset.browser-cache-only"]
    assert browser["categories"] == ["browser-cache"]
    assert "browser-cache.chrome.cache" in browser["rule_ids"]
    assert browser["plan_template"]["schema"] == "cleanwin.preset-plan-template.v1"
    assert browser["plan_template"]["destructive"] is False
    assert browser["plan_template"]["requires_validate_plan"] is True
    assert browser["plan_template"]["requires_matching_dry_run_token"] is True
    assert any("cookies" in step.lower() for step in browser["review_steps"])


def test_cli_provider_and_schema_registry_expose_preset_catalog(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("preset-catalog")
    assert cli["schema"] == PRESET_CATALOG_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "preset-catalog")
    assert provider["schema"] == PRESET_CATALOG_SCHEMA

    registry = schema_registry()
    names = {entry["name"] for entry in registry["entries"]}
    assert PRESET_CATALOG_SCHEMA in names
    assert "cleanwin.preset-plan-template.v1" in names
    assert require_schema_sample(PRESET_CATALOG_SCHEMA)["schema"] == PRESET_CATALOG_SCHEMA
    assert require_schema_sample("cleanwin.preset-plan-template.v1")["schema"] == "cleanwin.preset-plan-template.v1"
