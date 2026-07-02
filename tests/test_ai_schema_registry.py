"""Unit tests for AI schema registry and plan negotiation."""

from __future__ import annotations

from cleanwincli.ai_schema_registry import (
    LATEST_PLAN_SCHEMA,
    SUPPORTED_PLAN_SCHEMAS,
    negotiate_plan_schema,
    schema_registry,
)


class TestSchemaRegistry:
    def test_returns_registry_payload(self) -> None:
        result = schema_registry()
        assert result["schema"] == "cleanwin.ai-schema-registry.v1"
        assert result["latest_plan_schema"] == LATEST_PLAN_SCHEMA
        assert result["supported_plan_schemas"] == list(SUPPORTED_PLAN_SCHEMAS)
        assert result["schema_count"] > 0
        assert len(result["entries"]) == result["schema_count"]

    def test_entries_have_required_fields(self) -> None:
        result = schema_registry()
        for entry in result["entries"]:
            assert "name" in entry
            assert "version" in entry
            assert "module" in entry
            assert "stability" in entry
            assert "kind" in entry
            assert "producer" in entry
            assert "consumers" in entry
            assert entry["latest"] is True

    def test_samples_included_for_known_schemas(self) -> None:
        result = schema_registry()
        assert "samples" in result
        assert "cleanwin.inspect.v1" in result["samples"]
        assert "cleanwin.plan.v1" in result["samples"]
        assert "cleanwin.execute.v1" in result["samples"]

    def test_no_duplicate_schema_names(self) -> None:
        result = schema_registry()
        names = [entry["name"] for entry in result["entries"]]
        assert len(names) == len(set(names))


class TestNegotiatePlanSchema:
    def test_none_requested_uses_latest(self) -> None:
        result = negotiate_plan_schema(None)
        assert result["accepted"] is True
        assert result["requested_schema"] == LATEST_PLAN_SCHEMA
        assert result["selected_schema"] == LATEST_PLAN_SCHEMA

    def test_empty_string_uses_latest(self) -> None:
        result = negotiate_plan_schema("")
        assert result["accepted"] is True
        assert result["selected_schema"] == LATEST_PLAN_SCHEMA

    def test_supported_schema_accepted(self) -> None:
        result = negotiate_plan_schema(LATEST_PLAN_SCHEMA)
        assert result["accepted"] is True
        assert result["selected_schema"] == LATEST_PLAN_SCHEMA
        assert result["error"] is None

    def test_unsupported_schema_rejected(self) -> None:
        result = negotiate_plan_schema("cleanwin.nonexistent.v99")
        assert result["accepted"] is False
        assert result["selected_schema"] is None
        assert "Unsupported plan schema" in result["error"]

    def test_returns_validate_plan_schema(self) -> None:
        result = negotiate_plan_schema(None)
        assert result["schema"] == "cleanwin.validate-plan.v1"

    def test_supported_plan_schemas_listed(self) -> None:
        result = negotiate_plan_schema(None)
        assert LATEST_PLAN_SCHEMA in result["supported_plan_schemas"]
