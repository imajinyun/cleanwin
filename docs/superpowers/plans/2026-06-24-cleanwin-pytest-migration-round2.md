# CleanWin Pytest Migration Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue migrating remaining unittest-style CleanWin tests to idiomatic pytest without a large, risky rewrite of the biggest CLI test file.

**Architecture:** Reuse `tests/conftest.py` as the shared pytest support layer, extend it only where existing tests need environment-aware CLI calls, then migrate medium and small `unittest.TestCase` files to top-level pytest functions. Keep `tests/test_cli.py` for a later dedicated split because it is still a large scenario suite.

**Tech Stack:** Python 3.10+, pytest 8, Ruff, mypy, project `.venv`, aiflow queue orchestration.

---

## Unit-Test Workflow Checkpoints

Step1 status: completed. `bits-unit-test-gen` preparation produced `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.raeuPuK4Cq`.

Step2 status: completed. `LANG=python`; project convention is pytest-first and venv-first; `pyproject.toml` configures pytest and dev dependencies.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "environment-aware cleanwin helpers",
      "locator": "tests/conftest.py fixtures",
      "source": "explicit",
      "reason": "remaining identity and AI contract tests need shared CLI helpers that accept env overrides",
      "hunks": []
    },
    {
      "file_path": "tests/test_rule_catalog.py",
      "target_type": "file",
      "symbol": "rule catalog tests",
      "locator": "RuleCatalogTests",
      "source": "explicit",
      "reason": "small pure unit test file can be fully converted to pytest functions and pytest.raises",
      "hunks": []
    },
    {
      "file_path": "tests/test_identity.py",
      "target_type": "file",
      "symbol": "identity tests",
      "locator": "IdentityTests",
      "source": "explicit",
      "reason": "temporary directories, CLI env overrides, skip behavior, and RuntimeError checks map directly to pytest fixtures",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_readiness.py",
      "target_type": "file",
      "symbol": "AI readiness tests",
      "locator": "AIReadinessTests",
      "source": "explicit",
      "reason": "provider matrix should become pytest parametrization and shared cleanwin_json calls",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_contracts.py",
      "target_type": "file",
      "symbol": "AI contract tests",
      "locator": "AIContractTests",
      "source": "explicit",
      "reason": "schema/tool contract tests are medium-sized and benefit from native pytest assertions and tmp_path",
      "hunks": []
    },
    {
      "file_path": "tests/test_windows_integration.py",
      "target_type": "file",
      "symbol": "Windows integration tests",
      "locator": "WindowsIntegrationTests",
      "source": "explicit",
      "reason": "skip decorators and temp directories should use pytest.mark.skipif and tmp_path",
      "hunks": []
    },
    {
      "file_path": "tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "remaining MCP TestCase methods",
      "locator": "CleanWinMCPServerTests",
      "source": "explicit",
      "reason": "the file already has pytest resource tests; remaining class methods can be converted without touching production code",
      "hunks": []
    }
  ],
  "diff_context": null,
  "fallback_notes": "tests/test_cli.py remains out of scope for this round because it needs a dedicated scenario fixture split."
}
```

Step4 status: completed.

```json
{
  "BUG_MAP": []
}
```

Filtered candidates: this is a test maintainability migration. No production defect was proven by the remaining unittest style.

---

## Task 1: Extend Shared Pytest CLI Helpers

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_identity.py`

- [x] Add environment override support to `run_cleanwin` and `cleanwin_json`.
- [x] Validate with `.venv/bin/python -m pytest tests/test_identity.py -q`.

## Task 2: Migrate Rule Catalog and Identity Tests

**Files:**
- Modify: `tests/test_rule_catalog.py`
- Modify: `tests/test_identity.py`

- [x] Convert `RuleCatalogTests` to top-level pytest functions.
- [x] Convert `IdentityTests` to top-level pytest functions using `tmp_path`, `pytest.skip`, and `pytest.raises`.
- [x] Validate with `.venv/bin/python -m pytest tests/test_rule_catalog.py tests/test_identity.py -q`.

