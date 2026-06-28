from __future__ import annotations

import json
from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.evidence_bundle import (
    WINDOWS_EVIDENCE_BUNDLE_RECORD_SCHEMA,
    WINDOWS_EVIDENCE_BUNDLE_SCHEMA,
    windows_evidence_bundle_report,
)

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSample = Callable[[str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertSummaryCounts = Callable[[JSONPayload, dict[str, int]], JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertFieldValues = Callable[[JSONPayload, dict[str, Any]], JSONPayload]
AssertAllMatch = Callable[[Sequence[Any], Callable[[Any], bool]], Sequence[Any]]
AssertExactCount = Callable[[Sequence[Any], int], Sequence[Any]]


def _jsonl_records(payload: JSONPayload) -> list[JSONPayload]:
    records = [json.loads(line) for line in str(payload["jsonl"]).splitlines()]
    for record in records:
        assert isinstance(record, dict)
    return records


def test_windows_evidence_bundle_is_readonly_jsonl_chain(
    assert_readonly_report: AssertReadonlyReport,
    assert_summary_counts: AssertSummaryCounts,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
    assert_all_match: AssertAllMatch,
    assert_exact_count: AssertExactCount,
) -> None:
    report = assert_readonly_report(windows_evidence_bundle_report(), WINDOWS_EVIDENCE_BUNDLE_SCHEMA)
    records = _jsonl_records(report)
    by_id = {record["id"]: record for record in records}

    assert_summary_counts(report, {"record_count": 12, "jsonl_line_count": 12, "execution_enabled_count": 0})
    assert_exact_count(records, 12)
    assert_contains_all(
        by_id,
        [
            "report.windows-inventory",
            "snapshot.windows-native-artifacts",
            "plan.registry-privacy",
            "plan.appx-removal",
            "plan.service-task-disable",
            "drill.rollback",
            "gate.promotion",
            "rules.rule-pack-catalog",
            "rules.quality-dashboard",
            "rules.external-quality-summary",
            "recovery.readiness",
            "matrix.windows-smoke",
        ],
    )
    assert_contains_all(
        report["summary"]["kind_counts"],
        ["report-ref", "snapshot-ref", "plan-ref", "drill-ref", "gate-ref", "rule-governance-ref", "recovery-ref", "ci-artifact-ref"],
    )
    assert_field_values(
        by_id["rules.external-quality-summary"],
        {
            "schema": WINDOWS_EVIDENCE_BUNDLE_RECORD_SCHEMA,
            "kind": "rule-governance-ref",
            "payload_schema": "cleanwin.external-rule-quality-summary.v1",
            "payload_summary.execution_enabled": False,
            "payload_summary.promotion_allowed": False,
        },
    )
    assert_contains_all(by_id["rules.external-quality-summary"]["required_for"], ["external-rule-review", "promotion-gates"])
    assert_field_values(
        report["usage"],
        {
            "format": "jsonl",
            "write_behavior": "caller-managed",
            "suggested_artifact_name": "cleanwin-windows-evidence-bundle.jsonl",
        },
    )
    assert_all_match(records, lambda record: record["schema"] == WINDOWS_EVIDENCE_BUNDLE_RECORD_SCHEMA)
    assert_all_match(records, lambda record: record["executes_system_commands"] is False)


def test_windows_evidence_bundle_cli_provider_and_schema_registry(
    cleanwin_json: CleanWinJSON,
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_sample: AssertSchemaSample,
    assert_readonly_report: AssertReadonlyReport,
    assert_contains_all: AssertContainsAll,
    assert_summary_counts: AssertSummaryCounts,
) -> None:
    sample = assert_readonly_report(
        assert_cli_provider_schema_sample("windows-evidence-bundle", WINDOWS_EVIDENCE_BUNDLE_SCHEMA),
        WINDOWS_EVIDENCE_BUNDLE_SCHEMA,
    )
    record_sample = assert_schema_sample(WINDOWS_EVIDENCE_BUNDLE_RECORD_SCHEMA)

    assert_contains_all(cleanwin_json("windows-evidence-bundle"), ["jsonl", "records"])
    assert_field_names = set(record_sample)
    assert_contains_all(assert_field_names, ["id", "kind", "ref", "payload_schema", "payload_summary"])
    assert_summary_counts(sample, {"jsonl_line_count": len(_jsonl_records(sample))})
