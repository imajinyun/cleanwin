"""Read-only Windows evidence bundle contract."""

from __future__ import annotations

import json
from typing import Any

from cleanwincli.execution_contracts import (
    appx_removal_plan_report,
    registry_privacy_change_plan_report,
    rollback_drill_report,
    service_task_disable_plan_report,
)
from cleanwincli.promotion_gates import promotion_gates_report
from cleanwincli.recovery import recovery_readiness_report
from cleanwincli.windows_inventory import windows_inventory_report
from cleanwincli.windows_native_artifacts import windows_native_artifacts_report
from cleanwincli.windows_smoke import windows_smoke_matrix_report

WINDOWS_EVIDENCE_BUNDLE_SCHEMA = "cleanwin.windows-evidence-bundle.v1"
WINDOWS_EVIDENCE_BUNDLE_RECORD_SCHEMA = "cleanwin.windows-evidence-bundle-record.v1"


def _record(
    record_id: str,
    *,
    kind: str,
    ref: str,
    schema: str,
    producer: str,
    required_for: list[str],
    payload_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": WINDOWS_EVIDENCE_BUNDLE_RECORD_SCHEMA,
        "id": record_id,
        "kind": kind,
        "ref": ref,
        "payload_schema": schema,
        "producer": producer,
        "required_for": required_for,
        "payload_summary": payload_summary,
        "destructive": False,
        "executes_system_commands": False,
    }


def _jsonl(records: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(record, sort_keys=True, ensure_ascii=False) for record in records)


def windows_evidence_bundle_report() -> dict[str, Any]:
    inventory = windows_inventory_report()
    native_artifacts = windows_native_artifacts_report()
    smoke = windows_smoke_matrix_report()
    registry_plan = registry_privacy_change_plan_report()
    appx_plan = appx_removal_plan_report()
    service_task_plan = service_task_disable_plan_report()
    rollback_drills = rollback_drill_report()
    promotion_gates = promotion_gates_report()
    recovery = recovery_readiness_report()

    records = [
        _record(
            "report.windows-inventory",
            kind="report-ref",
            ref="report://windows-inventory/current",
            schema=str(inventory["schema"]),
            producer="windows-inventory",
            required_for=["appx-removal-plan", "promotion-gates"],
            payload_summary={"section_count": inventory["summary"]["section_count"], "appx_classification_count": inventory["summary"].get("appx_classification_count", 0)},
        ),
        _record(
            "snapshot.windows-native-artifacts",
            kind="snapshot-ref",
            ref="snapshot://windows-native-artifacts/contracts",
            schema=str(native_artifacts["schema"]),
            producer="windows-native-artifacts",
            required_for=["windows-smoke-matrix", "rollback-drill-report"],
            payload_summary={"contract_count": native_artifacts["summary"]["contract_count"], "execution_enabled_count": native_artifacts["summary"]["execution_enabled_count"]},
        ),
        _record(
            "plan.registry-privacy",
            kind="plan-ref",
            ref="plan://registry-privacy/current",
            schema=str(registry_plan["schema"]),
            producer="registry-privacy-plan",
            required_for=["promotion-gates", "rollback-drill-report"],
            payload_summary={
                "change_count": registry_plan["summary"]["change_count"],
                "requires_registry_export_count": registry_plan["summary"]["requires_registry_export_count"],
            },
        ),
        _record(
            "plan.appx-removal",
            kind="plan-ref",
            ref="plan://appx-removal/current",
            schema=str(appx_plan["schema"]),
            producer="appx-removal-plan",
            required_for=["promotion-gates", "rollback-drill-report"],
            payload_summary={
                "change_count": appx_plan["summary"]["change_count"],
                "blocked_package_count": appx_plan["summary"]["blocked_package_count"],
            },
        ),
        _record(
            "plan.service-task-disable",
            kind="plan-ref",
            ref="plan://service-task-disable/current",
            schema=str(service_task_plan["schema"]),
            producer="service-task-disable-plan",
            required_for=["promotion-gates", "rollback-drill-report"],
            payload_summary={
                "change_count": service_task_plan["summary"]["change_count"],
                "blocked_target_count": service_task_plan["summary"]["blocked_target_count"],
            },
        ),
        _record(
            "drill.rollback",
            kind="drill-ref",
            ref="drill://rollback/current",
            schema=str(rollback_drills["schema"]),
            producer="rollback-drill-report",
            required_for=["registry-privacy-plan", "appx-removal-plan", "service-task-disable-plan"],
            payload_summary={"drill_count": rollback_drills["summary"]["drill_count"], "target_types": rollback_drills["summary"]["target_types"]},
        ),
        _record(
            "gate.promotion",
            kind="gate-ref",
            ref="gate://promotion/current",
            schema=str(promotion_gates["schema"]),
            producer="promotion-gates",
            required_for=["execution-expansion-review"],
            payload_summary={
                "gate_count": promotion_gates["gate_count"],
                "execution_enabled_count": 1 if promotion_gates["execution_enabled"] else 0,
            },
        ),
        _record(
            "recovery.readiness",
            kind="recovery-ref",
            ref="recovery://readiness/current",
            schema=str(recovery["schema"]),
            producer="recovery-readiness",
            required_for=["execution-expansion-review", "rollback-drill-report"],
            payload_summary={
                "capability_count": len(recovery["capabilities"]),
                "available_count": sum(1 for capability in recovery["capabilities"] if capability["available"]),
            },
        ),
        _record(
            "matrix.windows-smoke",
            kind="ci-artifact-ref",
            ref="ci://windows-smoke-matrix/current",
            schema=str(smoke["schema"]),
            producer="windows-smoke-matrix",
            required_for=["windows-ci-artifacts"],
            payload_summary={
                "scenario_count": smoke["scenario_count"],
                "destructive_scenario_count": smoke["summary"]["destructive_scenario_count"],
            },
        ),
    ]

    kind_counts = {kind: sum(1 for record in records if record["kind"] == kind) for kind in sorted({str(record["kind"]) for record in records})}
    jsonl_payload = _jsonl(records)
    return {
        "schema": WINDOWS_EVIDENCE_BUNDLE_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "records": records,
        "jsonl": jsonl_payload,
        "summary": {
            "record_count": len(records),
            "jsonl_line_count": len(jsonl_payload.splitlines()),
            "kind_counts": kind_counts,
            "execution_enabled_count": sum(1 for record in records if record["executes_system_commands"]),
        },
        "usage": {
            "format": "jsonl",
            "write_behavior": "caller-managed",
            "suggested_artifact_name": "cleanwin-windows-evidence-bundle.jsonl",
            "machine_consumers": ["ai-host", "mcp", "ci", "governance-review"],
        },
        "non_goals": [
            "This report does not write files.",
            "This report does not collect Windows artifacts.",
            "This report does not execute cleanup, registry, AppX, service, task, DISM, or PowerShell commands.",
        ],
    }
