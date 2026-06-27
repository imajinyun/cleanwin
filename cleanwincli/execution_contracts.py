"""Non-executable execution expansion contracts."""

from __future__ import annotations

from typing import Any

DISABLE_REVERT_CONTRACT_SCHEMA = "cleanwin.disable-revert-contract.v1"
BACKUP_DELETE_CONTRACT_SCHEMA = "cleanwin.backup-delete-contract.v1"
PERMANENT_DELETE_DENIAL_SCHEMA = "cleanwin.permanent-delete-denial.v1"
REGISTRY_PRIVACY_PLAN_SCHEMA = "cleanwin.registry-privacy-plan.v1"
REGISTRY_PRIVACY_CHANGE_SCHEMA = "cleanwin.registry-privacy-change.v1"
REGISTRY_PRIVACY_REVERT_SCHEMA = "cleanwin.registry-privacy-revert.v1"
REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA = "cleanwin.registry-privacy-plan-validation.v1"
APPX_REMOVAL_PLAN_SCHEMA = "cleanwin.appx-removal-plan.v1"
APPX_REMOVAL_CHANGE_SCHEMA = "cleanwin.appx-removal-change.v1"
APPX_REMOVAL_REVERT_SCHEMA = "cleanwin.appx-removal-revert.v1"
APPX_REMOVAL_PLAN_VALIDATION_SCHEMA = "cleanwin.appx-removal-plan-validation.v1"
SERVICE_TASK_DISABLE_PLAN_SCHEMA = "cleanwin.service-task-disable-plan.v1"
SERVICE_DISABLE_CHANGE_SCHEMA = "cleanwin.service-disable-change.v1"
TASK_DISABLE_CHANGE_SCHEMA = "cleanwin.scheduled-task-disable-change.v1"
SERVICE_TASK_REVERT_SCHEMA = "cleanwin.service-task-revert.v1"
SERVICE_TASK_DISABLE_PLAN_VALIDATION_SCHEMA = "cleanwin.service-task-disable-plan-validation.v1"
ROLLBACK_DRILL_REPORT_SCHEMA = "cleanwin.rollback-drill-report.v1"
ROLLBACK_DRILL_CASE_SCHEMA = "cleanwin.rollback-drill-case.v1"
ROLLBACK_DRILL_VALIDATION_SCHEMA = "cleanwin.rollback-drill-validation.v1"

_PROTECTED_SERVICE_TASK_TOKENS = (
    "microsoft",
    "windows",
    "defender",
    "security",
    "driver",
    "kernel",
    "wuauserv",
    "bits",
    "store",
)
_PROTECTED_SERVICE_TASK_PHRASES = (
    "windows update",
    "microsoft update",
    "windows installer",
)

_THIRD_PARTY_UPDATER_TOKENS = ("updater", "update", "helper", "agent", "launcher")


def _rollback_drill_case(
    *,
    drill_id: str,
    target_type: str,
    source_schema: str,
    snapshot_refs: list[str],
    planned_action: list[str],
    restore_command: list[str],
    required_metadata: dict[str, Any],
    verification_steps: list[str],
) -> dict[str, Any]:
    return {
        "schema": ROLLBACK_DRILL_CASE_SCHEMA,
        "id": drill_id,
        "target_type": target_type,
        "source_plan_schema": source_schema,
        "fixture_only": True,
        "snapshot_refs": snapshot_refs,
        "drill_chain": ["snapshot", "simulate-action", "verify-after-simulation", "simulate-rollback", "verify-after-rollback"],
        "planned_action": planned_action,
        "restore_command": restore_command,
        "required_metadata": required_metadata,
        "verification_steps": verification_steps,
        "executes_system_commands": False,
        "execution_enabled": False,
        "safe_to_execute": False,
    }


