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

## Round 4 Pytest Governance Plan

Step1 status: completed. `bits-unit-test-gen` preparation produced
`BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.vaAI47e5IH`.

Step2 status: completed. `LANG=python`; `EXEC_SOURCE` is empty; project convention
is pytest-first, venv-first, and shared-helper-first.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared pytest helper layer",
      "locator": "tests/conftest.py fixtures",
      "source": "explicit",
      "reason": "remaining tests need shared helpers for schema samples, execution-disabled contracts, safe-to-execute checks, and command sequence assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "pytest governance AST checks",
      "locator": "tests/test_pytest_governance.py",
      "source": "explicit",
      "reason": "governance budgets must shrink as direct schema/read-only assertions are migrated",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_contracts.py",
      "target_type": "file",
      "symbol": "AI contract schema sample assertions",
      "locator": "tests/test_ai_contracts.py direct schema assertions",
      "source": "explicit",
      "reason": "largest remaining cluster of direct schema and read-only sample assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py",
      "target_type": "file",
      "symbol": "CLI scenario schema assertions",
      "locator": "tests/test_cli.py direct schema assertions",
      "source": "explicit",
      "reason": "CLI scenario suite still has direct payload schema assertions that can reuse helpers without restructuring the suite",
      "hunks": []
    },
    {
      "file_path": "tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "MCP resource and tool schema assertions",
      "locator": "tests/test_mcp_server.py direct schema assertions",
      "source": "explicit",
      "reason": "MCP helpers already centralize structured content; remaining direct schema checks should share payload helper behavior",
      "hunks": []
    },
    {
      "file_path": "tests/test_debloat_privacy.py",
      "target_type": "file",
      "symbol": "debloat privacy safety assertions",
      "locator": "tests/test_debloat_privacy.py safe_to_execute and evidence schema assertions",
      "source": "explicit",
      "reason": "read-only inventory tests can share schema and safe-to-execute helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_installed_apps.py",
      "target_type": "file",
      "symbol": "installed app safety assertions",
      "locator": "tests/test_installed_apps.py uninstall strategy assertions",
      "source": "explicit",
      "reason": "nested uninstall strategy schema and auto-executable assertions should use shared helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_execution_contracts.py",
      "target_type": "file",
      "symbol": "execution contract disabled assertions",
      "locator": "tests/test_execution_contracts.py execution_enabled assertions",
      "source": "explicit",
      "reason": "execution contract tests repeat disabled flag checks and should use shared helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_file_reports.py tests/test_browser_inventory.py tests/test_startup_inventory.py tests/test_system_health.py",
      "target_type": "file",
      "symbol": "inventory safe_to_execute assertions",
      "locator": "safe_to_execute false assertions across inventory tests",
      "source": "explicit",
      "reason": "read-only inventory tests repeat safe_to_execute false checks",
      "hunks": []
    }
  ],
  "diff_context": null,
  "fallback_notes": "This round is a pytest governance debt-reduction pass. It does not add cleanup execution paths or production behavior changes."
}
```

Step4 status: completed.

```json
{
  "BUG_MAP": []
}
```

Filtered candidates: this round targets test maintainability and governance
coverage. No production defect was proven by the remaining assertion style.

### Round 4 Tasks

- `PYTEST-GOV-88`: Record the Round 4 pytest governance plan and queue the next 10 tasks.
- `PYTEST-GOV-89`: Migrate AI contract schema sample assertions to shared helpers and shrink the direct schema budget.
- `PYTEST-GOV-90`: Migrate CLI scenario schema assertions to shared helpers and shrink the direct schema budget.
- `PYTEST-GOV-91`: Migrate MCP resource/tool schema assertions to shared helpers and shrink the direct schema budget.
- `PYTEST-GOV-92`: Migrate nested report schema assertions in debloat, installed app, and official command tests.
- `PYTEST-GOV-93`: Add shared safe-to-execute assertions and migrate read-only inventory tests.
- `PYTEST-GOV-94`: Govern direct safe-to-execute false assertions with an AST migration budget.
- `PYTEST-GOV-95`: Extend execution-disabled helpers for named gate flags and migrate execution contract tests.
- `PYTEST-GOV-96`: Govern direct execution-disabled flag assertions and update pytest workflow docs.
- `PYTEST-GOV-97`: Run the final quality gate, generate the aiflow governance report, and record Round 4 evidence.

## Explicit Non-Goal

Do not rewrite `tests/test_cli.py` in this round. It remains a dedicated future task because it should first get scenario-level fixtures before class removal.

## Round 5 Pytest Governance Plan

**Goal:** Finish the remaining read-only boolean migration budget and reduce the execution-disabled assertion budget with reusable pytest helpers.

**Architecture:** Keep the work in small, independently verifiable commits. Add only test helper surface that removes repeated assertion logic, then migrate focused test modules and tighten AST governance budgets after each group.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.wIF3QEszcJ`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared pytest safety helpers",
      "locator": "assert_readonly_report, assert_execution_disabled helpers",
      "source": "explicit",
      "reason": "remaining direct assertions need a reusable helper for nested read-only payloads and named execution-disabled flags",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_contracts.py tests/test_ai_readiness.py tests/test_presets.py tests/test_recovery.py",
      "target_type": "file",
      "symbol": "read-only boolean assertions",
      "locator": "READONLY_BOOLEAN_ASSERTION_ALLOWLIST entries",
      "source": "explicit",
      "reason": "these tests still carry the read-only boolean migration budget",
      "hunks": []
    },
    {
      "file_path": "tests/test_official_commands.py tests/test_system_health.py tests/test_browser_inventory.py tests/test_debloat_privacy.py tests/test_installed_apps.py tests/test_startup_inventory.py tests/test_ai_contracts.py tests/test_ai_readiness.py tests/test_presets.py tests/test_promotion_gates.py",
      "target_type": "file",
      "symbol": "execution-disabled assertions",
      "locator": "EXECUTION_DISABLED_ASSERTION_ALLOWLIST entries",
      "source": "explicit",
      "reason": "remaining direct disabled-flag assertions should use the shared execution-disabled helper where it keeps intent clear",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "pytest governance budgets",
      "locator": "READONLY_BOOLEAN_ASSERTION_ALLOWLIST and EXECUTION_DISABLED_ASSERTION_ALLOWLIST",
      "source": "explicit",
      "reason": "budget updates make the migration machine-checkable",
      "hunks": []
    }
  ],
  "diff_context": null,
  "fallback_notes": "This is a test-governance migration pass; it does not change production cleanup behavior."
}
```

Step4 status: completed.

```json
{
  "BUG_MAP": []
}
```

Filtered candidates: no production defect is claimed. The actionable risk is duplicated direct boolean assertions that can drift from shared pytest safety contracts.

### Round 5 Tasks

- `PYTEST-GOV-98`: Record this Round 5 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-99`: Add a reusable read-only payload helper for nested samples/routes/templates that do not need a full report schema assertion.
- `PYTEST-GOV-100`: Migrate remaining read-only schema sample assertions in `tests/test_ai_contracts.py`.
- `PYTEST-GOV-101`: Migrate remaining read-only CLI/readiness assertions in `tests/test_ai_readiness.py`.
- `PYTEST-GOV-102`: Migrate remaining read-only preset and recovery assertions in `tests/test_presets.py` and `tests/test_recovery.py`.
- `PYTEST-GOV-103`: Clear the `READONLY_BOOLEAN_ASSERTION_ALLOWLIST` budget and verify the governance smoke.
- `PYTEST-GOV-104`: Migrate execution-disabled report gate assertions in `tests/test_official_commands.py` and `tests/test_system_health.py`.
- `PYTEST-GOV-105`: Migrate execution-disabled inventory/report assertions in `tests/test_browser_inventory.py`, `tests/test_debloat_privacy.py`, `tests/test_installed_apps.py`, `tests/test_startup_inventory.py`, and `tests/test_recovery.py`.
- `PYTEST-GOV-106`: Migrate execution-disabled workflow/preset/promotion assertions in `tests/test_ai_contracts.py`, `tests/test_ai_readiness.py`, `tests/test_presets.py`, and `tests/test_promotion_gates.py`.
- `PYTEST-GOV-107`: Tighten the execution-disabled budget, update pytest governance documentation, run quality gates, and refresh the local aiflow governance report.

