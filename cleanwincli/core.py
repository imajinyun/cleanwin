"""CleanWin core capabilities contract."""

from __future__ import annotations

from typing import Any

from cleanwincli import __version__
from cleanwincli.ai_schema import CONFIRMATION_PHRASE
from cleanwincli.models import (
    CATEGORY_APP_LEFTOVERS,
    CATEGORY_BROWSER_CACHE,
    CATEGORY_DEV_CACHE,
    CATEGORY_PACKAGE_CACHE,
    CATEGORY_TEMP,
    EXECUTABLE_CACHE_CATEGORIES,
    PLAN_SCHEMA,
)


def capabilities() -> dict[str, Any]:
    return {
        "tool": "cleanwin",
        "version": __version__,
        "default_dry_run": True,
        "plan_schema": PLAN_SCHEMA,
        "execution_requires_execute_flag": True,
        "deletion_exit": "cleanwincli.delete_ops.safe_delete",
        "default_delete_mode": "recycle",
        "fail_closed": [
            "non-windows recycle execution without CLEANWIN_TEST_MODE",
            "symlink or junction candidates",
            "protected Windows paths",
            "protected user data paths",
            "operation log write failures",
        ],
        "safe_categories": [CATEGORY_APP_LEFTOVERS, CATEGORY_BROWSER_CACHE, CATEGORY_DEV_CACHE, CATEGORY_PACKAGE_CACHE, CATEGORY_TEMP],
        "executable_cache_categories": sorted(EXECUTABLE_CACHE_CATEGORIES),
        "read_only_categories": [
            "browser-cache-report",
            "backup-delete-contract",
            "browser-profile-inventory",
            "docker-report",
            "file-report",
            "large-files",
            "permanent-delete-denial",
            "registry-report",
            "scan-governance",
            "startup-report",
            "system-health-report",
            "disable-revert-contract",
            "visual-studio-report",
            "windows-inventory",
            "windows-report",
            "wsl-report",
        ],
        "never_auto_execute": ["registry-clean", "startup-disable", "windows-component-clean"],
        "promotion_gates_schema": "cleanwin.promotion-gates.v1",
        "ai": {
            "tool_catalog_schema": "cleanwin.ai-tools.v1",
            "workflow_router_schema": "cleanwin.workflow-router.v1",
            "host_policy_schema": "cleanwin.ai-host-policy.v1",
            "destructive_tool": "cleanwin_execute_plan",
            "confirmation_phrase": CONFIRMATION_PHRASE,
        },
    }