def rollback_drill_report() -> dict[str, Any]:
    drills = [
        _rollback_drill_case(
            drill_id="rollback-drill.registry-privacy-import",
            target_type="registry-privacy",
            source_schema=REGISTRY_PRIVACY_PLAN_SCHEMA,
            snapshot_refs=["snapshot://registry/privacy.telemetry.allow-telemetry.reg"],
            planned_action=["reg.exe", "add", r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection", "/v", "AllowTelemetry", "/d", "0"],
            restore_command=["reg.exe", "import", "<export-file.reg>"],
            required_metadata={
                "hive": "HKLM",
                "subkey_path": r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                "value_name": "AllowTelemetry",
                "previous_value": "3",
                "registry_export_ref": "snapshot://registry/privacy.telemetry.allow-telemetry.reg",
            },
            verification_steps=["compare previous registry value", "verify import command references registry export"],
        ),
        _rollback_drill_case(
            drill_id="rollback-drill.scheduled-task-xml-restore",
            target_type="scheduled-task",
            source_schema=SERVICE_TASK_DISABLE_PLAN_SCHEMA,
            snapshot_refs=["snapshot://scheduled-task/Example/Updater.xml"],
            planned_action=["schtasks", "/Change", "/TN", r"\Example\Updater", "/Disable"],
            restore_command=["schtasks", "/Create", "/TN", r"\Example\Updater", "/XML", "<task-export.xml>", "/F"],
            required_metadata={
                "task_name": r"\Example\Updater",
                "previous_state": "Ready",
                "task_xml_or_export_ref": "snapshot://scheduled-task/Example/Updater.xml",
                "restore_command": "schtasks /Create /XML <task-export.xml>",
            },
            verification_steps=["compare task XML identity", "verify restored task state"],
        ),
        _rollback_drill_case(
            drill_id="rollback-drill.service-start-type-restore",
            target_type="service",
            source_schema=SERVICE_TASK_DISABLE_PLAN_SCHEMA,
            snapshot_refs=["snapshot://service/ExampleUpdater.reg"],
            planned_action=["sc.exe", "config", "ExampleUpdater", "start=", "disabled"],
            restore_command=["reg.exe", "import", "<service-export.reg>"],
            required_metadata={
                "service_name": "ExampleUpdater",
                "previous_status": "Running",
                "previous_start_type": "Automatic",
                "snapshot_artifact_ref": "snapshot://service/ExampleUpdater.reg",
                "restore_command": "reg.exe import <service-export.reg>",
            },
            verification_steps=["compare sc.exe qc output", "verify service start type restored"],
        ),
        _rollback_drill_case(
            drill_id="rollback-drill.appx-restore-metadata",
            target_type="appx-package",
            source_schema=APPX_REMOVAL_PLAN_SCHEMA,
            snapshot_refs=["snapshot://appx/Microsoft.BingWeather_8wekyb3d8bbwe.json"],
            planned_action=["powershell.exe", "Remove-AppxPackage", "-Package", "Microsoft.BingWeather_1.0.0.0_x64__8wekyb3d8bbwe"],
            restore_command=["powershell.exe", "Add-AppxPackage", "-Register", r"<InstallLocation>\AppxManifest.xml"],
            required_metadata={
                "package_name": "Microsoft.BingWeather_1.0.0.0_x64__8wekyb3d8bbwe",
                "package_family_name": "Microsoft.BingWeather_8wekyb3d8bbwe",
                "previous_registration_state": "registered",
                "install_location": r"C:\Program Files\WindowsApps\Microsoft.BingWeather_1.0.0.0_x64__8wekyb3d8bbwe",
                "restore_command": r"Add-AppxPackage -Register <InstallLocation>\AppxManifest.xml",
            },
            verification_steps=["compare package family identity", "verify restore command references install location"],
        ),
    ]
    validation = validate_rollback_drills({"schema": ROLLBACK_DRILL_REPORT_SCHEMA, "drills": drills})
    return {
        "schema": ROLLBACK_DRILL_REPORT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "fixture_only": True,
        "drills": drills,
        "summary": {
            "drill_count": len(drills),
            "execution_enabled_count": sum(1 for drill in drills if drill["execution_enabled"]),
            "fixture_only_count": sum(1 for drill in drills if drill["fixture_only"]),
            "target_types": sorted({str(drill["target_type"]) for drill in drills}),
        },
        "validation": validation,
        "execution_gate": {
            "rollback_drill_execution_enabled": False,
            "requires_snapshot_refs": True,
            "requires_restore_command": True,
            "requires_required_metadata": True,
            "requires_post_rollback_verification": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not import registry files.",
            "This report does not recreate scheduled tasks.",
            "This report does not change service start types.",
            "This report does not reinstall AppX packages.",
        ],
    }


def validate_rollback_drills(report: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if report.get("schema") != ROLLBACK_DRILL_REPORT_SCHEMA:
        violations.append({"path": "schema", "code": "INVALID_SCHEMA", "message": f"schema must be {ROLLBACK_DRILL_REPORT_SCHEMA}"})
    drills = report.get("drills")
    if not isinstance(drills, list):
        violations.append({"path": "drills", "code": "MISSING_DRILLS", "message": "drills must be a list"})
        drills = []
    for index, drill in enumerate(drills):
        if not isinstance(drill, dict):
            violations.append({"path": f"drills.{index}", "code": "INVALID_DRILL", "message": "drill must be an object"})
            continue
        prefix = f"drills.{index}"
        if drill.get("schema") != ROLLBACK_DRILL_CASE_SCHEMA:
            violations.append({"path": f"{prefix}.schema", "code": "INVALID_DRILL_SCHEMA", "message": f"drill schema must be {ROLLBACK_DRILL_CASE_SCHEMA}"})
        if drill.get("fixture_only") is not True:
            violations.append({"path": f"{prefix}.fixture_only", "code": "FIXTURE_ONLY_REQUIRED", "message": "rollback drills must remain fixture-only"})
        if drill.get("execution_enabled") is not False or drill.get("executes_system_commands") is not False:
            violations.append({"path": f"{prefix}.execution_enabled", "code": "EXECUTION_MUST_STAY_DISABLED", "message": "rollback drills must not execute commands"})
        for field, code in (
            ("snapshot_refs", "SNAPSHOT_REFS_REQUIRED"),
            ("restore_command", "RESTORE_COMMAND_REQUIRED"),
            ("required_metadata", "ROLLBACK_METADATA_REQUIRED"),
            ("verification_steps", "POST_ROLLBACK_VERIFICATION_REQUIRED"),
        ):
            if not drill.get(field):
                violations.append({"path": f"{prefix}.{field}", "code": code, "message": f"{field} is required"})
    return {
        "schema": ROLLBACK_DRILL_VALIDATION_SCHEMA,
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def _service_task_block_reasons(item: dict[str, Any], *, item_type: str) -> list[str]:
    text = " ".join(
        str(item.get(field) or "")
        for field in (
            "name",
            "display_name",
            "publisher",
            "author",
            "binary_path",
            "task_to_run",
            "service_type",
            "task_folder",
        )
    ).lower()
    reasons: list[str] = []
    if any(token in text for token in _PROTECTED_SERVICE_TASK_TOKENS) or any(phrase in text for phrase in _PROTECTED_SERVICE_TASK_PHRASES):
        reasons.append("protected_vendor_or_core_surface")
    if item_type == "service" and item.get("is_driver") is True:
        reasons.append("driver_service")
    if item_type == "service" and item.get("start_type_classification") in {"boot-or-system"}:
        reasons.append("boot_or_system_start")
    if item_type == "task" and str(item.get("run_as_user") or "").upper() in {"SYSTEM", "LOCAL SYSTEM"}:
        reasons.append("system_principal")
    if item.get("target_status") not in {"exists", "missing"}:
        reasons.append("target_status_unresolved")
    if not any(token in text for token in _THIRD_PARTY_UPDATER_TOKENS):
        reasons.append("not_curated_third_party_updater")
    return reasons


def _service_disable_change(service: dict[str, Any]) -> dict[str, Any]:
    name = str(service.get("name") or "")
    snapshot_ref = f"snapshot://service/{name}.reg"
    return {
        "schema": SERVICE_DISABLE_CHANGE_SCHEMA,
        "id": f"service-disable.change.{name}",
        "target_action": "service-disable",
        "service_name": name,
        "display_name": str(service.get("display_name") or ""),
        "current_status": str(service.get("status") or ""),
        "current_start_type": str(service.get("start_type") or ""),
        "target_start_type": "disabled",
        "dependencies": list(service.get("dependencies") or []),
        "trigger_start": service.get("trigger_start"),
        "recovery_actions": list(service.get("recovery_actions") or []),
        "snapshot_refs": [snapshot_ref],
        "required_snapshot_commands": [
            ["sc.exe", "qc", name],
            ["reg.exe", "export", rf"HKLM\SYSTEM\CurrentControlSet\Services\{name}", "<service-export.reg>", "/y"],
        ],
        "restore_command": ["reg.exe", "import", "<service-export.reg>"],
        "rollback": {
            "schema": SERVICE_TASK_REVERT_SCHEMA,
            "target_type": "service",
            "object_name": name,
            "snapshot_refs": [snapshot_ref],
            "previous_state": str(service.get("status") or ""),
            "previous_start_type": str(service.get("start_type") or ""),
            "restore_command": ["reg.exe", "import", "<service-export.reg>"],
            "verification": ["query sc.exe qc", "query service status"],
        },
        "execution_enabled": False,
        "auto_executable": False,
        "safe_to_execute": False,
    }


def _task_disable_change(task: dict[str, Any]) -> dict[str, Any]:
    task_name = str(task.get("task_path") or task.get("name") or "")
    snapshot_name = task_name.strip("\\").replace("\\", "/")
    snapshot_ref = f"snapshot://scheduled-task/{snapshot_name}.xml"
    return {
        "schema": TASK_DISABLE_CHANGE_SCHEMA,
        "id": f"scheduled-task-disable.change.{task_name}",
        "target_action": "scheduled-task-disable",
        "task_name": task_name,
        "current_state": str(task.get("state") or ""),
        "run_as_user": str(task.get("run_as_user") or ""),
        "run_level": str(task.get("run_level") or ""),
        "task_to_run": str(task.get("task_to_run") or ""),
        "snapshot_refs": [snapshot_ref],
        "required_snapshot_commands": [["schtasks", "/Query", "/TN", task_name, "/XML"]],
        "restore_command": ["schtasks", "/Create", "/TN", task_name, "/XML", "<task-export.xml>", "/F"],
        "rollback": {
            "schema": SERVICE_TASK_REVERT_SCHEMA,
            "target_type": "scheduled-task",
            "object_name": task_name,
            "snapshot_refs": [snapshot_ref],
            "previous_state": str(task.get("state") or ""),
            "restore_command": ["schtasks", "/Create", "/TN", task_name, "/XML", "<task-export.xml>", "/F"],
            "verification": ["query scheduled task state", "compare task XML identity"],
        },
        "execution_enabled": False,
        "auto_executable": False,
        "safe_to_execute": False,
    }


def service_task_disable_plan_report(source_report: dict[str, Any] | None = None) -> dict[str, Any]:
    if source_report is None:
        from cleanwincli.startup_inventory import startup_service_inventory_report

        source_report = startup_service_inventory_report()
    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for service in source_report.get("services", []):
        if not isinstance(service, dict):
            continue
        reasons = _service_task_block_reasons(service, item_type="service")
        if reasons:
            blocked.append({"target_type": "service", "name": service.get("name", ""), "blocked_reasons": reasons, "execution_enabled": False, "safe_to_execute": False})
            continue
        changes.append(_service_disable_change(service))
    for task in source_report.get("scheduled_tasks", []):
        if not isinstance(task, dict):
            continue
        reasons = _service_task_block_reasons(task, item_type="task")
        if reasons:
            blocked.append({"target_type": "scheduled-task", "name": task.get("task_path", task.get("name", "")), "blocked_reasons": reasons, "execution_enabled": False, "safe_to_execute": False})
            continue
        changes.append(_task_disable_change(task))
    return {
        "schema": SERVICE_TASK_DISABLE_PLAN_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "source_report_schema": source_report.get("schema"),
        "plan_state": "simulation-only",
        "changes": changes,
        "blocked_targets": blocked,
        "summary": {
            "change_count": len(changes),
            "blocked_target_count": len(blocked),
            "service_change_count": sum(1 for change in changes if change["schema"] == SERVICE_DISABLE_CHANGE_SCHEMA),
            "scheduled_task_change_count": sum(1 for change in changes if change["schema"] == TASK_DISABLE_CHANGE_SCHEMA),
            "execution_enabled_count": sum(1 for change in changes if change["execution_enabled"]),
        },
        "validation": validate_service_task_disable_plan({"schema": SERVICE_TASK_DISABLE_PLAN_SCHEMA, "changes": changes}),
        "execution_gate": {
            "service_task_disable_execution_enabled": False,
            "requires_service_registry_export": True,
            "requires_service_state_snapshot": True,
            "requires_task_xml_export": True,
            "requires_dependency_trigger_recovery_review": True,
            "requires_restore_command": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not stop or disable services.",
            "This report does not disable scheduled tasks.",
            "This report does not modify service registry keys or task XML.",
        ],
    }


def validate_service_task_disable_plan(plan: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if plan.get("schema") != SERVICE_TASK_DISABLE_PLAN_SCHEMA:
        violations.append({"path": "schema", "code": "INVALID_SCHEMA", "message": f"schema must be {SERVICE_TASK_DISABLE_PLAN_SCHEMA}"})
    changes = plan.get("changes")
    if not isinstance(changes, list):
        violations.append({"path": "changes", "code": "MISSING_CHANGES", "message": "changes must be a list"})
        changes = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            violations.append({"path": f"changes.{index}", "code": "INVALID_CHANGE", "message": "change must be an object"})
            continue
        prefix = f"changes.{index}"
        schema = change.get("schema")
        if schema not in {SERVICE_DISABLE_CHANGE_SCHEMA, TASK_DISABLE_CHANGE_SCHEMA}:
            violations.append({"path": f"{prefix}.schema", "code": "INVALID_CHANGE_SCHEMA", "message": "change schema must be service or scheduled-task disable"})
        if not change.get("snapshot_refs"):
            violations.append({"path": f"{prefix}.snapshot_refs", "code": "SNAPSHOT_REQUIRED", "message": "snapshot reference is required"})
        if not change.get("restore_command"):
            violations.append({"path": f"{prefix}.restore_command", "code": "RESTORE_COMMAND_REQUIRED", "message": "restore command is required"})
        rollback = change.get("rollback")
        if not isinstance(rollback, dict) or rollback.get("schema") != SERVICE_TASK_REVERT_SCHEMA:
            violations.append({"path": f"{prefix}.rollback", "code": "ROLLBACK_PLAN_REQUIRED", "message": "rollback metadata is required"})
        if change.get("execution_enabled") is not False:
            violations.append({"path": f"{prefix}.execution_enabled", "code": "EXECUTION_MUST_STAY_DISABLED", "message": "service/task disable plan must remain simulation-only"})
        if schema == SERVICE_DISABLE_CHANGE_SCHEMA:
            if not change.get("service_name"):
                violations.append({"path": f"{prefix}.service_name", "code": "SERVICE_NAME_REQUIRED", "message": "service name is required"})
            for field in ("dependencies", "trigger_start", "recovery_actions"):
                if field not in change:
                    violations.append({"path": f"{prefix}.{field}", "code": "SERVICE_REVIEW_FIELD_REQUIRED", "message": f"{field} review is required"})
        if schema == TASK_DISABLE_CHANGE_SCHEMA:
            if not change.get("task_name"):
                violations.append({"path": f"{prefix}.task_name", "code": "TASK_NAME_REQUIRED", "message": "task name is required"})
            if not any("XML" in " ".join(command) for command in change.get("required_snapshot_commands", []) if isinstance(command, list)):
                violations.append({"path": f"{prefix}.required_snapshot_commands", "code": "TASK_XML_EXPORT_REQUIRED", "message": "scheduled task XML export is required"})
    return {
        "schema": SERVICE_TASK_DISABLE_PLAN_VALIDATION_SCHEMA,
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def _registry_privacy_change_from_finding(finding: dict[str, Any]) -> dict[str, Any]:
    evidence = finding.get("change_evidence", {})
    expected_values = evidence.get("expected_private_values", [])
    target_value = str(expected_values[0]) if isinstance(expected_values, list) and expected_values else ""
    hive = str(evidence.get("hive") or "")
    subkey_path = str(evidence.get("subkey_path") or "")
    value_name = str(evidence.get("value_name") or "")
    observed_value = str(evidence.get("observed_value") or "")
    registry_export_ref = f"snapshot://registry/{finding.get('id')}.reg"
    return {
        "schema": REGISTRY_PRIVACY_CHANGE_SCHEMA,
        "id": f"registry-privacy.change.{finding['id']}",
        "source_finding_id": finding["id"],
        "target_action": "registry-privacy-change",
        "risk": finding.get("risk", "medium"),
        "state": "simulated",
        "hive": hive,
        "subkey_path": subkey_path,
        "value_name": value_name,
        "previous_value": observed_value,
        "target_value": target_value,
        "registry_export_ref": registry_export_ref,
        "required_export_command": evidence.get("required_export_command", ["reg.exe", "export", rf"{hive}\{subkey_path}", "<export-file.reg>", "/y"]),
        "restore_command": ["reg.exe", "import", "<export-file.reg>"],
        "managed_device_detection": {
            "required": True,
            "signals": ["domain_joined", "mdm_enrolled", "policy_key_owned_by_organization"],
            "state": "not-evaluated",
        },
        "owner_review": {
            "required": True,
            "policy_owner": "unknown",
            "review_state": "required",
        },
        "dry_run_confirmation": {
            "required": True,
            "token_ref": "cleanwin.ai-confirmation-summary.v1.confirmation_token",
            "provided": False,
        },
        "rollback": {
            "schema": REGISTRY_PRIVACY_REVERT_SCHEMA,
            "registry_export_ref": registry_export_ref,
            "previous_value": observed_value,
            "restore_command": ["reg.exe", "import", "<export-file.reg>"],
            "verification": ["query exact registry value after restore", "compare previous value"],
        },
        "execution_enabled": False,
        "auto_executable": False,
        "safe_to_execute": False,
    }


def registry_privacy_change_plan_report(source_report: dict[str, Any] | None = None) -> dict[str, Any]:
    if source_report is None:
        from cleanwincli.debloat_privacy import debloat_privacy_report

        source_report = debloat_privacy_report()
    findings = [
        finding
        for finding in source_report.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("kind") == "registry-policy"
        and finding.get("state") == "review-recommended"
        and isinstance(finding.get("change_evidence"), dict)
    ]
    changes = [_registry_privacy_change_from_finding(finding) for finding in findings]
    return {
        "schema": REGISTRY_PRIVACY_PLAN_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "source_report_schema": source_report.get("schema"),
        "plan_state": "simulation-only",
        "changes": changes,
        "summary": {
            "change_count": len(changes),
            "execution_enabled_count": sum(1 for change in changes if change["execution_enabled"]),
            "requires_registry_export_count": len(changes),
            "requires_owner_review_count": len(changes),
            "requires_dry_run_token_count": len(changes),
        },
        "validation": validate_registry_privacy_change_plan({"schema": REGISTRY_PRIVACY_PLAN_SCHEMA, "changes": changes}),
        "execution_gate": {
            "registry_privacy_execution_enabled": False,
            "requires_registry_export": True,
            "requires_previous_value": True,
            "requires_managed_device_detection": True,
            "requires_policy_owner_review": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not write registry values.",
            "This report does not import registry rollback files.",
            "This report does not bypass managed-device policy ownership.",
        ],
    }


def validate_registry_privacy_change_plan(plan: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if plan.get("schema") != REGISTRY_PRIVACY_PLAN_SCHEMA:
        violations.append({"path": "schema", "code": "INVALID_SCHEMA", "message": f"schema must be {REGISTRY_PRIVACY_PLAN_SCHEMA}"})
    changes = plan.get("changes")
    if not isinstance(changes, list):
        violations.append({"path": "changes", "code": "MISSING_CHANGES", "message": "changes must be a list"})
        changes = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            violations.append({"path": f"changes.{index}", "code": "INVALID_CHANGE", "message": "change must be an object"})
            continue
        prefix = f"changes.{index}"
        required_fields = {
            "schema": REGISTRY_PRIVACY_CHANGE_SCHEMA,
            "hive": None,
            "subkey_path": None,
            "value_name": None,
            "previous_value": None,
            "target_value": None,
            "registry_export_ref": None,
            "restore_command": None,
        }
        for field, expected in required_fields.items():
            value = change.get(field)
            if expected is not None and value != expected:
                violations.append({"path": f"{prefix}.{field}", "code": "INVALID_FIELD", "message": f"{field} must be {expected}"})
            elif expected is None and (value is None or value == "" or value == []):
                violations.append({"path": f"{prefix}.{field}", "code": "MISSING_FIELD", "message": f"{field} is required"})
        if change.get("execution_enabled") is not False:
            violations.append({"path": f"{prefix}.execution_enabled", "code": "EXECUTION_MUST_STAY_DISABLED", "message": "registry privacy plan must remain simulation-only"})
        managed_detection = change.get("managed_device_detection")
        if not isinstance(managed_detection, dict) or managed_detection.get("required") is not True:
            violations.append({"path": f"{prefix}.managed_device_detection", "code": "MANAGED_DEVICE_DETECTION_REQUIRED", "message": "managed device detection is required"})
        owner_review = change.get("owner_review")
        if not isinstance(owner_review, dict) or owner_review.get("required") is not True:
            violations.append({"path": f"{prefix}.owner_review", "code": "OWNER_REVIEW_REQUIRED", "message": "policy owner review is required"})
        dry_run = change.get("dry_run_confirmation")
        if not isinstance(dry_run, dict) or dry_run.get("required") is not True:
            violations.append({"path": f"{prefix}.dry_run_confirmation", "code": "DRY_RUN_TOKEN_REQUIRED", "message": "dry-run confirmation token is required"})
        rollback = change.get("rollback")
        if not isinstance(rollback, dict) or rollback.get("schema") != REGISTRY_PRIVACY_REVERT_SCHEMA:
            violations.append({"path": f"{prefix}.rollback", "code": "ROLLBACK_PLAN_REQUIRED", "message": "rollback metadata is required"})
    return {
        "schema": REGISTRY_PRIVACY_PLAN_VALIDATION_SCHEMA,
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def _appx_item_identity(item: dict[str, Any]) -> dict[str, str]:
    name = str(item.get("Name") or item.get("name") or item.get("DisplayName") or "")
    package_full_name = str(item.get("PackageFullName") or item.get("package_full_name") or item.get("PackageName") or name)
    package_family_name = str(item.get("PackageFamilyName") or item.get("package_family_name") or "")
    publisher = str(item.get("Publisher") or item.get("publisher") or item.get("PublisherId") or "")
    return {
        "name": name,
        "package_full_name": package_full_name,
        "package_family_name": package_family_name,
        "publisher": publisher,
    }


def _appx_block_reasons(item: dict[str, Any], classification: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    category = classification.get("category")
    if category != "consumer-app":
        reasons.append(f"category:{category}")
    if classification.get("protected_by_default") is True:
        reasons.append("protected_by_default")
    if classification.get("dependency") is True:
        reasons.append("dependency_or_framework")
    if classification.get("non_removable") is True:
        reasons.append("non_removable")
    if classification.get("provisioned_state") is True:
        reasons.append("provisioned_package")
    if not _appx_item_identity(item)["package_full_name"]:
        reasons.append("missing_package_identity")
    return reasons


def _appx_removal_change_from_item(item: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    identity = _appx_item_identity(item)
    snapshot_ref = f"snapshot://appx/{identity['package_full_name']}.json"
    return {
        "schema": APPX_REMOVAL_CHANGE_SCHEMA,
        "id": f"appx-removal.change.{identity['name']}",
        "target_action": "appx-per-user-remove",
        "scope": "per-user",
        "package": identity,
        "classification": classification,
        "snapshot_refs": [snapshot_ref],
        "remove_command": ["powershell.exe", "Remove-AppxPackage", "-Package", identity["package_full_name"]],
        "restore_command": ["powershell.exe", "Add-AppxPackage", "-Register", "<InstallLocation>\\AppxManifest.xml"],
        "rollback": {
            "schema": APPX_REMOVAL_REVERT_SCHEMA,
            "package_full_name": identity["package_full_name"],
            "package_family_name": identity["package_family_name"],
            "snapshot_refs": [snapshot_ref],
            "restore_command": ["powershell.exe", "Add-AppxPackage", "-Register", "<InstallLocation>\\AppxManifest.xml"],
            "verification": ["query Get-AppxPackage for current user", "compare package family name"],
        },
        "execution_enabled": False,
        "auto_executable": False,
        "safe_to_execute": False,
    }


def appx_removal_plan_report(source_report: dict[str, Any] | None = None) -> dict[str, Any]:
    if source_report is None:
        from cleanwincli.windows_inventory import windows_inventory_report

        source_report = windows_inventory_report()
    changes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for section in source_report.get("sections", []):
        if not isinstance(section, dict) or section.get("id") not in {"appx-packages", "provisioned-appx-packages"}:
            continue
        for item in section.get("items", []):
            if not isinstance(item, dict):
                continue
            classification = item.get("cleanwin_classification")
            if not isinstance(classification, dict):
                continue
            reasons = _appx_block_reasons(item, classification)
            if reasons:
                identity = _appx_item_identity(item)
                blocked.append(
                    {
                        "schema": "cleanwin.appx-removal-block.v1",
                        "package": identity,
                        "classification": classification,
                        "blocked_reasons": reasons,
                        "execution_enabled": False,
                        "safe_to_execute": False,
                    }
                )
                continue
            changes.append(_appx_removal_change_from_item(item, classification))
    return {
        "schema": APPX_REMOVAL_PLAN_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "source_report_schema": source_report.get("schema"),
        "plan_state": "simulation-only",
        "scope": "per-user",
        "changes": changes,
        "blocked_packages": blocked,
        "summary": {
            "change_count": len(changes),
            "blocked_package_count": len(blocked),
            "execution_enabled_count": sum(1 for change in changes if change["execution_enabled"]),
            "per_user_scope_count": sum(1 for change in changes if change["scope"] == "per-user"),
        },
        "validation": validate_appx_removal_plan({"schema": APPX_REMOVAL_PLAN_SCHEMA, "changes": changes}),
        "execution_gate": {
            "appx_removal_execution_enabled": False,
            "requires_appx_snapshot": True,
            "requires_consumer_app_classification": True,
            "requires_non_framework_non_system": True,
            "requires_non_provisioned_scope": True,
            "requires_restore_command": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not remove AppX packages.",
            "This report does not remove provisioned packages.",
            "This report does not remove framework, system, dependency, non-removable, OEM, or unknown packages.",
        ],
    }


def validate_appx_removal_plan(plan: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    if plan.get("schema") != APPX_REMOVAL_PLAN_SCHEMA:
        violations.append({"path": "schema", "code": "INVALID_SCHEMA", "message": f"schema must be {APPX_REMOVAL_PLAN_SCHEMA}"})
    changes = plan.get("changes")
    if not isinstance(changes, list):
        violations.append({"path": "changes", "code": "MISSING_CHANGES", "message": "changes must be a list"})
        changes = []
    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            violations.append({"path": f"changes.{index}", "code": "INVALID_CHANGE", "message": "change must be an object"})
            continue
        prefix = f"changes.{index}"
        if change.get("schema") != APPX_REMOVAL_CHANGE_SCHEMA:
            violations.append({"path": f"{prefix}.schema", "code": "INVALID_CHANGE_SCHEMA", "message": f"schema must be {APPX_REMOVAL_CHANGE_SCHEMA}"})
        if change.get("scope") != "per-user":
            violations.append({"path": f"{prefix}.scope", "code": "PER_USER_SCOPE_REQUIRED", "message": "AppX removal plan is limited to per-user scope"})
        classification = change.get("classification")
        if not isinstance(classification, dict) or classification.get("category") != "consumer-app":
            violations.append({"path": f"{prefix}.classification", "code": "CONSUMER_APP_REQUIRED", "message": "only consumer-app classifications may be planned"})
        elif (
            classification.get("protected_by_default") is True
            or classification.get("dependency") is True
            or classification.get("non_removable") is True
            or classification.get("provisioned_state") is True
        ):
            violations.append({"path": f"{prefix}.classification", "code": "PROTECTED_PACKAGE_BLOCKED", "message": "framework/system/provisioned/dependency packages are blocked"})
        package = change.get("package")
        if not isinstance(package, dict) or not package.get("package_full_name"):
            violations.append({"path": f"{prefix}.package.package_full_name", "code": "PACKAGE_IDENTITY_REQUIRED", "message": "package_full_name is required"})
        if not change.get("snapshot_refs"):
            violations.append({"path": f"{prefix}.snapshot_refs", "code": "APPX_SNAPSHOT_REQUIRED", "message": "snapshot reference is required"})
        rollback = change.get("rollback")
        if not isinstance(rollback, dict) or rollback.get("schema") != APPX_REMOVAL_REVERT_SCHEMA:
            violations.append({"path": f"{prefix}.rollback", "code": "ROLLBACK_PLAN_REQUIRED", "message": "rollback metadata is required"})
        if not change.get("restore_command"):
            violations.append({"path": f"{prefix}.restore_command", "code": "RESTORE_COMMAND_REQUIRED", "message": "restore command is required"})
        if change.get("execution_enabled") is not False:
            violations.append({"path": f"{prefix}.execution_enabled", "code": "EXECUTION_MUST_STAY_DISABLED", "message": "AppX removal plan must remain simulation-only"})
    return {
        "schema": APPX_REMOVAL_PLAN_VALIDATION_SCHEMA,
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def disable_revert_contract_report() -> dict[str, Any]:
    action_contracts = [
        {
            "id": "disable-revert.startup-entry",
            "target_action": "startup-disable",
            "source_report": "cleanwin.startup-service-inventory.v1",
            "required_snapshots": ["registry-export", "startup-folder-snapshot"],
            "required_rollback_metadata": ["startup_location", "entry_name", "previous_command", "restore_action", "snapshot_artifact_ref"],
            "required_review_evidence": ["publisher", "signature_status", "target_path", "target_status", "target_exists", "risk"],
            "revert_plan_schema": "cleanwin.revert.startup-entry.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "disable-revert.service",
            "target_action": "service-disable-or-stop",
            "source_report": "cleanwin.startup-service-inventory.v1",
            "required_snapshots": ["system-restore-point", "service-state", "service-registry-export"],
            "required_rollback_metadata": ["service_name", "previous_status", "previous_start_type", "restore_command", "snapshot_artifact_ref"],
            "required_review_evidence": [
                "display_name",
                "publisher",
                "signature_status",
                "target_path",
                "target_status",
                "start_type_classification",
                "dependencies",
                "trigger_start",
                "recovery_actions",
                "risk",
            ],
            "revert_plan_schema": "cleanwin.revert.service.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "disable-revert.scheduled-task",
            "target_action": "scheduled-task-disable",
            "source_report": "cleanwin.startup-service-inventory.v1",
            "required_snapshots": ["system-restore-point", "scheduled-task-state", "scheduled-task-xml-export"],
            "required_rollback_metadata": ["task_name", "previous_state", "task_xml_or_export_ref", "restore_command", "snapshot_artifact_ref"],
            "required_review_evidence": [
                "task_to_run",
                "publisher",
                "target_path",
                "target_status",
                "target_exists",
                "run_as_user",
                "run_level",
                "xml_snapshot_required",
                "risk",
            ],
            "revert_plan_schema": "cleanwin.revert.scheduled-task.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "disable-revert.policy",
            "target_action": "policy-change",
            "source_report": "cleanwin.debloat-privacy-report.v1",
            "required_snapshots": ["registry-export", "system-restore-point"],
            "required_rollback_metadata": ["hive", "subkey_path", "value_name", "previous_value", "registry_export_ref"],
            "required_review_evidence": ["policy_owner", "observed_value", "expected_value", "managed_device_state"],
            "revert_plan_schema": "cleanwin.revert.policy.v1",
            "execution_enabled": False,
            "auto_executable": False,
        },
    ]
    return {
        "schema": DISABLE_REVERT_CONTRACT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "action_contracts": action_contracts,
        "summary": {
            "contract_count": len(action_contracts),
            "execution_enabled_count": sum(1 for item in action_contracts if item["execution_enabled"]),
            "requires_snapshot_count": sum(1 for item in action_contracts if item["required_snapshots"]),
        },
        "execution_gate": {
            "disable_revert_execution_enabled": False,
            "requires_snapshot_artifacts": True,
            "requires_revert_plan": True,
            "requires_policy_simulation": True,
            "requires_matching_dry_run_token": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not disable startup entries.",
            "This report does not stop or disable services.",
            "This report does not disable scheduled tasks or change policies.",
        ],
    }


def backup_delete_contract_report() -> dict[str, Any]:
    backup_scopes = [
        {
            "id": "backup-delete.file-tree",
            "target_surface": "reviewed file or directory tree",
            "allowed_categories": ["app-leftovers", "future-backup-delete-only"],
            "required_identity": ["cleanwin.filesystem-identity.v1", "canonical_path", "file_id_or_stat_tuple", "size_bytes", "modified_ns"],
            "required_backup_metadata": ["backup_path", "backup_identity", "source_identity", "created_at", "verification_digest"],
            "required_audit_refs": ["plan_source_fingerprint", "dry_run_confirmation_token", "operation_log_ref"],
            "execution_enabled": False,
            "auto_executable": False,
        },
        {
            "id": "backup-delete.registry-key",
            "target_surface": "registry key export before registry mutation",
            "allowed_categories": ["future-registry-change"],
            "required_identity": ["hive", "subkey_path", "value_names", "observed_values"],
            "required_backup_metadata": ["registry_export_ref", "export_command", "export_digest", "previous_values"],
            "required_audit_refs": ["policy_owner_review", "plan_source_fingerprint", "operation_log_ref"],
            "execution_enabled": False,
            "auto_executable": False,
        },
    ]
    return {
        "schema": BACKUP_DELETE_CONTRACT_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "backup_scopes": backup_scopes,
        "summary": {
            "scope_count": len(backup_scopes),
            "execution_enabled_count": sum(1 for item in backup_scopes if item["execution_enabled"]),
            "requires_backup_verification_count": len(backup_scopes),
        },
        "execution_gate": {
            "backup_delete_execution_enabled": False,
            "requires_pre_delete_backup": True,
            "requires_backup_verification": True,
            "requires_identity_match_before_delete": True,
            "requires_operation_log": True,
            "requires_restore_drill_evidence": True,
            "ai_auto_call_allowed": False,
        },
        "non_goals": [
            "This report does not copy backup data.",
            "This report does not delete source data after backup.",
            "This report does not replace recycle-mode execution for ordinary low-risk cleanup.",
        ],
    }


def permanent_delete_denial_report() -> dict[str, Any]:
    return {
        "schema": PERMANENT_DELETE_DENIAL_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "capability": {
            "id": "permanent-delete",
            "risk": "critical",
            "default_state": "denied",
            "execution_enabled": False,
            "ai_auto_call_allowed": False,
            "mcp_tool_exposed": False,
            "allowed_delete_modes": ["recycle"],
            "denied_delete_modes": ["permanent"],
        },
        "required_future_gates": [
            "separate explicit permanent-delete command surface",
            "stronger human confirmation phrase",
            "non-AI auto-call policy",
            "backup or recovery proof",
            "operation log with irreversible-delete marker",
            "release-specific destructive capability review",
        ],
        "current_enforcement": {
            "plan_validation_rejects_permanent": True,
            "execute_plan_passes_allow_permanent_false": True,
            "ai_host_policy_requires_recycle": True,
            "mcp_execute_schema_allows_recycle_only": True,
            "delete_ops_requires_allow_permanent_true": True,
        },
        "summary": {
            "execution_enabled_count": 0,
            "denied_mode_count": 1,
            "future_gate_count": 6,
        },
        "non_goals": [
            "This report does not enable permanent deletion.",
            "This report does not add permanent deletion to AI or MCP tools.",
            "This report does not relax recycle-mode execution requirements.",
        ],
    }
