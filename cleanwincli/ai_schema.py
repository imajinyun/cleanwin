"""Machine-readable AI tool schemas for safe cleanwin integrations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

DEFAULT_OPERATION_LOG = "~/.cleanwin/operations.jsonl"
CONFIRMATION_PHRASE = "确认执行 cleanwin 清理"


def string_schema(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def integer_schema(description: str) -> dict[str, Any]:
    return {"type": "integer", "description": description}


def number_schema(description: str) -> dict[str, Any]:
    return {"type": "number", "description": description}


def bool_schema(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description}


def category_array_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": "cleanwin category keys selected from capabilities output.",
        "minItems": 1,
    }


def rule_id_array_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional cleanwin collector/report rule IDs to filter candidates or read-only findings.",
    }


def object_schema(properties: dict[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


AI_TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "cleanwin_capabilities",
        "description": "Describe cleanwin commands, safety guardrails, AI contracts, and supported categories.",
        "risk": "readonly",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema({}),
        "argv_template": ["cleanwin", "--json", "capabilities"],
    },
    {
        "name": "cleanwin_workflow_router",
        "description": "Route user intent to the safest CleanWin workflow before selecting cleanup tools.",
        "risk": "readonly",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema({}),
        "argv_template": ["cleanwin", "--json", "workflow-router"],
    },
    {
        "name": "cleanwin_inspect",
        "description": "Preview cleanup candidates without deleting files.",
        "risk": "readonly",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema(
            {
                "categories": category_array_schema(),
                "rule_ids": rule_id_array_schema(),
                "older_than_days": number_schema("Only show candidates older than this many days."),
                "max_items": integer_schema("Maximum number of candidates to return."),
            }
        ),
        "argv_template": ["cleanwin", "--json", "inspect"],
    },
    {
        "name": "cleanwin_generate_plan",
        "description": "Generate a reusable non-destructive cleanup plan.",
        "risk": "planning",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema(
            {
                "categories": category_array_schema(),
                "rule_ids": rule_id_array_schema(),
                "older_than_days": number_schema("Only plan candidates older than this many days."),
                "max_items": integer_schema("Maximum planned candidate count."),
                "output": string_schema("Optional path to write the generated plan JSON file."),
            },
            required=("categories",),
        ),
        "argv_template": ["cleanwin", "--json", "plan"],
    },
    {
        "name": "cleanwin_validate_plan",
        "description": "Validate a cleanwin cleanup plan before dry-run or execution.",
        "risk": "planning",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema(
            {
                "plan_file": string_schema("Path to a cleanwin plan JSON file."),
                "require_plan_context": bool_schema("Require home/user context matching before execution."),
            },
            required=("plan_file",),
        ),
        "argv_template": ["cleanwin", "--json", "validate-plan"],
    },
    {
        "name": "cleanwin_review_plan",
        "description": "Summarize a cleanwin plan for human/AI review before policy simulation or execution.",
        "risk": "planning",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema(
            {
                "plan_file": string_schema("Path to a cleanwin plan JSON file."),
                "require_plan_context": bool_schema("Require home/user context matching in the review validation."),
            },
            required=("plan_file",),
        ),
        "argv_template": ["cleanwin", "--json", "review-plan"],
    },
    {
        "name": "cleanwin_policy_simulate",
        "description": "Simulate host-side policy decisions for a cleanwin plan without deleting files.",
        "risk": "planning",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema(
            {
                "plan_file": string_schema("Path to a cleanwin plan JSON file."),
                "execute": bool_schema("Simulate destructive execution intent."),
                "delete_mode": {"type": "string", "enum": ["recycle", "permanent"], "default": "recycle"},
                "operation_log": string_schema("JSONL operation log path for the simulated execution."),
                "require_plan_context": bool_schema("Require home/user context match before execution."),
                "require_confirmation_token": bool_schema("Require a matching dry-run confirmation token."),
                "confirmation_token": string_schema("Token generated by a matching cleanwin dry-run."),
                "confirmation_phrase": string_schema("Exact human confirmation phrase used when simulating execution."),
            },
            required=("plan_file",),
        ),
        "argv_template": ["cleanwin", "--json", "policy-simulate"],
    },
    {
        "name": "cleanwin_dry_run_plan",
        "description": "Run a cleanup plan in dry-run mode with recycle routing selected for the eventual execution path.",
        "risk": "dry-run",
        "auto_call_allowed": True,
        "requires_confirmation": False,
        "parameters": object_schema(
            {
                "plan_file": string_schema("Path to a cleanwin plan JSON file."),
                "trash_root": string_schema("Optional recycle sandbox path used in test mode."),
            },
            required=("plan_file",),
        ),
        "argv_template": ["cleanwin", "--json", "execute-plan"],
    },
    {
        "name": "cleanwin_execute_plan",
        "description": "Execute a validated cleanwin plan using recycle mode and explicit human confirmation gates.",
        "risk": "destructive",
        "auto_call_allowed": False,
        "requires_confirmation": True,
        "parameters": object_schema(
            {
                "plan_file": string_schema("Path to a cleanwin plan JSON file."),
                "delete_mode": {"type": "string", "enum": ["recycle"]},
                "operation_log": string_schema("JSONL operation log path for execution."),
                "require_plan_context": bool_schema("Require home/user context matching before execution."),
                "confirmation_phrase": string_schema("Exact human confirmation phrase required before execution."),
                "confirmation_token": string_schema("Token produced by a matching dry-run."),
                "trash_root": string_schema("Optional recycle sandbox path used only in test mode."),
            },
            required=("plan_file", "delete_mode", "operation_log", "require_plan_context", "confirmation_phrase", "confirmation_token"),
        ),
        "argv_template": ["cleanwin", "--json", "execute-plan"],
    },
)


def _tool_contract(tool: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool["description"],
        "risk": tool["risk"],
        "auto_call_allowed": tool["auto_call_allowed"],
        "requires_confirmation": tool["requires_confirmation"],
        "parameters": tool["parameters"],
        "argv_template": tool["argv_template"],
    }


def tool_catalog() -> dict[str, Any]:
    return {
        "schema": "cleanwin.ai-tools.v1",
        "tool_count": len(AI_TOOL_DEFINITIONS),
        "tools": [_tool_contract(tool) for tool in AI_TOOL_DEFINITIONS],
    }


def openai_functions_export() -> dict[str, Any]:
    functions = []
    for tool in AI_TOOL_DEFINITIONS:
        functions.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
        )
    return {"schema": "cleanwin.ai-openai-functions.v1", "functions": functions}


def anthropic_tools_export() -> dict[str, Any]:
    tools = []
    for tool in AI_TOOL_DEFINITIONS:
        tools.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
        )
    return {"schema": "cleanwin.ai-anthropic-tools.v1", "tools": tools}


def provider_export_parity() -> dict[str, Any]:
    catalog_names = [tool["name"] for tool in AI_TOOL_DEFINITIONS]
    openai_names = [item["function"]["name"] for item in openai_functions_export()["functions"]]
    anthropic_names = [item["name"] for item in anthropic_tools_export()["tools"]]
    return {
        "schema": "cleanwin.ai-provider-export-parity.v1",
        "valid": catalog_names == openai_names == anthropic_names,
        "catalog_names": catalog_names,
        "openai_names": openai_names,
        "anthropic_names": anthropic_names,
    }


def _validate_json_value(value: Any, schema: Mapping[str, Any], path: str) -> list[str]:
    expected_type = schema.get("type")
    violations: list[str] = []
    if "enum" in schema and value not in schema.get("enum", []):
        violations.append(f"{path} must be one of {schema['enum']}")
        return violations
    if expected_type == "object":
        if not isinstance(value, Mapping):
            return [f"{path} must be an object"]
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if isinstance(required, Sequence) and not isinstance(required, str):
            for field in required:
                if field not in value:
                    violations.append(f"{path}.{field} is required")
        if isinstance(properties, Mapping):
            allowed = {str(key) for key in properties}
            if schema.get("additionalProperties") is False:
                for field in sorted(str(key) for key in value if str(key) not in allowed):
                    violations.append(f"{path}.{field} is not allowed")
            for field, field_schema in properties.items():
                if field in value and isinstance(field_schema, Mapping):
                    violations.extend(_validate_json_value(value[field], field_schema, f"{path}.{field}"))
        return violations
    if expected_type == "array":
        if not isinstance(value, list):
            return [f"{path} must be an array"]
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            violations.append(f"{path} must contain at least {min_items} item(s)")
        item_schema = schema.get("items", {})
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                violations.extend(_validate_json_value(item, item_schema, f"{path}[{index}]"))
        return violations
    if expected_type == "string" and not isinstance(value, str):
        return [f"{path} must be a string"]
    if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return [f"{path} must be an integer"]
    if expected_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return [f"{path} must be a number"]
    if expected_type == "boolean" and not isinstance(value, bool):
        return [f"{path} must be a boolean"]
    return violations


def validate_tool_arguments(tool: Mapping[str, Any], arguments: Mapping[str, Any]) -> dict[str, Any]:
    schema = tool.get("parameters", {})
    violations = _validate_json_value(arguments, schema, "arguments") if isinstance(schema, Mapping) else ["tool parameters must be an object schema"]
    return {
        "schema": "cleanwin.ai-tool-argument-validation.v1",
        "tool": str(tool.get("name") or ""),
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
    }


def validate_ai_schema() -> dict[str, Any]:
    violations: list[str] = []
    names = [str(tool.get("name")) for tool in AI_TOOL_DEFINITIONS]
    if len(set(names)) != len(names):
        violations.append("tool names must be unique")
    for tool in AI_TOOL_DEFINITIONS:
        if str(tool.get("risk")) == "destructive":
            if tool.get("auto_call_allowed") is not False:
                violations.append(f"{tool['name']} must deny auto_call_allowed")
            if tool.get("requires_confirmation") is not True:
                violations.append(f"{tool['name']} must require confirmation")
        if not isinstance(tool.get("argv_template"), list) or not tool["argv_template"]:
            violations.append(f"{tool['name']} must define argv_template")
    parity = provider_export_parity()
    if not parity["valid"]:
        violations.append("provider export parity must be valid")
    return {
        "schema": "cleanwin.ai-schema-validation.v1",
        "valid": not violations,
        "violation_count": len(violations),
        "violations": violations,
        "parity": parity,
    }
