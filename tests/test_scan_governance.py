from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cleanwincli.ai_versioning import schema_registry, schema_sample
from cleanwincli.scan_governance import SCAN_GOVERNANCE_SCHEMA, scan_governance_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]


def test_scan_governance_is_read_only_and_release_gated() -> None:
    report = scan_governance_report()

    assert report["schema"] == SCAN_GOVERNANCE_SCHEMA
    assert report["destructive"] is False
    assert report["executes_system_commands"] is False
    assert report["release_gate"]["requires_quality"] is True
    assert "make quality" in report["release_gate"]["required_commands"]
    assert report["release_gate"]["blocks_execution_expansion"] is True
    assert any("does not import external cleaner rules" in item for item in report["non_goals"])


def test_scan_budgets_and_external_rule_contract_block_unsafe_imports() -> None:
    report = scan_governance_report()
    by_id = {budget["id"]: budget for budget in report["scan_budgets"]}

    assert by_id["default-inspect"]["max_items"] == 100
    assert by_id["file-report"]["max_files_scanned"] == 2000
    assert by_id["file-report"]["max_hash_bytes_per_file"] == 1048576
    assert by_id["file-report"]["permission_error_policy"] == "aggregate-and-continue"

    contract = report["external_rule_contract"]
    assert contract["schema"] == "cleanwin.external-rule-review.v1"
    assert contract["default_state"] == "report-only"
    assert contract["execution_enabled"] is False
    assert "license" in contract["required_source_evidence"]
    assert "sensitive_exclusions" in contract["required_safety_evidence"]
    assert "raw shell command strings" in contract["blocked_patterns"]
    assert "promotion-gate approval" in contract["promotion_requirements"]


def test_cli_provider_and_schema_registry_expose_scan_governance(cleanwin_json: CleanWinJSON) -> None:
    cli = cleanwin_json("scan-governance")
    assert cli["schema"] == SCAN_GOVERNANCE_SCHEMA

    provider = cleanwin_json("ai-tools", "--provider", "scan-governance")
    assert provider["schema"] == SCAN_GOVERNANCE_SCHEMA

    registry = schema_registry()
    names = {entry["name"] for entry in registry["entries"]}
    assert SCAN_GOVERNANCE_SCHEMA in names
    assert "cleanwin.external-rule-review.v1" in names
    governance_sample = schema_sample(SCAN_GOVERNANCE_SCHEMA)
    contract_sample = schema_sample("cleanwin.external-rule-review.v1")
    assert governance_sample is not None
    assert contract_sample is not None
    assert governance_sample["schema"] == SCAN_GOVERNANCE_SCHEMA
    assert contract_sample["schema"] == "cleanwin.external-rule-review.v1"
