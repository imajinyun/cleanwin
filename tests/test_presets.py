from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.presets import PRESET_CATALOG_SCHEMA, preset_catalog_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[list[str]], dict[str, JSONPayload]]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyPayload = Callable[[JSONPayload], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]


def test_preset_catalog_is_read_only_and_non_executable(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    report = preset_catalog_report()

    assert_readonly_report(report, PRESET_CATALOG_SCHEMA)
    assert_execution_disabled(report["execution_gate"], "preset_execution_enabled", "ai_auto_call_allowed")
    assert_summary_counts(report, {"execution_enabled_count": 0})
    for preset in report["presets"]:
        assert_execution_disabled(preset["plan_template"])


def test_preset_catalog_contains_safe_templates_and_review_gates(
    assert_payload_schema: AssertPayloadSchema,
    assert_readonly_payload: AssertReadonlyPayload,
) -> None:
    report = preset_catalog_report()
    by_id = {preset["id"]: preset for preset in report["presets"]}

    assert "preset.daily-safe-cache" in by_id
    assert "preset.browser-cache-only" in by_id
    assert "preset.uninstalled-app-leftovers" in by_id
    browser = by_id["preset.browser-cache-only"]
    assert browser["categories"] == ["browser-cache"]
    assert "browser-cache.chrome.cache" in browser["rule_ids"]
    assert_payload_schema(browser["plan_template"], "cleanwin.preset-plan-template.v1")
    assert_readonly_payload(browser["plan_template"])
    assert browser["plan_template"]["requires_validate_plan"] is True
    assert browser["plan_template"]["requires_matching_dry_run_token"] is True
    assert any("cookies" in step.lower() for step in browser["review_steps"])


def test_cli_provider_and_schema_registry_expose_preset_catalog(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    assert_cli_provider_schema_sample("preset-catalog", PRESET_CATALOG_SCHEMA)
    assert_schema_samples(["cleanwin.preset-plan-template.v1"])
