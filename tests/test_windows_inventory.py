from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from cleanwincli.windows_inventory import (
    APPX_PACKAGE_SNAPSHOT_SCHEMA,
    PROVISIONED_APPX_PACKAGE_SNAPSHOT_SCHEMA,
    WINDOWS_INVENTORY_SCHEMA,
    appx_snapshot_artifact_contract,
    windows_inventory_report,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], list[Any]], None]
AssertAnyMatch = Callable[[list[JSONPayload], Callable[[JSONPayload], bool]], JSONPayload]
AssertAnyTextContains = Callable[[list[str], str], None]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]


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
    assert_summary_counts(report, {"collection_plan_count": 11, "requires_admin_collection_count": 7})


def test_fixture_inventory_covers_windows_baseline_without_enabling_execution(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = windows_inventory_report(
        installed_apps=[{"display_name": "Slack", "publisher": "Slack Technologies LLC"}],
        appx_packages=[{"name": "Microsoft.XboxGamingOverlay", "publisher": "Microsoft"}],
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
            "collection_plan_count": 11,
            "appx_classification_count": 2,
            "appx_manual_review_count": 2,
            "provisioned_appx_future_user_impact_count": 1,
        },
    )


def test_appx_packages_are_classified_without_enabling_execution(
    assert_payload_schema: AssertPayloadSchema,
    assert_field_values: AssertFieldValues,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    report = windows_inventory_report(
        appx_packages=[
            {"name": "Microsoft.VCLibs.140.00.UWPDesktop", "publisher": "Microsoft", "IsFramework": True},
            {"name": "Microsoft.XboxGamingOverlay", "publisher": "Microsoft"},
            {"name": "DellSupportAssist", "publisher": "Dell"},
            {"name": "Unknown.Package", "publisher": "Example"},
        ],
        provisioned_appx_packages=[
            {"name": "Microsoft.ZuneMusic", "publisher": "Microsoft"},
        ],
    )
    by_id = {section["id"]: section for section in report["sections"]}
    appx_by_name = {item["name"]: item for item in by_id["appx-packages"]["items"]}
    provisioned_by_name = {item["name"]: item for item in by_id["provisioned-appx-packages"]["items"]}

    framework = appx_by_name["Microsoft.VCLibs.140.00.UWPDesktop"]["cleanwin_classification"]
    consumer = appx_by_name["Microsoft.XboxGamingOverlay"]["cleanwin_classification"]
    oem = appx_by_name["DellSupportAssist"]["cleanwin_classification"]
    unknown = appx_by_name["Unknown.Package"]["cleanwin_classification"]
    provisioned = provisioned_by_name["Microsoft.ZuneMusic"]["cleanwin_classification"]

    assert_payload_schema(framework, "cleanwin.appx-package-classification.v1")
    assert_field_values(framework, {"category": "framework", "protected_by_default": True, "review_action": "protect"})
    assert_field_values(
        framework,
        {
            "package_family_name": "",
            "publisher": "Microsoft",
            "non_removable": False,
            "dependency": True,
        },
    )
    assert_field_values(consumer, {"category": "consumer-app", "protected_by_default": False, "review_action": "manual-review"})
    assert_field_values(oem, {"category": "oem", "review_action": "manual-review"})
    assert_field_values(unknown, {"category": "unknown", "protected_by_default": True, "review_action": "inventory-only"})
    assert_field_values(provisioned, {"category": "consumer-app", "future_user_profile_impact": True})
    assert_contains_all(consumer["matched_tokens"], ["xbox"])
    for classification in [framework, consumer, oem, unknown, provisioned]:
        assert_execution_disabled(classification)
    assert_summary_counts(
        report,
        {
            "appx_classification_count": 5,
            "appx_protected_by_default_count": 2,
            "appx_manual_review_count": 3,
            "provisioned_appx_future_user_impact_count": 1,
        },
    )


def test_collection_plans_describe_read_only_windows_evidence(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_payload_schema: AssertPayloadSchema,
    assert_field_values: AssertFieldValues,
    assert_contains_all: AssertContainsAll,
) -> None:
    report = windows_inventory_report(appx_packages=[{"name": "Microsoft.XboxGamingOverlay"}])
    by_id = {section["id"]: section for section in report["sections"]}

    appx_plan = by_id["appx-packages"]["collection_plan"]
    assert_payload_schema(appx_plan, "cleanwin.windows-inventory-collection-plan.v1")
    assert_field_values(
        appx_plan,
        {
            "method": "powershell-appx-package-inventory",
            "requires_admin": True,
            "expected_artifact_schema": "cleanwin.appx-package-snapshot.v1",
            "promotion_gate_id": "windows-inventory-to-appx-change",
        },
    )
    assert_execution_disabled(appx_plan)
    assert_contains_all(appx_plan["failure_modes"], ["external-command-not-executed", "requires-admin"])
    assert_payload_schema(appx_plan["artifact_contract"], APPX_PACKAGE_SNAPSHOT_SCHEMA)
    assert_field_values(
        appx_plan["artifact_contract"],
        {
            "artifact_kind": "appx-package-snapshot",
            "scope": "all-users-installed-registration",
            "future_user_profile_impact": False,
            "golden_fixture_required": True,
        },
    )
    assert_contains_all(
        appx_plan["artifact_contract"]["required_fields"],
        ["Name", "PackageFullName", "PackageFamilyName", "Publisher", "InstallLocation"],
    )
    assert_contains_all(appx_plan["artifact_contract"]["rollback_reference_fields"], ["snapshot_artifact_ref"])

    component_plan = by_id["component-store"]["collection_plan"]
    assert_field_values(
        component_plan,
        {
            "method": "dism-component-store-analysis",
            "requires_admin": True,
            "expected_artifact_schema": "cleanwin.component-store-analysis.v1",
        },
    )
    assert_contains_all(component_plan["command"], ["dism.exe", "/AnalyzeComponentStore"])
    assert_execution_disabled(component_plan)


def test_appx_snapshot_artifact_contracts_are_golden_fixture_ready(
    assert_payload_schema: AssertPayloadSchema,
    assert_field_values: AssertFieldValues,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
) -> None:
    appx_contract = appx_snapshot_artifact_contract(provisioned=False)
    provisioned_contract = appx_snapshot_artifact_contract(provisioned=True)

    assert_payload_schema(appx_contract, APPX_PACKAGE_SNAPSHOT_SCHEMA)
    assert_payload_schema(provisioned_contract, PROVISIONED_APPX_PACKAGE_SNAPSHOT_SCHEMA)
    assert_field_values(
        provisioned_contract,
        {
            "artifact_kind": "provisioned-appx-package-snapshot",
            "scope": "windows-image-provisioning",
            "future_user_profile_impact": True,
            "golden_fixture_required": True,
        },
    )
    assert_contains_all(appx_contract["identity_fields"], ["Name", "PackageFullName", "PackageFamilyName", "Publisher"])
    assert_contains_all(provisioned_contract["identity_fields"], ["PackageName", "DisplayName", "PackageFamilyName", "PublisherId"])
    assert_contains_all(provisioned_contract["classification_inputs"], ["DisplayName", "PackageName", "PackageFamilyName", "PublisherId"])
    assert_contains_all(provisioned_contract["rollback_reference_fields"], ["PackageName", "snapshot_artifact_ref"])
    assert_execution_disabled(appx_contract)
    assert_execution_disabled(provisioned_contract)


def test_source_evidence_records_collection_plan_without_running_commands(
    assert_field_values: AssertFieldValues,
    assert_execution_disabled: AssertExecutionDisabled,
) -> None:
    report = windows_inventory_report()
    by_id = {section["id"]: section for section in report["sections"]}

    source = by_id["windows-features"]["source"]
    assert_field_values(
        source["evidence"],
        {
            "collection_method": "dism-feature-inventory",
            "requires_admin": True,
            "executes_by_report": False,
            "expected_artifact_schema": "cleanwin.windows-feature-snapshot.v1",
        },
    )
    assert_execution_disabled(source["evidence"])


def test_cli_and_ai_provider_expose_windows_inventory(
    cleanwin_json: CleanWinJSON,
    assert_readonly_report: AssertReadonlyReport,
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    payload = cleanwin_json("windows-inventory")
    assert_readonly_report(payload, WINDOWS_INVENTORY_SCHEMA)
    assert_cli_provider_schema_sample("windows-inventory", WINDOWS_INVENTORY_SCHEMA)