## Task 3: Migrate AI Readiness and AI Contract Tests

**Files:**
- Modify: `tests/test_ai_readiness.py`
- Modify: `tests/test_ai_contracts.py`

- [x] Convert readiness tests to top-level pytest functions.
- [x] Convert provider alias loop to `pytest.mark.parametrize`.
- [x] Convert AI contract tests to top-level pytest functions and shared CLI helpers.
- [x] Validate with `.venv/bin/python -m pytest tests/test_ai_readiness.py tests/test_ai_contracts.py -q`.

## Task 4: Migrate Windows Integration and Remaining MCP Tests

**Files:**
- Modify: `tests/test_windows_integration.py`
- Modify: `tests/test_mcp_server.py`

- [x] Convert Windows integration skips to `pytest.mark.skipif`.
- [x] Convert remaining `CleanWinMCPServerTests` methods to pytest functions.
- [x] Use `tmp_path` for MCP plan tests.
- [x] Validate with `.venv/bin/python -m pytest tests/test_windows_integration.py tests/test_mcp_server.py -q`.

## Task 5: Final Validation and Queue Evidence

**Files:**
- Modify if needed: `docs/superpowers/plans/2026-06-24-cleanwin-pytest-migration-round2.md`

- [x] Run `.venv/bin/python -m ruff check cleanwin.py cleanwincli tests`.
- [x] Run `.venv/bin/python -m mypy cleanwin.py cleanwincli tests`.
- [x] Run `make quality`.
- [x] Drain the new aiflow queue tasks and confirm no failed runs.

## Validation Evidence

- `CLEANWIN-PYTEST2-001`: `.venv/bin/python -m pytest tests/test_identity.py -q` -> 5 passed.
- `CLEANWIN-PYTEST2-002`: `.venv/bin/python -m pytest tests/test_rule_catalog.py tests/test_identity.py -q` -> 8 passed.
- `CLEANWIN-PYTEST2-003`: `.venv/bin/python -m pytest tests/test_ai_readiness.py tests/test_ai_contracts.py -q` -> 24 passed.
- `CLEANWIN-PYTEST2-004`: `.venv/bin/python -m pytest tests/test_windows_integration.py tests/test_mcp_server.py -q` -> 35 passed, 2 skipped.
- Round 2 focused migration set: `.venv/bin/python -m pytest tests/test_rule_catalog.py tests/test_identity.py tests/test_ai_readiness.py tests/test_ai_contracts.py tests/test_windows_integration.py tests/test_mcp_server.py -q` -> 67 passed, 2 skipped.
- Full gate: `make quality` -> passed, including venv setup, editable dev install, ruff, mypy, unittest discovery, pytest, compileall, AI/MCP smoke, package build, and install smoke checks.

## Round 3 Pytest Governance Evidence

- `PYTEST-GOV-78`: centralized payload schema assertions in `tests/conftest.py`.
- `PYTEST-GOV-79`: migrated filesystem identity schema checks to the shared schema helper.
- `PYTEST-GOV-80`: migrated report schema checks in scan governance, presets, and rule catalog tests.
- `PYTEST-GOV-81`: added an AST governance budget for remaining direct schema assertions.
- `PYTEST-GOV-82`: centralized execution-disabled contract assertions.
- `PYTEST-GOV-83`: migrated AI readiness read-only and schema report assertions.
- `PYTEST-GOV-84`: added an AST governance budget for remaining direct read-only boolean assertions.
- `PYTEST-GOV-85`: centralized command sequence assertions and migrated readiness/schema sample checks.
- `PYTEST-GOV-86`: documented the pytest helper and governance budget workflow in `AGENTS.md` and docs.
- `PYTEST-GOV-87`: final gate passed with `make quality`; generated `.aiflow/governance.json`
  as local aiflow evidence and confirmed the queue had 136 completed runs with no pending,
  failed, canceled, or leased runs.

## Explicit Non-Goal

Do not rewrite `tests/test_cli.py` in this round. It remains a dedicated future task because it should first get scenario-level fixtures before class removal.
