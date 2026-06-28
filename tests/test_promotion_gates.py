from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.promotion_gates import (
    PROMOTION_GATE_VALIDATION_SCHEMA,
    PROMOTION_GATES_SCHEMA,
    promotion_gates_report,
    validate_promotion_gate_action,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
SummaryCounts = dict[str, int]
AssertSummaryCounts = Callable[[JSONPayload, SummaryCounts], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_promotion_gates_are_non_destructive_and_keep_system_execution_disabled(
    assert_readonly_report: AssertReadonlyReport,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_summary_counts: AssertSummaryCounts,
    assert_any_text_contains: AssertAnyTextContains,
) -> None:
    report = promotion_gates_report()

    assert_readonly_report(report, PROMOTION_GATES_SCHEMA)
    assert_execution_disabled(report)
    assert_summary_counts(report, {"report_only_gate_count": 10})
    assert_any_text_contains(report["non_goals"], "does not enable registry")


def test_promotion_gates_cover_high_risk_report_surfaces(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = promotion_gates_report()
    by_id = {gate["id"]: gate for gate in report["gates"]}

    assert_contains_all(
        by_id,
        [
            "registry-privacy-to-registry-change",
            "startup-entry-to-disable-plan",
            "service-task-to-disable-plan",
            "official-command-to-executable-action",
            "windows-inventory-to-appx-change",
            "windows-inventory-to-feature-change",
            "windows-inventory-to-component-store-cleanup",
            "windows-inventory-to-installer-cache-cleanup",
            "windows-inventory-to-recycle-bin-empty",
            "browser-profile-to-cache-plan",
            "external-rule-to-reviewed-rule-pack",
        ],
    )

    registry_gate = by_id["registry-privacy-to-registry-change"]
    assert_field_values(registry_gate, {"default_state": "report-only"})
    assert_execution_disabled(registry_gate, "ai_auto_call_allowed")
    assert_contains_all(registry_gate["required_snapshots"], ["registry-export"])
    assert_contains_all(registry_gate["required_tests"], ["rollback-metadata-validation"])

    startup_gate = by_id["startup-entry-to-disable-plan"]
    assert_contains_all(startup_gate["required_evidence"], ["target_path", "target_status", "snapshot_requirements"])
    assert_contains_all(startup_gate["required_tests"], ["fixture-environment-expansion-required"])

    browser_gate = by_id["browser-profile-to-cache-plan"]
    assert_field_values(browser_gate, {"default_state": "low-risk-cache-only", "ai_auto_call_allowed": True})
    assert_contains_all(browser_gate["required_evidence"], ["locked_profile_state", "locked_state_ref", "sensitive_exclusions"])

    external_rule_gate = by_id["external-rule-to-reviewed-rule-pack"]
    assert_field_values(external_rule_gate, {"target_action": "external-rule-review", "default_state": "report-only"})
    assert_execution_disabled(external_rule_gate, "ai_auto_call_allowed")
    assert_contains_all(external_rule_gate["source_reports"], ["cleanwin.external-rule-translation.v1", "cleanwin.external-rule-import-sandbox.v1"])
    assert_contains_all(external_rule_gate["required_evidence"], ["quality_gate", "owner", "sensitive_exclusions", "active_install_marker"])
    assert_contains_all(external_rule_gate["required_tests"], ["fixture-dangerous-path-blocked", "fixture-unsupported-semantics-blocked"])


def test_promotion_gates_cover_windows_inventory_system_surfaces(
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = promotion_gates_report()
    by_id = {gate["id"]: gate for gate in report["gates"]}

    appx_gate = by_id["windows-inventory-to-appx-change"]
    assert_field_values(appx_gate, {"target_action": "appx-provisioned-package-change", "default_state": "report-only"})
    assert_execution_disabled(appx_gate, "ai_auto_call_allowed")
    assert_contains_all(appx_gate["source_reports"], ["cleanwin.windows-inventory.v1", "cleanwin.debloat-privacy-report.v1"])
    assert_contains_all(appx_gate["required_snapshots"], ["appx-package-snapshot", "provisioned-appx-snapshot"])
    assert_contains_all(appx_gate["required_evidence"], ["dependency_or_framework_classification"])

    component_gate = by_id["windows-inventory-to-component-store-cleanup"]
    assert_contains_all(component_gate["source_reports"], ["cleanwin.official-command-plan.v1"])
    assert_contains_all(component_gate["required_evidence"], ["official_command_id", "pending_reboot_state"])
    assert_contains_all(component_gate["required_tests"], ["command-id-allowlist"])

    service_task_gate = by_id["service-task-to-disable-plan"]
    assert_contains_all(service_task_gate["required_snapshots"], ["service-registry-export", "scheduled-task-xml-export"])
    assert_contains_all(service_task_gate["required_evidence"], ["target_status", "dependency_or_trigger_review", "recovery_or_xml_snapshot_requirement"])
    assert_contains_all(service_task_gate["required_tests"], ["fixture-service-target-status", "fixture-scheduled-task-xml-required"])

    installer_gate = by_id["windows-inventory-to-installer-cache-cleanup"]
    assert_contains_all(installer_gate["source_reports"], ["cleanwin.installed-app-inventory.v1"])
    assert_contains_all(installer_gate["required_evidence"], ["owning_product_code", "repair_uninstall_dependency_review"])

    recycle_gate = by_id["windows-inventory-to-recycle-bin-empty"]
    assert_contains_all(recycle_gate["required_evidence"], ["sid_or_user_scope", "user_confirmation_scope"])
    assert_any_text_contains([recycle_gate["rationale"]], "irreversible")


def test_cli_ai_provider_and_schema_registry_expose_promotion_gates(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
) -> None:
    assert_cli_provider_schema_sample("promotion-gates", PROMOTION_GATES_SCHEMA)


def test_promotion_gate_validator_reports_missing_evidence_without_execution(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={"schema": "cleanwin.windows-inventory.v1"},
        proposed_action={
            "target_action": "appx-provisioned-package-change",
            "evidence": ["package_name"],
            "snapshots": ["appx-package-snapshot"],
            "rollback_metadata": [],
            "tests": [],
            "human_confirmations": [],
        },
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": False, "gate_id": "windows-inventory-to-appx-change"})
    assert_contains_all(validation["missing_evidence"], ["package_family_name", "publisher", "provisioned_state"])
    assert_contains_all(validation["missing_snapshots"], ["system-restore-point", "provisioned-appx-snapshot"])
    assert_contains_all(validation["missing_rollback_metadata"], ["restore_command"])
    assert_contains_all(validation["missing_tests"], ["rollback-metadata-validation"])
    assert_contains_all(validation["missing_human_confirmations"], ["matching-dry-run-token"])
    assert_contains_all({error["code"] for error in validation["errors"]}, ["MISSING_REQUIRED_EVIDENCE", "MISSING_REQUIRED_SNAPSHOTS"])
    assert_execution_disabled(validation)


def test_promotion_gate_validator_accepts_complete_report_only_contract(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action={
            "target_action": "browser-cache-delete",
            "evidence": ["browser", "profile_name", "profile_path", "cache_layer", "locked_profile_state", "locked_state_ref", "sensitive_exclusions"],
            "snapshots": [],
            "rollback_metadata": ["profile_path", "cache_layer", "recycle_destination"],
            "tests": ["fixture-locked-profile", "fixture-sensitive-data-excluded", "cache-layer-classification"],
            "human_confirmations": ["matching-dry-run-token"],
            "locked_state": {"schema": "cleanwin.locked-state.v1", "locked": False, "state": "not-observed", "blocked_reasons": []},
        },
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": True, "gate_id": "browser-profile-to-cache-plan", "safe_to_execute": False})
    assert_field_values(
        validation,
        {
            "missing_evidence": [],
            "missing_snapshots": [],
            "missing_rollback_metadata": [],
            "missing_tests": [],
            "missing_human_confirmations": [],
            "missing_locked_state_evidence": [],
            "errors": [],
        },
    )
    assert_execution_disabled(validation)


def test_promotion_gate_validator_blocks_browser_cache_without_locked_state(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action={
            "target_action": "browser-cache-delete",
            "evidence": ["browser", "profile_name", "profile_path", "cache_layer", "locked_profile_state", "sensitive_exclusions"],
            "rollback_metadata": ["profile_path", "cache_layer", "recycle_destination"],
            "tests": ["fixture-locked-profile", "fixture-sensitive-data-excluded", "cache-layer-classification"],
            "human_confirmations": ["matching-dry-run-token"],
        },
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": False, "gate_id": "browser-profile-to-cache-plan"})
    assert_contains_all(validation["missing_evidence"], ["locked_state_ref"])
    assert_contains_all(validation["missing_locked_state_evidence"], ["locked_state_ref", "locked_state"])
    assert_contains_all({error["code"] for error in validation["errors"]}, ["MISSING_LOCKED_STATE_EVIDENCE"])
    assert_execution_disabled(validation)


def test_promotion_gate_validator_blocks_locked_browser_cache(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={"schema": "cleanwin.browser-profile-inventory.v1"},
        proposed_action={
            "target_action": "browser-cache-delete",
            "evidence": ["browser", "profile_name", "profile_path", "cache_layer", "locked_profile_state", "locked_state_ref", "sensitive_exclusions"],
            "rollback_metadata": ["profile_path", "cache_layer", "recycle_destination"],
            "tests": ["fixture-locked-profile", "fixture-sensitive-data-excluded", "cache-layer-classification"],
            "human_confirmations": ["matching-dry-run-token"],
            "locked_state": {
                "schema": "cleanwin.locked-state.v1",
                "locked": True,
                "state": "locked-or-running",
                "blocked_reasons": ["browser-process-running"],
            },
        },
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": False, "gate_id": "browser-profile-to-cache-plan", "missing_locked_state_evidence": []})
    assert_contains_all({error["code"] for error in validation["errors"]}, ["LOCKED_STATE_BLOCKS_CACHE_PROMOTION"])
    assert_execution_disabled(validation)


def test_promotion_gate_validator_blocks_external_rule_quality_gaps(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={
            "schema": "cleanwin.external-rule-translation.v1",
            "quality_gate": {
                "schema": "cleanwin.external-rule-quality-gate.v1",
                "risk": "high",
                "recoverability": "low",
                "dangerous_path_count": 1,
                "unsupported_semantic_count": 2,
                "active_marker_missing": True,
                "sensitive_exclusion_missing": True,
                "fixture_missing": True,
                "review_required": True,
                "execution_enabled": False,
                "promotion_allowed": False,
                "promotion_blockers": [
                    "external-untrusted-provenance",
                    "fixture-coverage-required",
                    "dangerous-path-review-required",
                    "unsupported-semantics-review-required",
                ],
            },
        },
        proposed_action={
            "target_action": "external-rule-review",
            "evidence": ["quality_gate"],
            "tests": [],
            "human_confirmations": [],
        },
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_field_values(validation, {"valid": False, "gate_id": "external-rule-to-reviewed-rule-pack"})
    assert_contains_all(validation["missing_evidence"], ["owner", "reviewer", "sensitive_exclusions", "active_install_marker"])
    assert_contains_all(validation["missing_tests"], ["fixture-dangerous-path-blocked", "fixture-unsupported-semantics-blocked"])
    assert_contains_all(validation["missing_quality_gate_reviews"], ["active-marker-review", "sensitive-exclusion-review", "fixture-coverage"])
    assert_contains_all(validation["missing_quality_gate_reviews"], ["dangerous-path-review", "unsupported-semantics-review", "owner-review"])
    assert_contains_all(validation["quality_gate_blockers"], ["external-untrusted-provenance", "fixture-coverage-required"])
    assert_contains_all(
        {error["code"] for error in validation["errors"]},
        ["EXTERNAL_RULE_QUALITY_BLOCKERS", "MISSING_EXTERNAL_RULE_REVIEWS"],
    )
    assert_execution_disabled(validation)


def test_promotion_gate_validator_keeps_external_rules_report_only_even_when_reviewed(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_field_values: AssertFieldValues,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={"schema": "cleanwin.external-rule-import-sandbox.v1"},
        proposed_action={
            "target_action": "external-rule-review",
            "evidence": [
                "import_batch_id",
                "source_hash",
                "external_rule_id",
                "translated_rule_id",
                "quality_gate",
                "owner",
                "reviewer",
                "rationale",
                "sensitive_exclusions",
                "active_install_marker",
            ],
            "tests": [
                "fixture-external-rule-golden",
                "fixture-dangerous-path-blocked",
                "fixture-unsupported-semantics-blocked",
                "fixture-sensitive-exclusion-required",
            ],
            "human_confirmations": ["explicit-external-rule-owner-review"],
            "quality_gate": {
                "schema": "cleanwin.external-rule-quality-gate.v1",
                "risk": "low",
                "recoverability": "high",
                "dangerous_path_count": 0,
                "unsupported_semantic_count": 0,
                "active_marker_missing": False,
                "sensitive_exclusion_missing": False,
                "fixture_missing": False,
                "review_required": False,
                "execution_enabled": False,
                "promotion_allowed": False,
                "promotion_blockers": [],
            },
        },
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_field_values(
        validation,
        {
            "valid": True,
            "gate_id": "external-rule-to-reviewed-rule-pack",
            "missing_quality_gate_reviews": [],
            "quality_gate_blockers": [],
            "safe_to_execute": False,
        },
    )
    assert_execution_disabled(validation)


def test_promotion_gate_validator_rejects_unknown_action(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
) -> None:
    validation = validate_promotion_gate_action(
        source_report={"schema": "cleanwin.windows-inventory.v1"},
        proposed_action={"target_action": "unknown-system-change"},
    )

    assert_payload_schema(validation, PROMOTION_GATE_VALIDATION_SCHEMA)
    assert_contains_all({error["code"] for error in validation["errors"]}, ["UNKNOWN_PROMOTION_GATE"])
    assert_execution_disabled(validation)
