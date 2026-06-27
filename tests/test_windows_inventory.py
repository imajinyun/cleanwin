from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from cleanwincli.windows_inventory import WINDOWS_INVENTORY_SCHEMA, windows_inventory_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], list[Any]], None]
AssertAnyMatch = Callable[[list[JSONPayload], Callable[[JSONPayload], bool]], JSONPayload]
AssertAnyTextContains = Callable[[list[str], str], None]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]


def test_report_is_non_destructive_and_defaults_to_unexecuted_sources(
    assert_readonly_report: AssertReadonlyReport,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_match: AssertAnyMatch,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = windows_inventory_report()

    assert_readonly_report(report, WINDOWS_INVENTORY_SCHEMA)
    assert_summary_counts(report, {"section_count": 11, "available_section_count": 0})
    assert_any_match(report["sections"], lambda section: section["id"] == "component-store")
    assert_any_match(
        report["sections"],
        lambda section: section["source"]["reason"] == "external-command-not-executed",
    )
    assert_any_text_contains(report["non_goals"], "does not execute PowerShell")


def test_fixture_inventory_covers_windows_baseline_without_enabling_execution(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = windows_inventory_report(
        installed_apps=[{"display_name": "Slack", "publisher": "Slack Technologies LLC"}],
        appx_packages=[{"name": "Microsoft.WindowsTerminal", "publisher": "Microsoft"}],
        provisioned_appx_packages=[{"name": "Microsoft.ZuneMusic"}],
        windows_features=[{"name": "Microsoft-Hyper-V-All", "state": "Disabled"}],
        update_cache=[{"path": r"C:\Windows\SoftwareDistribution\Download", "estimated_bytes": 1024}],
        delivery_optimization=[{"cache_host": "localhost", "estimated_bytes": 2048}],
        defender_state=[{"antivirus_enabled": True, "signature_age_days": 1}],
        restore_points=[{"sequence_number": 42, "description": "Before cleanup"}],
        recycle_bin=[{"sid": "S-1-5-21-example", "estimated_bytes": 4096}],
        installer_cache=[{"path": r"C:\Windows\Installer", "estimated_bytes": 8192}],
        component_store=[{"recommended_cleanup": True, "estimated_reclaimable_bytes": 16384}],
    )

    section_ids = {section["id"] for section in report["sections"]}
    assert_contains_all(
        section_ids,
        [
            "installed-apps",
            "appx-packages",
            "provisioned-appx-packages",
            "windows-features",
            "windows-update-cache",
            "delivery-optimization",
            "defender-state",
            "restore-points",
            "recycle-bin",
            "installer-cache",
            "component-store",
        ],
    )
    for section in report["sections"]:
        assert_execution_disabled(section)
    assert_execution_disabled(report["promotion_gate"])
    assert_summary_counts(
        report,
        {
            "available_section_count": 11,
            "total_item_count": 11,
            "appx_package_count": 1,
            "provisioned_appx_package_count": 1,
            "windows_feature_count": 1,
            "executes_system_command_count": 0,
        },
    )


def test_cli_and_ai_provider_expose_windows_inventory(
    cleanwin_json: CleanWinJSON,
    assert_readonly_report: AssertReadonlyReport,
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    payload = cleanwin_json("windows-inventory")
    assert_readonly_report(payload, WINDOWS_INVENTORY_SCHEMA)
    assert_cli_provider_schema_sample("windows-inventory", WINDOWS_INVENTORY_SCHEMA)