### Verification

Each round should run the smallest useful Makefile-backed pytest governance check before committing. The final round must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.

## Round 6 Pytest Governance Plan

**Goal:** Move repeated success/decision status assertions into shared pytest helpers and govern the remaining direct `valid`, `ready`, `passed`, and `allowed` checks with AST budgets.

**Architecture:** Keep the previous assertion budgets closed. Add small helper fixtures for positive and negative status payloads, introduce migration budgets for direct status assertions, then migrate focused test files in small commits.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.N3xLbVOeFu`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared status assertion helpers",
      "locator": "assert_payload_schema and safety helper fixtures",
      "source": "explicit",
      "reason": "tests repeat direct success/failure checks for valid, ready, passed, and allowed payload fields",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "status assertion governance budgets",
      "locator": "AST checks for direct status assertions",
      "source": "explicit",
      "reason": "new helper usage should be machine-checked like schema and safety assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_contracts.py tests/test_ai_readiness.py tests/test_cli.py",
      "target_type": "file",
      "symbol": "AI, readiness, and CLI status assertions",
      "locator": "direct valid, passed, ready, and allowed assertions",
      "source": "explicit",
      "reason": "these files contain the highest-density repeated status assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_identity.py tests/test_execution_contracts.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "remaining status assertions",
      "locator": "direct valid and allowed assertions in identity, execution, and MCP tests",
      "source": "explicit",
      "reason": "remaining direct status assertions should either migrate or be locked by a small budget",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest workflow documentation",
      "locator": "pytest governance helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe the new status helper and budget contract",
      "hunks": []
    }
  ],
  "diff_context": null,
  "fallback_notes": "This is a test-governance migration pass; it does not change production cleanup behavior or execution paths."
}
```

