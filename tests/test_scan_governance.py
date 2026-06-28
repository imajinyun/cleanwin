from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import Any

from cleanwincli.scan_governance import SCAN_GOVERNANCE_SCHEMA, scan_governance_report, validate_script_boundaries

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
AssertCliProviderSchemaSample = Callable[[str, str], JSONPayload]
AssertSchemaSamples = Callable[[list[str]], dict[str, JSONPayload]]
AssertPayloadSchema = Callable[[JSONPayload, str], JSONPayload]
AssertReadonlyReport = Callable[[JSONPayload, str], JSONPayload]
AssertExecutionDisabled = Callable[..., JSONPayload]
AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertAnyTextContains = Callable[[Sequence[str], str], None]
FieldValues = dict[str, Any]
AssertFieldValues = Callable[[JSONPayload, FieldValues], JSONPayload]


def test_scan_governance_is_read_only_and_release_gated(
    assert_readonly_report: AssertReadonlyReport,
    assert_contains_all: AssertContainsAll,
    assert_any_text_contains: AssertAnyTextContains,
    assert_field_values: AssertFieldValues,
) -> None:
    report = scan_governance_report()

    assert_readonly_report(report, SCAN_GOVERNANCE_SCHEMA)
    assert_field_values(
        report["release_gate"],
        {
            "requires_quality": True,
            "requires_script_boundary_tests": True,
            "blocks_execution_expansion": True,
        },
    )
    assert_contains_all(report["release_gate"]["required_commands"], ["make quality"])
    assert_any_text_contains(report["non_goals"], "does not import external cleaner rules")


def test_scan_budgets_and_external_rule_contract_block_unsafe_imports(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = scan_governance_report()
    by_id = {budget["id"]: budget for budget in report["scan_budgets"]}

    assert_field_values(by_id["default-inspect"], {"max_items": 100})
    assert_field_values(
        by_id["file-report"],
        {
            "max_files_scanned": 2000,
            "max_hash_bytes_per_file": 1048576,
            "permission_error_policy": "aggregate-and-continue",
        },
    )

    contract = report["external_rule_contract"]
    assert_payload_schema(contract, "cleanwin.external-rule-review.v1")
    assert_field_values(contract, {"default_state": "report-only"})
    assert_execution_disabled(contract)
    assert_contains_all(contract["required_source_evidence"], ["license"])
    assert_contains_all(contract["required_safety_evidence"], ["sensitive_exclusions"])
    assert_contains_all(contract["blocked_patterns"], ["raw shell command strings"])
    assert_contains_all(contract["promotion_requirements"], ["promotion-gate approval"])


def test_script_boundary_contract_constrains_cleanup_and_collector_writes(
    assert_payload_schema: AssertPayloadSchema,
    assert_execution_disabled: AssertExecutionDisabled,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    report = scan_governance_report()
    contract = report["script_boundary_contract"]

    assert_payload_schema(contract, "cleanwin.script-boundary-contract.v1")
    assert_execution_disabled(contract)
    assert_field_values(
        contract,
        {
            "default_state": "read-only-or-local-artifact-only",
            "makefile.managed_venv": ".venv",
            "native_collector.allowed_write_root": "operator-provided ArtifactRoot",
        },
    )
    assert_contains_all(contract["makefile"]["cleanup_targets"], [".pytest_cache", "__pycache__", "build", "dist"])
    assert_contains_all(contract["makefile"]["protected_targets"], [".venv", ".aiflow", ".harness", ".git", "aiflow.yaml"])
    assert_contains_all(
        contract["native_collector"]["required_root_checks"],
        [
            "ArtifactRoot must not be empty",
            "ArtifactRoot must not be a filesystem root",
            "ArtifactRoot parent must exist",
            "Artifact relative path must not be rooted",
            "Artifact relative path must stay under ArtifactRoot",
            "all artifacts are written below ArtifactRoot",
            "external command output paths must be resolved through Resolve-ArtifactPath",
        ],
    )
    assert_contains_all(contract["native_collector"]["forbidden_command_fragments"], ["reg.exe import", "RestoreHealth"])
    assert_contains_all(
        contract["native_collector"]["allowed_command_fragments"],
        [
            "Get-AppxPackage -AllUsers",
            "reg.exe export",
            "schtasks.exe /Query",
            "winget.exe export",
            "dism.exe /Online /Cleanup-Image /AnalyzeComponentStore",
        ],
    )
    assert_contains_all(
        contract["native_collector"]["allowed_write_api_lines"],
        [
            "$Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $FullPath -Encoding UTF8",
            "$Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8",
        ],
    )


def test_script_boundary_validation_reports_current_repo_state(
    assert_payload_schema: AssertPayloadSchema,
    assert_field_values: AssertFieldValues,
) -> None:
    report = scan_governance_report()
    validation = assert_payload_schema(report["script_boundary_validation"], "cleanwin.script-boundary-validation.v1")

    assert_field_values(validation, {"valid": True, "violation_count": 0})
    assert_field_values(report["summary"], {"script_boundary_valid": True})


def test_script_boundary_validation_flags_drift(
    assert_payload_schema: AssertPayloadSchema,
    assert_contains_all: AssertContainsAll,
    assert_field_values: AssertFieldValues,
) -> None:
    contract = scan_governance_report()["script_boundary_contract"]
    validation = assert_payload_schema(
        validate_script_boundaries(
            makefile_text="pytest:\n\t$(DEV_PYTHON) -m pytest -q\n\tpython -c \"import shutil; shutil.rmtree('.venv')\"",
            native_collector_text="\n".join(
                [
                    "function Resolve-ArtifactRoot { throw 'ArtifactRoot must not be empty' }",
                    "$OutFile = Join-Path $Root.FullName $Export.Path",
                    "reg.exe import backup.reg",
                    "Remove-Item -LiteralPath $FullPath -Force",
                    "Set-Content -LiteralPath C:\\temp\\artifact.json -Value $Payload",
                ]
            ),
            contract=contract,
        ),
        "cleanwin.script-boundary-validation.v1",
    )

    assert_field_values(validation, {"valid": False})
    assert_contains_all(
        {violation["code"] for violation in validation["violations"]},
        [
            "MISSING_MAKE_TARGET",
            "PROTECTED_TARGET_IN_CLEANUP",
            "MISSING_ARTIFACT_ROOT_GUARD",
            "FORBIDDEN_COMMAND_FRAGMENT",
            "MISSING_ARTIFACT_PATH_RESOLUTION",
            "DIRECT_ARTIFACT_ROOT_PATH_JOIN",
            "MISSING_LITERAL_ARTIFACT_WRITE",
            "UNREVIEWED_NATIVE_COLLECTOR_COMMAND",
            "DIRECT_ARTIFACT_WRITE_API",
        ],
    )


def test_cli_provider_and_schema_registry_expose_scan_governance(
    assert_cli_provider_schema_sample: AssertCliProviderSchemaSample,
    assert_schema_samples: AssertSchemaSamples,
) -> None:
    assert_cli_provider_schema_sample("scan-governance", SCAN_GOVERNANCE_SCHEMA)
    assert_schema_samples(
        [
            "cleanwin.external-rule-review.v1",
            "cleanwin.script-boundary-contract.v1",
            "cleanwin.script-boundary-validation.v1",
        ]
    )
