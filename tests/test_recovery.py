from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.recovery import RECOVERY_READINESS_SCHEMA, recovery_readiness_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def test_recovery_readiness_is_non_destructive_and_declares_gates() -> None:
    report = recovery_readiness_report()

    assert report["schema"] == RECOVERY_READINESS_SCHEMA
    assert report["destructive"] is False
    assert report["dry_run"] is True
    assert report["executes_system_commands"] is False
    assert report["ready_for_recovery_planning"] is True
    assert report["ready_for_system_execution"] is False
    assert report["execution_gate"]["requires_recovery_snapshot"] is True
    assert report["execution_gate"]["system_execution_enabled"] is False


def test_recovery_readiness_declares_snapshot_specs() -> None:
    report = recovery_readiness_report()
    specs = {item["id"]: item for item in report["snapshot_specs"]}

    assert "system-restore-point" in specs
    assert "registry-export" in specs
    assert "service-state" in specs
    assert "scheduled-task-state" in specs
    assert "appx-inventory" in specs
    assert "installed-app-inventory" in specs
    assert all(not spec["executed_by_report"] for spec in specs.values())
    assert "registry-change" in specs["registry-export"]["required_before"]


def test_cli_exposes_recovery_readiness(cleanwin_json: CleanWinJSON) -> None:
    payload = cleanwin_json("recovery-readiness")

    assert payload["schema"] == RECOVERY_READINESS_SCHEMA
    assert payload["executes_system_commands"] is False


def test_ai_tools_provider_exposes_recovery_readiness(cleanwin_json: CleanWinJSON) -> None:
    payload = cleanwin_json("ai-tools", "--provider", "recovery-readiness")

    assert payload["schema"] == RECOVERY_READINESS_SCHEMA