Step4 status: completed.

```json
{
  "BUG_MAP": []
}
```

Filtered candidates: no production defect is claimed. The actionable risk is duplicated status assertions that can drift from shared pytest contract helpers.

### Round 6 Tasks

- `PYTEST-GOV-108`: Record this Round 6 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-109`: Add reusable status helpers for truthy and falsey payload fields.
- `PYTEST-GOV-110`: Add AST governance budgets for direct status assertions.
- `PYTEST-GOV-111`: Migrate AI contract validation and host policy status assertions.
- `PYTEST-GOV-112`: Migrate AI readiness and doctor status assertions.
- `PYTEST-GOV-113`: Migrate CLI plan/review validation status assertions.
- `PYTEST-GOV-114`: Migrate CLI permanent/admin validation denial assertions.
- `PYTEST-GOV-115`: Migrate identity and execution contract status assertions.
- `PYTEST-GOV-116`: Migrate MCP governance decision status assertions and shrink any remaining status budget.
- `PYTEST-GOV-117`: Update pytest governance documentation, run quality gates, refresh the local aiflow governance report, and complete the round.

### Verification

Each round should run the smallest useful Makefile-backed pytest governance check before committing. The final round must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.

## Round 7 Pytest Governance Plan

**Goal:** Move repeated summary-count and dry-run-result assertions into shared pytest helpers, then govern remaining direct summary assertions with AST budgets.

**Architecture:** Keep all previous assertion budgets closed. Add small helpers for payload summary counts and dry-run execution summaries, introduce a migration budget for direct summary assertions, then migrate focused tests in small commits.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.GMINKXsx4v`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared summary and dry-run assertion helpers",
      "locator": "assert_dry_run_result and shared payload helpers",
      "source": "explicit",
      "reason": "tests repeat direct summary count and dry-run result assertions across CLI, MCP, inventory, and contract tests",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "summary assertion governance budget",
      "locator": "AST checks for direct summary assertions",
      "source": "explicit",
      "reason": "summary-count assertions should be machine-checked like schema, read-only, status, and execution-disabled assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "CLI and MCP dry-run result assertions",
      "locator": "direct executed/dry_run/result_count/status_counts assertions",
      "source": "explicit",
      "reason": "dry-run output semantics are repeated and should use shared helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py tests/test_file_reports.py tests/test_installed_apps.py tests/test_browser_inventory.py",
      "target_type": "file",
      "symbol": "summary count assertions in high-density tests",
      "locator": "direct payload['summary'][...] assertions",
      "source": "explicit",
      "reason": "these files contain the highest-density repeated summary count assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_startup_inventory.py tests/test_debloat_privacy.py tests/test_execution_contracts.py tests/test_official_commands.py tests/test_presets.py tests/test_system_health.py tests/test_windows_smoke.py",
      "target_type": "file",
      "symbol": "remaining summary count assertions",
      "locator": "direct report['summary'][...] assertions",
      "source": "explicit",
      "reason": "remaining direct summary assertions should migrate or be locked by a shrinking budget",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest workflow documentation",
      "locator": "pytest governance helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe the new summary helper and budget contract",
      "hunks": []
    }
  ],
  "diff_context": null,
  "fallback_notes": "This is a test-governance migration pass; it does not change production cleanup behavior or execution paths."
}
```

Step4 status: completed.

```json
{
  "BUG_MAP": []
}
```

Filtered candidates: no production defect is claimed. The actionable risk is duplicated summary and dry-run result assertions that can drift from shared pytest contract helpers.

### Round 7 Tasks

- `PYTEST-GOV-118`: Record this Round 7 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-119`: Add reusable summary-count and dry-run summary helpers.
- `PYTEST-GOV-120`: Add AST governance budgets for direct summary assertions.
- `PYTEST-GOV-121`: Migrate CLI dry-run result summary assertions.
- `PYTEST-GOV-122`: Migrate MCP dry-run result summary assertions.
- `PYTEST-GOV-123`: Migrate high-density CLI summary count assertions.
- `PYTEST-GOV-124`: Migrate file, installed-app, and browser inventory summary assertions.
- `PYTEST-GOV-125`: Migrate startup and debloat/privacy summary assertions.
- `PYTEST-GOV-126`: Migrate execution, official-command, preset, system-health, and Windows-smoke summary assertions and clear the summary budget.
- `PYTEST-GOV-127`: Update pytest governance documentation, run quality gates, refresh local aiflow governance report, and complete the round.

### Verification

Each round should run the smallest useful Makefile-backed pytest governance check before committing. The final round must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.
