"""Compatibility shim: re-exports from ai_schema_registry and ai_schema_samples.

This module is preserved for backwards compatibility. New code should import
directly from ai_schema_registry or ai_schema_samples.
"""

from __future__ import annotations

from cleanwincli.ai_schema_registry import (
    LATEST_PLAN_SCHEMA,
    SUPPORTED_PLAN_SCHEMAS,
    SchemaEntry,
    negotiate_plan_schema,
    schema_registry,
)
from cleanwincli.ai_schema_samples import schema_sample

__all__ = [
    "LATEST_PLAN_SCHEMA",
    "SUPPORTED_PLAN_SCHEMAS",
    "SchemaEntry",
    "negotiate_plan_schema",
    "schema_registry",
    "schema_sample",
]
