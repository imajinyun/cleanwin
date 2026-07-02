"""Read-only contract exposure matrix and consistency validation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONTRACT_EXPOSURE_MATRIX_SCHEMA = "cleanwin.contract-exposure-matrix.v1"
CONTRACT_EXPOSURE_VALIDATION_SCHEMA = "cleanwin.contract-exposure-validation.v1"

MISSING_SCHEMA_REGISTRY_ENTRY = "MISSING_SCHEMA_REGISTRY_ENTRY"
MISSING_CLI_COMMAND = "MISSING_CLI_COMMAND"
MISSING_AI_TOOLS_PROVIDER = "MISSING_AI_TOOLS_PROVIDER"
MISSING_MCP_RESOURCE = "MISSING_MCP_RESOURCE"
MISSING_DOCS_REFERENCE = "MISSING_DOCS_REFERENCE"
MISSING_WORKFLOW_TRACE_REFERENCE = "MISSING_WORKFLOW_TRACE_REFERENCE"
MISSING_EVIDENCE_BUNDLE_REFERENCE = "MISSING_EVIDENCE_BUNDLE_REFERENCE"

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_SOURCE = REPO_ROOT / "cleanwincli" / "cli.py"
CORE_SOURCE = REPO_ROOT / "cleanwincli" / "core.py"
MCP_SOURCE = REPO_ROOT / "cleanwincli" / "mcp_server.py"
AI_TOOLS_SOURCE = REPO_ROOT / "cleanwincli" / "ai_tools.py"
WORKFLOW_TRACE_SOURCE = REPO_ROOT / "cleanwincli" / "workflow_artifacts.py"
EVIDENCE_BUNDLE_SOURCE = REPO_ROOT / "cleanwincli" / "evidence_bundle.py"
DOC_PATHS = (REPO_ROOT / "docs" / "doc" / "README.md", REPO_ROOT / "docs" / "doc" / "README.CN.md")


@dataclass(frozen=True)
class ContractExposureExpectation:
    contract_id: str
    schemas: tuple[str, ...]
    cli_command: str | None = None
    ai_tools_provider: str | None = None
    mcp_resource: str | None = None
    workflow_trace_schema: str | None = None
    evidence_bundle_ref: str | None = None
    docs_refs: tuple[str, ...] = ()


CONTRACT_EXPOSURE_EXPECTATIONS: tuple[ContractExposureExpectation, ...] = (
    ContractExposureExpectation(
        contract_id="low-risk-cache-readiness",
        schemas=(
            "cleanwin.low-risk-cache-execution-readiness.v1",
            "cleanwin.low-risk-cache-readiness-validation.v1",
            "cleanwin.operation-log-readiness.v1",
            "cleanwin.operation-log-readiness-validation.v1",
        ),
        cli_command="low-risk-cache-readiness",
        ai_tools_provider="low-risk-cache-readiness",
        mcp_resource="cleanwin://engineering/low-risk-cache-readiness",
        workflow_trace_schema="cleanwin.low-risk-cache-readiness-validation.v1",
        evidence_bundle_ref="gate.low-risk-cache-readiness",
        docs_refs=("low-risk-cache-readiness", "cleanwin.low-risk-cache-readiness-validation.v1", "operation-log-readiness"),
    ),
    ContractExposureExpectation(
        contract_id="operation-log-readiness",
        schemas=("cleanwin.operation-log-readiness.v1", "cleanwin.operation-log-readiness-validation.v1"),
        cli_command="operation-log-readiness",
        ai_tools_provider="operation-log-readiness",
        mcp_resource="cleanwin://engineering/operation-log-readiness",
        workflow_trace_schema="cleanwin.operation-log-readiness-validation.v1",
        docs_refs=("operation-log-readiness", "cleanwin.operation-log-readiness-validation.v1"),
    ),
    ContractExposureExpectation(
        contract_id="promotion-gates",
        schemas=("cleanwin.promotion-gates.v1", "cleanwin.promotion-gate-validation.v1"),
        cli_command="promotion-gates",
        ai_tools_provider="promotion-gates",
        evidence_bundle_ref="gate.promotion",
        docs_refs=("promotion-gates", "cleanwin.promotion-gate-validation.v1"),
    ),
    ContractExposureExpectation(
        contract_id="workflow-decision",
        schemas=("cleanwin.workflow-decision.v1",),
        cli_command="workflow-decision",
        ai_tools_provider="workflow-decision",
        mcp_resource="cleanwin://ai/workflow-decision",
        docs_refs=("workflow-decision", "cleanwin://ai/workflow-decision"),
    ),
    ContractExposureExpectation(
        contract_id="workflow-trace",
        schemas=("cleanwin.workflow-trace.v1",),
        cli_command="workflow-trace",
        ai_tools_provider="workflow-trace",
        mcp_resource="cleanwin://ai/workflow-trace",
        docs_refs=("workflow-trace", "cleanwin://ai/workflow-trace"),
    ),
    ContractExposureExpectation(
        contract_id="windows-evidence-bundle",
        schemas=("cleanwin.windows-evidence-bundle.v1", "cleanwin.windows-evidence-bundle-record.v1"),
        cli_command="windows-evidence-bundle",
        ai_tools_provider="windows-evidence-bundle",
        docs_refs=("windows-evidence-bundle", "cleanwin.windows-evidence-bundle.v1"),
    ),
    ContractExposureExpectation(
        contract_id="external-rule-quality",
        schemas=("cleanwin.external-rule-quality-summary.v1",),
        ai_tools_provider="external-rule-translate",
        evidence_bundle_ref="rules.external-quality-summary",
        docs_refs=("external-rule-quality", "cleanwin.external-rule-quality-summary.v1"),
    ),
    ContractExposureExpectation(
        contract_id="native-collector-artifact-validation",
        schemas=("cleanwin.windows-native-artifact-validation.v1",),
        cli_command="windows-artifact-validate",
        ai_tools_provider="windows-artifact-validate",
        docs_refs=("windows-artifact-validation", "cleanwin.windows-native-artifact-validation.v1"),
    ),
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _source_snapshot() -> dict[str, str]:
    docs = "\n".join(_read_text(path) for path in DOC_PATHS)
    return {
        "cli": _read_text(CLI_SOURCE),
        "core": _read_text(CORE_SOURCE),
        "mcp": _read_text(MCP_SOURCE),
        "workflow_trace": _read_text(WORKFLOW_TRACE_SOURCE),
        "evidence_bundle": _read_text(EVIDENCE_BUNDLE_SOURCE),
        "docs": docs,
    }


def _registry_schema_names_from_source() -> set[str]:
    names: set[str] = set()
    source = _read_text(REPO_ROOT / "cleanwincli" / "ai_schema_registry.py")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('("cleanwin.'):
            names.add(stripped.split('"', 2)[1])
    return names


def _provider_names() -> set[str]:
    source = _read_text(AI_TOOLS_SOURCE)
    providers: set[str] = set()
    in_registry = False
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('_AI_TOOLS_REGISTRY'):
            in_registry = True
            continue
        if in_registry:
            if stripped.startswith('}'):
                break
            if stripped.startswith('"') and '":' in stripped:
                providers.add(stripped.removeprefix('"').split('":', 1)[0])
    return providers


def _cli_command_names() -> set[str]:
    source = _read_text(CLI_SOURCE)
    commands: set[str] = set()
    marker = 'subparsers.add_parser("'
    for line in source.splitlines():
        if marker in line:
            commands.add(line.split(marker, 1)[1].split('"', 1)[0])
    return commands


def _mcp_resource_uris() -> set[str]:
    source = _read_text(MCP_SOURCE)
    uris: set[str] = set()
    marker = '"uri": "'
    for line in source.splitlines():
        if marker in line:
            uris.add(line.split(marker, 1)[1].split('"', 1)[0])
    return uris


def _status(value: bool | None) -> str:
    if value is None:
        return "not_applicable"
    return "present" if value else "missing"


def _presence_row(name: str, value: bool | None) -> dict[str, Any]:
    return {"name": name, "status": _status(value), "present": value is True, "required": value is not None}


def _missing_schema_errors(expectation: ContractExposureExpectation, schema_names: set[str]) -> list[dict[str, str]]:
    return [
        {"code": MISSING_SCHEMA_REGISTRY_ENTRY, "contract_id": expectation.contract_id, "detail": schema}
        for schema in expectation.schemas
        if schema not in schema_names
    ]


def _row_errors(row: Mapping[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    contract_id = str(row.get("contract_id") or "")
    for exposure in ("cli_command", "ai_tools_provider", "mcp_resource", "workflow_trace", "evidence_bundle", "docs"):
        value = row.get(exposure)
        if not isinstance(value, Mapping) or value.get("status") != "missing":
            continue
        code = {
            "cli_command": MISSING_CLI_COMMAND,
            "ai_tools_provider": MISSING_AI_TOOLS_PROVIDER,
            "mcp_resource": MISSING_MCP_RESOURCE,
            "workflow_trace": MISSING_WORKFLOW_TRACE_REFERENCE,
            "evidence_bundle": MISSING_EVIDENCE_BUNDLE_REFERENCE,
            "docs": MISSING_DOCS_REFERENCE,
        }[exposure]
        errors.append({"code": code, "contract_id": contract_id, "detail": str(value.get("name") or exposure)})
    return errors


def contract_exposure_matrix(
    expectations: Sequence[ContractExposureExpectation] = CONTRACT_EXPOSURE_EXPECTATIONS,
) -> dict[str, Any]:
    """Return a read-only matrix of contract exposure across CLI, AI, MCP, docs, and evidence refs."""
    from cleanwincli.ai_schema import tool_catalog

    sources = _source_snapshot()
    schema_names = _registry_schema_names_from_source()
    providers = _provider_names()
    commands = _cli_command_names()
    mcp_resources = _mcp_resource_uris()
    catalog_tools = {str(tool["name"]) for tool in tool_catalog()["tools"]}
    rows: list[dict[str, Any]] = []
    for expectation in expectations:
        schema_rows = [_presence_row(schema, schema in schema_names) for schema in expectation.schemas]
        cli_present = None if expectation.cli_command is None else expectation.cli_command in commands and f'args.command == "{expectation.cli_command}"' in sources["cli"]
        provider_present = None if expectation.ai_tools_provider is None else expectation.ai_tools_provider in providers
        mcp_present = None if expectation.mcp_resource is None else expectation.mcp_resource in mcp_resources
        workflow_present = None if expectation.workflow_trace_schema is None else expectation.workflow_trace_schema in sources["workflow_trace"]
        evidence_present = None if expectation.evidence_bundle_ref is None else expectation.evidence_bundle_ref in sources["evidence_bundle"]
        docs_present = all(ref in sources["docs"] for ref in expectation.docs_refs)
        row = {
            "contract_id": expectation.contract_id,
            "schemas": schema_rows,
            "cli_command": _presence_row(expectation.cli_command or "", cli_present),
            "ai_tools_provider": _presence_row(expectation.ai_tools_provider or "", provider_present),
            "mcp_resource": _presence_row(expectation.mcp_resource or "", mcp_present),
            "workflow_trace": _presence_row(expectation.workflow_trace_schema or "", workflow_present),
            "evidence_bundle": _presence_row(expectation.evidence_bundle_ref or "", evidence_present),
            "docs": _presence_row(", ".join(expectation.docs_refs), docs_present),
            "ai_tool_catalog": _presence_row(f"cleanwin_{expectation.cli_command.replace('-', '_')}" if expectation.cli_command else "", None),
        }
        if expectation.cli_command:
            row["ai_tool_catalog"] = _presence_row(f"cleanwin_{expectation.cli_command.replace('-', '_')}", f"cleanwin_{expectation.cli_command.replace('-', '_')}" in catalog_tools)
        rows.append(row)

    errors: list[dict[str, str]] = []
    for expectation, row in zip(expectations, rows, strict=True):
        errors.extend(_missing_schema_errors(expectation, schema_names))
        errors.extend(_row_errors(row))

    return {
        "schema": CONTRACT_EXPOSURE_MATRIX_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "contract_count": len(rows),
        "valid": not errors,
        "rows": rows,
        "summary": {
            "contract_count": len(rows),
            "missing_exposure_count": len(errors),
            "required_schema_count": sum(len(expectation.schemas) for expectation in expectations),
            "mcp_resource_count": sum(1 for expectation in expectations if expectation.mcp_resource),
        },
        "validation": {
            "schema": CONTRACT_EXPOSURE_VALIDATION_SCHEMA,
            "valid": not errors,
            "error_count": len(errors),
            "errors": errors,
        },
        "non_goals": [
            "This matrix does not enable cleanup execution.",
            "Rows marked not_applicable are optional exposure surfaces and are not counted as missing.",
            "This matrix does not run Windows, PowerShell, DISM, registry, AppX, service, task, or cleanup commands.",
            "This matrix only validates contract exposure consistency.",
        ],
    }


def validate_contract_exposure_matrix(matrix: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a contract exposure matrix payload."""
    errors: list[dict[str, str]] = []
    if matrix.get("schema") != CONTRACT_EXPOSURE_MATRIX_SCHEMA:
        errors.append({"code": "INVALID_CONTRACT_EXPOSURE_MATRIX_SCHEMA", "contract_id": "", "detail": str(matrix.get("schema") or "")})
    rows = matrix.get("rows")
    if not isinstance(rows, Iterable) or isinstance(rows, str | bytes):
        rows = []
        errors.append({"code": "INVALID_CONTRACT_EXPOSURE_ROWS", "contract_id": "", "detail": "rows"})
    for row in rows:
        if not isinstance(row, Mapping):
            errors.append({"code": "INVALID_CONTRACT_EXPOSURE_ROW", "contract_id": "", "detail": "row"})
            continue
        contract_id = str(row.get("contract_id") or "")
        schemas = row.get("schemas")
        if not isinstance(schemas, Iterable) or isinstance(schemas, str | bytes):
            errors.append({"code": MISSING_SCHEMA_REGISTRY_ENTRY, "contract_id": contract_id, "detail": "schemas"})
        else:
            for schema in schemas:
                if isinstance(schema, Mapping) and schema.get("status") == "missing":
                    errors.append({"code": MISSING_SCHEMA_REGISTRY_ENTRY, "contract_id": contract_id, "detail": str(schema.get("name") or "")})
        errors.extend(_row_errors(row))
    return {
        "schema": CONTRACT_EXPOSURE_VALIDATION_SCHEMA,
        "valid": not errors,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "error_count": len(errors),
        "errors": errors,
        "safe_to_execute": False,
    }
