"""CleanWin command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cleanwincli.ai_policy_simulate import policy_simulate
from cleanwincli.ai_tools import ai_tools_report
from cleanwincli.collectors import parse_categories, parse_rule_ids
from cleanwincli.commands import (
    ai_readiness_command,
    ai_runbook_command,
    ai_self_test_command,
    appx_removal_plan_command,
    backup_delete_contract_command,
    browser_profile_inventory_command,
    contract_exposure_matrix_command,
    debloat_privacy_report_command,
    disable_revert_contract_command,
    environment_index_command,
    external_rule_translate_command,
    file_report_command,
    host_policy_report,
    installed_app_inventory_command,
    low_risk_cache_readiness_command,
    official_command_plan_command,
    operation_log_readiness_command,
    permanent_delete_denial_command,
    preset_catalog_command,
    promotion_gates_command,
    recovery_readiness_command,
    registry_privacy_plan_command,
    rollback_drill_report_command,
    rule_pack_catalog_command,
    rule_quality_dashboard_command,
    scan_governance_command,
    self_update_command,
    service_task_disable_plan_command,
    startup_service_inventory_command,
    system_health_report_command,
    windows_artifact_layout_command,
    windows_artifact_validate_command,
    windows_evidence_bundle_command,
    windows_inventory_command,
    windows_native_artifacts_command,
    windows_smoke_matrix_command,
    workflow_decision_command,
    workflow_router_command,
    workflow_trace_command,
)
from cleanwincli.core import (
    capabilities,
)
from cleanwincli.doctor import doctor_report
from cleanwincli.output import render_human_payload
from cleanwincli.plan_executor import execute_plan
from cleanwincli.plan_io import build_plan, inspect, load_plan
from cleanwincli.plan_review import review_plan
from cleanwincli.plan_validation import validate_plan_payload


def emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_human_payload(payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cleanwin", description="Conservative Windows cleanup planner")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("capabilities", help="show safety capabilities")

    inspect_parser = subparsers.add_parser("inspect", help="inspect cleanup candidates")
    inspect_parser.add_argument("--categories", default="temp,dev-cache")
    inspect_parser.add_argument("--older-than-days", type=int, default=7)
    inspect_parser.add_argument("--max-items", type=int, default=100)
    inspect_parser.add_argument("--rule-id", action="append", default=[], help="filter candidates/findings by rule id; may be repeated or comma-separated")

    plan_parser = subparsers.add_parser("plan", help="create a cleanup plan")
    plan_parser.add_argument("--categories", default="temp,dev-cache")
    plan_parser.add_argument("--older-than-days", type=int, default=7)
    plan_parser.add_argument("--max-items", type=int, default=100)
    plan_parser.add_argument("--rule-id", action="append", default=[], help="filter planned candidates by rule id; may be repeated or comma-separated")
    plan_parser.add_argument("--output")

    validate_parser = subparsers.add_parser("validate-plan", help="validate a cleanup plan")
    validate_parser.add_argument("--plan-file", required=True)
    validate_parser.add_argument("--no-require-plan-context", action="store_true")

    review_parser = subparsers.add_parser("review-plan", help="summarize a cleanup plan for human/AI review")
    review_parser.add_argument("--plan-file", required=True)
    review_parser.add_argument("--no-require-plan-context", action="store_true")

    execute_parser = subparsers.add_parser("execute-plan", help="execute a previously validated cleanup plan")
    execute_parser.add_argument("--plan-file", required=True)
    execute_parser.add_argument("--execute", action="store_true")
    execute_parser.add_argument("--yes", action="store_true")
    execute_parser.add_argument("--no-require-plan-context", action="store_true")
    execute_parser.add_argument("--operation-log")
    execute_parser.add_argument("--trash-root")
    execute_parser.add_argument("--confirmation-phrase")
    execute_parser.add_argument("--confirmation-token")

    ai_tools_parser = subparsers.add_parser("ai-tools", help="show AI/MCP tool schemas")
    ai_tools_parser.add_argument(
        "--provider",
        choices=[
            "catalog",
            "openai",
            "anthropic",
            "parity",
            "validation",
            "registry",
            "host-policy",
            "readiness",
            "self-test",
            "runbook",
            "workflow-router",
            "environment-index",
            "workflow-decision",
            "workflow-trace",
            "doctor",
            "backup-delete-contract",
            "file-report",
            "recovery-readiness",
            "scan-governance",
            "external-rule-translate",
            "installed-app-inventory",
            "official-command-plan",
            "preset-catalog",
            "rule-pack-catalog",
            "rule-quality-dashboard",
            "promotion-gates",
            "low-risk-cache-readiness",
            "operation-log-readiness",
            "contract-exposure-matrix",
            "browser-profile-inventory",
            "debloat-privacy-report",
            "disable-revert-contract",
            "permanent-delete-denial",
            "registry-privacy-plan",
            "appx-removal-plan",
            "service-task-disable-plan",
            "rollback-drill-report",
            "startup-service-inventory",
            "system-health-report",
            "windows-artifact-layout",
            "windows-artifact-validate",
            "windows-native-artifacts",
            "windows-inventory",
            "windows-smoke-matrix",
            "windows-evidence-bundle",
            "review-sample",
        ],
        default="catalog",
    )

    subparsers.add_parser("schema-registry", help="show machine-readable schema registry")
    subparsers.add_parser("doctor", help="run non-destructive engineering health checks")
    self_update_parser = subparsers.add_parser("self-update", help="check for newer cleanwin versions (Windows portable only)")
    self_update_parser.add_argument("--execute", action="store_true", help="download and replace the current install via install.ps1")
    self_update_parser.add_argument("--version", default="latest", help="target version (default: latest)")
    subparsers.add_parser("backup-delete-contract", help="show non-executable backup-then-delete contracts")
    subparsers.add_parser("file-report", help="show read-only large-file and duplicate-file report")
    subparsers.add_parser("recovery-readiness", help="show non-destructive recovery readiness gates")
    subparsers.add_parser("scan-governance", help="show scan performance and external rule review governance")
    external_rule_parser = subparsers.add_parser("external-rule-translate", help="translate winapp2.ini or CleanerML rules into read-only review candidates")
    external_rule_parser.add_argument("--input", required=True, help="local winapp2.ini or CleanerML file to parse")
    external_rule_parser.add_argument("--format", choices=["auto", "winapp2", "cleanerml"], default="auto")
    external_rule_parser.add_argument("--upstream-project")
    external_rule_parser.add_argument("--upstream-ref", default="local-file")
    external_rule_parser.add_argument("--license", default="external-review-required")
    subparsers.add_parser("installed-app-inventory", help="show read-only installed app inventory")
    subparsers.add_parser("official-command-plan", help="show read-only official Windows cleanup command plan")
    subparsers.add_parser("preset-catalog", help="show read-only cleanup preset catalog")
    subparsers.add_parser("rule-pack-catalog", help="show read-only cleanup rule pack catalog and quality scores")
    subparsers.add_parser("rule-quality-dashboard", help="show read-only cleanup rule quality dashboard")
    subparsers.add_parser("promotion-gates", help="show report-to-execution promotion gates")
    subparsers.add_parser("low-risk-cache-readiness", help="show read-only low-risk cache execution readiness gates")
    subparsers.add_parser("operation-log-readiness", help="show read-only operation log readiness gates")
    contract_exposure_parser = subparsers.add_parser("contract-exposure-matrix", help="show read-only contract exposure consistency matrix")
    contract_exposure_parser.add_argument("--validate", action="store_true")
    subparsers.add_parser("browser-profile-inventory", help="show read-only browser profile and cache layer inventory")
    subparsers.add_parser("debloat-privacy-report", help="show read-only debloat and privacy telemetry report")
    subparsers.add_parser("disable-revert-contract", help="show non-executable disable/revert action contracts")
    subparsers.add_parser("permanent-delete-denial", help="show permanent deletion denial contract")
    subparsers.add_parser("registry-privacy-plan", help="show simulated registry privacy change/revert plan")
    subparsers.add_parser("appx-removal-plan", help="show simulated AppX per-user remove/revert plan")
    subparsers.add_parser("service-task-disable-plan", help="show simulated service/task disable/revert plan")
    subparsers.add_parser("rollback-drill-report", help="show fixture-only rollback drill coverage")
    subparsers.add_parser("startup-service-inventory", help="show read-only startup, service, and task inventory")
    subparsers.add_parser("system-health-report", help="show read-only Windows system health recommendations")
    subparsers.add_parser("windows-artifact-layout", help="show read-only Windows native artifact layout contract")
    artifact_validate_parser = subparsers.add_parser("windows-artifact-validate", help="validate a Windows native collector manifest and artifact hashes")
    artifact_validate_parser.add_argument("--manifest", help="path to collector manifest.json; omitted emits the validator sample contract")
    subparsers.add_parser("windows-native-artifacts", help="show read-only Windows native artifact collection contracts")
    subparsers.add_parser("windows-inventory", help="show read-only Windows inventory baseline")
    subparsers.add_parser("windows-smoke-matrix", help="show Windows smoke evidence matrix")
    subparsers.add_parser("windows-evidence-bundle", help="show Windows evidence JSONL bundle")

    host_policy_parser = subparsers.add_parser("host-policy", help="show AI host allow/deny policy")
    host_policy_parser.add_argument("--validate", action="store_true")

    readiness_parser = subparsers.add_parser("ai-readiness", help="show AI host readiness report")
    readiness_parser.add_argument("--validate", action="store_true")

    subparsers.add_parser("ai-self-test", help="run deterministic AI host self-test checks")
    subparsers.add_parser("ai-runbook", help="show safe AI/MCP host runbook")
    subparsers.add_parser("workflow-router", help="show AI-safe workflow routing contract")
    subparsers.add_parser("environment-index", help="show read-only host capability index")
    subparsers.add_parser("workflow-trace", help="show expected AI workflow artifact chain")

    workflow_decision_parser = subparsers.add_parser("workflow-decision", help="validate a requested workflow route/tool decision")
    workflow_decision_parser.add_argument("--route-id", required=True)
    workflow_decision_parser.add_argument("--requested-tool")
    workflow_decision_parser.add_argument("--artifact", action="append", default=[], help="artifact already produced by earlier workflow steps; may be repeated")

    simulate_parser = subparsers.add_parser("policy-simulate", help="simulate AI host execution policy")
    simulate_parser.add_argument("--plan-file", required=True)
    simulate_parser.add_argument("--execute", action="store_true")
    simulate_parser.add_argument("--delete-mode", choices=["recycle", "permanent"], default="recycle")
    simulate_parser.add_argument("--operation-log")
    simulate_parser.add_argument("--no-require-plan-context", action="store_true")
    simulate_parser.add_argument("--require-confirmation-token", action="store_true")
    simulate_parser.add_argument("--confirmation-token")
    simulate_parser.add_argument("--confirmation-phrase")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "capabilities":
            emit(capabilities(), as_json=args.json)
            return 0
        if args.command == "inspect":
            payload = inspect(
                parse_categories(args.categories),
                older_than_days=args.older_than_days,
                max_items=args.max_items,
                rule_ids=[rule_id for item in args.rule_id for rule_id in parse_rule_ids(item)],
            )
            emit(payload, as_json=args.json)
            return 0
        if args.command == "plan":
            plan = build_plan(
                parse_categories(args.categories),
                older_than_days=args.older_than_days,
                max_items=args.max_items,
                rule_ids=[rule_id for item in args.rule_id for rule_id in parse_rule_ids(item)],
            )
            payload = plan.to_dict()
            if args.output:
                Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
            emit(payload, as_json=args.json)
            return 0
        if args.command == "validate-plan":
            plan, raw = load_plan(Path(args.plan_file))
            payload = validate_plan_payload(plan, raw, require_context=not args.no_require_plan_context)
            emit(payload, as_json=args.json)
            return 0 if payload["valid"] else 2
        if args.command == "review-plan":
            plan, raw = load_plan(Path(args.plan_file))
            payload = review_plan(plan, raw, require_context=not args.no_require_plan_context)
            emit(payload, as_json=args.json)
            return 0 if payload["validation"]["valid"] else 2
        if args.command == "execute-plan":
            plan, raw = load_plan(Path(args.plan_file))
            payload = execute_plan(
                plan,
                execute=args.execute,
                yes=args.yes,
                require_context=not args.no_require_plan_context,
                raw_payload=raw,
                operation_log=Path(args.operation_log) if args.operation_log else None,
                trash_root=Path(args.trash_root) if args.trash_root else None,
                confirmation_phrase=args.confirmation_phrase,
                confirmation_token=args.confirmation_token,
            )
            emit(payload, as_json=args.json)
            return 0 if not payload.get("error") and payload.get("validation", {}).get("valid", True) else 2
        if args.command == "ai-tools":
            emit(ai_tools_report(args.provider), as_json=args.json)
            return 0
        if args.command == "schema-registry":
            emit(ai_tools_report("registry"), as_json=args.json)
            return 0
        if args.command == "doctor":
            payload = doctor_report()
            emit(payload, as_json=args.json)
            return 0 if payload["ready"] else 2
        if args.command == "self-update":
            payload = self_update_command(execute=args.execute, version=args.version)
            emit(payload, as_json=args.json)
            return 0 if payload["executed"] or payload["dry_run"] else 1
        if args.command == "backup-delete-contract":
            emit(backup_delete_contract_command(), as_json=args.json)
            return 0
        if args.command == "file-report":
            emit(file_report_command(), as_json=args.json)
            return 0
        if args.command == "recovery-readiness":
            emit(recovery_readiness_command(), as_json=args.json)
            return 0
        if args.command == "scan-governance":
            emit(scan_governance_command(), as_json=args.json)
            return 0
        if args.command == "external-rule-translate":
            emit(
                external_rule_translate_command(
                    Path(args.input),
                    source_format=args.format,
                    upstream_project=args.upstream_project,
                    upstream_rule_id_or_commit=args.upstream_ref,
                    license_name=args.license,
                ),
                as_json=args.json,
            )
            return 0
        if args.command == "installed-app-inventory":
            emit(installed_app_inventory_command(), as_json=args.json)
            return 0
        if args.command == "official-command-plan":
            emit(official_command_plan_command(), as_json=args.json)
            return 0
        if args.command == "preset-catalog":
            emit(preset_catalog_command(), as_json=args.json)
            return 0
        if args.command == "rule-pack-catalog":
            emit(rule_pack_catalog_command(), as_json=args.json)
            return 0
        if args.command == "rule-quality-dashboard":
            emit(rule_quality_dashboard_command(), as_json=args.json)
            return 0
        if args.command == "promotion-gates":
            emit(promotion_gates_command(), as_json=args.json)
            return 0
        if args.command == "low-risk-cache-readiness":
            emit(low_risk_cache_readiness_command(), as_json=args.json)
            return 0
        if args.command == "operation-log-readiness":
            emit(operation_log_readiness_command(), as_json=args.json)
            return 0
        if args.command == "contract-exposure-matrix":
            payload = contract_exposure_matrix_command(validate=args.validate)
            emit(payload, as_json=args.json)
            return 0 if payload.get("valid", False) else 2
        if args.command == "browser-profile-inventory":
            emit(browser_profile_inventory_command(), as_json=args.json)
            return 0
        if args.command == "debloat-privacy-report":
            emit(debloat_privacy_report_command(), as_json=args.json)
            return 0
        if args.command == "disable-revert-contract":
            emit(disable_revert_contract_command(), as_json=args.json)
            return 0
        if args.command == "permanent-delete-denial":
            emit(permanent_delete_denial_command(), as_json=args.json)
            return 0
        if args.command == "registry-privacy-plan":
            emit(registry_privacy_plan_command(), as_json=args.json)
            return 0
        if args.command == "appx-removal-plan":
            emit(appx_removal_plan_command(), as_json=args.json)
            return 0
        if args.command == "service-task-disable-plan":
            emit(service_task_disable_plan_command(), as_json=args.json)
            return 0
        if args.command == "rollback-drill-report":
            emit(rollback_drill_report_command(), as_json=args.json)
            return 0
        if args.command == "startup-service-inventory":
            emit(startup_service_inventory_command(), as_json=args.json)
            return 0
        if args.command == "system-health-report":
            emit(system_health_report_command(), as_json=args.json)
            return 0
        if args.command == "windows-artifact-layout":
            emit(windows_artifact_layout_command(), as_json=args.json)
            return 0
        if args.command == "windows-artifact-validate":
            payload = windows_artifact_validate_command(Path(args.manifest) if args.manifest else None)
            emit(payload, as_json=args.json)
            return 0 if payload.get("valid", False) else 2
        if args.command == "windows-native-artifacts":
            emit(windows_native_artifacts_command(), as_json=args.json)
            return 0
        if args.command == "windows-inventory":
            emit(windows_inventory_command(), as_json=args.json)
            return 0
        if args.command == "windows-smoke-matrix":
            emit(windows_smoke_matrix_command(), as_json=args.json)
            return 0
        if args.command == "windows-evidence-bundle":
            emit(windows_evidence_bundle_command(), as_json=args.json)
            return 0
        if args.command == "host-policy":
            emit(host_policy_report(validate=args.validate), as_json=args.json)
            return 0
        if args.command == "ai-readiness":
            emit(ai_readiness_command(validate=args.validate), as_json=args.json)
            return 0
        if args.command == "ai-self-test":
            emit(ai_self_test_command(), as_json=args.json)
            return 0
        if args.command == "ai-runbook":
            emit(ai_runbook_command(), as_json=args.json)
            return 0
        if args.command == "workflow-router":
            emit(workflow_router_command(), as_json=args.json)
            return 0
        if args.command == "environment-index":
            emit(environment_index_command(), as_json=args.json)
            return 0
        if args.command == "workflow-decision":
            emit(
                workflow_decision_command(route_id=args.route_id, requested_tool=args.requested_tool, artifacts=args.artifact),
                as_json=args.json,
            )
            return 0
        if args.command == "workflow-trace":
            emit(workflow_trace_command(), as_json=args.json)
            return 0
        if args.command == "policy-simulate":
            plan, raw = load_plan(Path(args.plan_file))
            payload = policy_simulate(
                plan,
                raw,
                execute=args.execute,
                delete_mode=args.delete_mode,
                operation_log=args.operation_log,
                require_plan_context=not args.no_require_plan_context,
                require_confirmation_token=args.require_confirmation_token,
                confirmation_token=args.confirmation_token,
                confirmation_phrase=args.confirmation_phrase,
            )
            emit(payload, as_json=args.json)
            return 0 if payload["validation"]["valid"] else 2
    except Exception as exc:  # noqa: BLE001 - CLI must surface structured failure.
        emit({"error": str(exc), "schema": "cleanwin.error.v1"}, as_json=args.json)
        return 1
    print("unreachable command", file=sys.stderr)
    return 1
