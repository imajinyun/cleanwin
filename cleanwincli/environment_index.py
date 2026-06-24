"""Read-only environment capability index for CleanWin hosts."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from shutil import which
from typing import Any

from cleanwincli import __version__

ENVIRONMENT_INDEX_SCHEMA = "cleanwin.environment-index.v1"


def _command_status(name: str) -> dict[str, Any]:
    path = which(name)
    return {
        "name": name,
        "available": path is not None,
        "path": path,
        "version": None,
        "verification_command": [name, "--version"],
        "executes_by_report": False,
    }


def environment_index_report() -> dict[str, Any]:
    os_name = os.name
    is_windows = os_name == "nt"
    test_mode = os.environ.get("CLEANWIN_TEST_MODE") == "1"
    default_operation_log = Path.home() / ".cleanwin" / "operations.jsonl"
    return {
        "schema": ENVIRONMENT_INDEX_SCHEMA,
        "destructive": False,
        "dry_run": True,
        "executes_system_commands": False,
        "platform": {
            "os_name": os_name,
            "system": platform.system(),
            "release": platform.release(),
            "platform": platform.platform(),
            "is_windows": is_windows,
            "python_version": platform.python_version(),
            "python_executable": sys.executable,
        },
        "cleanwin": {
            "version": __version__,
            "test_mode": test_mode,
            "entrypoints": [
                _command_status("cleanwin"),
                _command_status("cleanwin-mcp"),
            ],
        },
        "capabilities": [
            {
                "id": "read-only-inventory",
                "available": True,
                "reason": "pure-python-readonly-reports",
                "routes": ["discover-capabilities", "read-only-inventory"],
            },
            {
                "id": "planning",
                "available": True,
                "reason": "plan-validation-and-review-are-non-destructive",
                "routes": ["plan-cleanup", "validate-and-review", "dry-run-execution"],
            },
            {
                "id": "windows-recycle-execution",
                "available": is_windows or test_mode,
                "reason": "windows-host" if is_windows else ("test-mode" if test_mode else "non-windows-fail-closed"),
                "routes": ["recycle-execution"],
            },
            {
                "id": "mcp-structured-tools",
                "available": True,
                "reason": "mcp-server-builds-argv-from-registered-tool-schemas",
                "routes": ["discover-capabilities", "read-only-inventory", "plan-cleanup"],
            },
        ],
        "operation_log": {
            "default_path": str(default_operation_log),
            "parent": str(default_operation_log.parent),
            "parent_exists": default_operation_log.parent.exists(),
            "write_checked": False,
            "required_for_execution": True,
        },
        "fail_closed": [
            "non-windows recycle execution without CLEANWIN_TEST_MODE",
            "permanent delete route is not exposed",
            "raw command arguments are denied by AI/MCP policy",
        ],
        "non_goals": [
            "This report does not install tools.",
            "This report does not create directories or write operation logs.",
            "This report does not execute cleanup.",
        ],
    }
