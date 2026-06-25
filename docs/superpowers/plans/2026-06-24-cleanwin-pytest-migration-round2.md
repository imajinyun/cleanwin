# CleanWin Pytest Migration Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue migrating remaining unittest-style CleanWin tests to idiomatic pytest without a large, risky rewrite of the biggest CLI test file.

**Architecture:** Reuse `tests/conftest.py` as the shared pytest support layer, extend it only where existing tests need environment-aware CLI calls, then migrate medium and small `unittest.TestCase` files to top-level pytest functions. Keep `tests/test_cli.py` for a later dedicated split because it is still a large scenario suite.

**Tech Stack:** Python 3.10+, pytest 8, Ruff, mypy, project `.venv`, aiflow queue orchestration.

---

## Round 13 Pytest Governance Plan

**Goal:** Make the pytest governance tests self-host the same shared assertion
helpers they enforce for the rest of the suite.

**Architecture:** Keep the current zero-budget checks for migrated assertion
families. Add a compact "governance helper" adoption lane for
`tests/test_pytest_governance.py`, then migrate its repeated empty-list,
workflow-text, and helper-adoption scalar assertions in small commits. This
round stays test/doc only and does not change cleanwin runtime behavior or any
cleanup execution path.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests,
Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed.
`BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.BvpRrUsC2c`

Step2 status: completed. `LANG=python`; `EXEC_SOURCE` is empty. Project
conventions require pytest-native tests, shared helpers, and Makefile-backed
`.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "pytest governance self-hosted assertion helpers",
      "locator": "direct empty-list, length, and workflow text assertions",
      "source": "explicit",
      "reason": "governance tests should model the helper usage they require from migrated test files",
      "hunks": []
    },
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared assertion helper support layer",
      "locator": "existing collection, text, exact, scalar, and predicate fixtures",
      "source": "explicit",
      "reason": "reuse existing helpers first; only add narrow helpers if governance tests expose a real shared need",
      "hunks": []
    },
    {
      "file_path": "docs/doc/README.md docs/doc/README.CN.md AGENTS.md",
      "target_type": "file",
      "symbol": "pytest governance workflow documentation",
      "locator": "development and CI test workflow sections",
      "source": "explicit",
      "reason": "docs should stay aligned if governance self-hosting rules or helper families change",
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

Filtered candidates: no production defect is claimed. The actionable risk is
that governance tests still contain repeated direct assertions while enforcing
shared assertion helpers elsewhere.

### Round 13 Tasks

- `PYTEST-GOV-178`: Record this Round 13 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-179`: Add governance-test adoption tracking for shared helper usage in `tests/test_pytest_governance.py`.
- `PYTEST-GOV-180`: Migrate pytest-native, filesystem-fixture, subprocess, and raises-budget empty-list assertions to shared helpers.
- `PYTEST-GOV-181`: Migrate provider/schema registry and direct schema/readonly/safety budget empty-list assertions to shared helpers.
- `PYTEST-GOV-182`: Migrate execution-disabled/status/summary/predicate budget empty-list assertions to shared helpers.
- `PYTEST-GOV-183`: Migrate helper-adoption missing-list assertions to shared helpers.
- `PYTEST-GOV-184`: Migrate helper-adoption minimum-count assertions to scalar helpers.
- `PYTEST-GOV-185`: Migrate workflow text contract assertions to shared text membership helpers.
- `PYTEST-GOV-186`: Run focused pytest governance gates and tighten governance-test helper adoption evidence.
- `PYTEST-GOV-187`: Update docs if needed, run final `make quality`, refresh local aiflow governance report, and complete the round.

### Verification

Each task should run the smallest useful Makefile-backed pytest governance check
before committing. The final task must run `make quality` so lint, pytest, type
checking, compile, packaging, smoke tests, and pytest governance all execute
through the repository `.venv`.

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

## Round 8 Pytest Governance Plan

**Goal:** Move repeated collection membership and text-substring assertions into shared pytest helpers and pytest parametrization so contract tests stay concise, diagnostic, and governance-friendly.

**Architecture:** Keep all previous direct assertion budgets closed. Add small collection/text helpers in `tests/conftest.py`, then migrate repeated groups in focused test files. This round does not change production cleanup behavior, command surfaces, or execution paths.

**Tech Stack:** Python, pytest fixtures, shared assertion helpers, targeted parametrization, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.BUHX4iDIDi`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared collection and text assertion helpers",
      "locator": "tests/conftest.py shared pytest helper layer",
      "source": "explicit",
      "reason": "tests repeat equivalent contains-all, contains-none, and substring checks across contract reports",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_readiness.py tests/test_ai_contracts.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "AI/MCP collection membership assertions",
      "locator": "direct repeated membership checks for tool names, schemas, codes, and violations",
      "source": "explicit",
      "reason": "AI/MCP tests contain repeated membership assertions that should produce compact pytest diagnostics through helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py",
      "target_type": "file",
      "symbol": "CLI scenario collection membership assertions",
      "locator": "direct path/category/rule membership checks",
      "source": "explicit",
      "reason": "the large CLI scenario file still has repeated list/set membership assertions that can move to helpers without splitting the file",
      "hunks": []
    },
    {
      "file_path": "tests/test_execution_contracts.py tests/test_official_commands.py tests/test_promotion_gates.py tests/test_presets.py tests/test_system_health.py tests/test_windows_smoke.py",
      "target_type": "file",
      "symbol": "contract surface expected-id membership assertions",
      "locator": "direct repeated assert '<id>' in by_id",
      "source": "explicit",
      "reason": "contract report tests repeatedly verify expected IDs and required evidence with hand-written membership assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_file_reports.py tests/test_browser_inventory.py tests/test_installed_apps.py tests/test_startup_inventory.py tests/test_debloat_privacy.py tests/test_recovery.py tests/test_rule_catalog.py tests/test_scan_governance.py",
      "target_type": "file",
      "symbol": "inventory/report membership assertions",
      "locator": "direct repeated field/path/substr membership checks",
      "source": "explicit",
      "reason": "smaller inventory and governance tests can reuse the same helpers for expected fields, paths, and evidence markers",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest workflow documentation",
      "locator": "pytest governance helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe the new collection and text helper guidance",
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

Filtered candidates: no production defect is claimed. The actionable risk is repeated collection and substring assertions that can drift from shared pytest diagnostics.

### Round 8 Tasks

- `PYTEST-GOV-128`: Record this Round 8 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-129`: Add reusable collection and text assertion helpers.
- `PYTEST-GOV-130`: Migrate AI readiness collection membership assertions.
- `PYTEST-GOV-131`: Migrate AI contract and MCP validation/code membership assertions.
- `PYTEST-GOV-132`: Migrate CLI capability, package, app-leftover, browser, and review membership assertions.
- `PYTEST-GOV-133`: Migrate execution and official-command contract membership assertions.
- `PYTEST-GOV-134`: Migrate preset, promotion, system-health, and Windows-smoke membership assertions.
- `PYTEST-GOV-135`: Migrate inventory/report/recovery/rule-catalog/scan-governance membership assertions.
- `PYTEST-GOV-136`: Add governance smoke coverage for collection helper adoption and run focused pytest gates.
- `PYTEST-GOV-137`: Update pytest governance documentation, run quality gates, refresh local aiflow governance report, and complete the round.

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

## Round 9 Pytest Governance Plan

**Goal:** Move remaining predicate-style assertions into shared pytest helpers and govern direct `any(...)` / `all(...)` assertion drift with focused AST budgets.

**Architecture:** Keep previous schema, status, summary, dry-run, and collection-helper budgets intact. Add predicate helpers for positive and negative collection matching, migrate focused assertion clusters, then close with a shrinking governance smoke budget.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.COoJSiAP8D`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared predicate assertion helpers",
      "locator": "collection predicate helpers near existing collection/text helpers",
      "source": "explicit",
      "reason": "remaining tests repeat any/all predicate assertions for field, path, and text matching",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "predicate assertion governance budget",
      "locator": "AST checks for direct any/all assertions",
      "source": "explicit",
      "reason": "direct predicate assertions should be governed like schema, status, summary, dry-run, and collection assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_identity.py tests/test_file_reports.py",
      "target_type": "file",
      "symbol": "identity and file-report predicate assertions",
      "locator": "direct membership, text, and any/equality assertions",
      "source": "explicit",
      "reason": "identity and file report tests still contain helperizable predicate assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_browser_inventory.py tests/test_installed_apps.py",
      "target_type": "file",
      "symbol": "inventory predicate assertions",
      "locator": "all(...) negative path checks and any(...) source checks",
      "source": "explicit",
      "reason": "inventory tests should express predicate expectations through shared pytest helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py",
      "target_type": "file",
      "symbol": "CLI candidate and path predicate assertions",
      "locator": "candidate category/delete-mode and path equality checks",
      "source": "explicit",
      "reason": "CLI tests contain repeated candidate matching assertions that should be helperized",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_readiness.py tests/test_ai_contracts.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "AI and MCP field assertion clusters",
      "locator": "repeated tool/resource field and sequence assertions",
      "source": "explicit",
      "reason": "AI/MCP tests should share predicate helpers for structured contract checks",
      "hunks": []
    },
    {
      "file_path": "tests/test_execution_contracts.py tests/test_official_commands.py tests/test_system_health.py tests/test_recovery.py tests/test_scan_governance.py tests/test_rule_catalog.py",
      "target_type": "file",
      "symbol": "remaining safety and governance predicate assertions",
      "locator": "execution gate, official command, system-health, recovery, scan, and rationale predicates",
      "source": "explicit",
      "reason": "remaining direct predicates should migrate or be locked by a final budget",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest workflow documentation",
      "locator": "pytest predicate helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe when to use shared predicate helpers",
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

Filtered candidates: no production defect is claimed. The actionable risk is duplicated predicate assertion style that can drift from shared pytest helper contracts.

### Round 9 Tasks

- `PYTEST-GOV-138`: Record this Round 9 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-139`: Add reusable predicate helpers for `any(...)` / `all(...)` style assertions.
- `PYTEST-GOV-140`: Add governance smoke and budgets for helperized predicate assertions.
- `PYTEST-GOV-141`: Migrate remaining identity and file-report membership/text predicate assertions.
- `PYTEST-GOV-142`: Migrate browser inventory and installed-app predicate assertions.
- `PYTEST-GOV-143`: Migrate CLI repeated candidate/category/delete-mode and path equality predicate assertions.
- `PYTEST-GOV-144`: Migrate AI readiness, AI contracts, and MCP repeated field/sequence assertion clusters.
- `PYTEST-GOV-145`: Migrate execution, official-command, system-health, recovery, scan-governance, and rule-catalog remaining predicate assertions.
- `PYTEST-GOV-146`: Tighten pytest governance smoke for remaining direct predicate assertion budget and run focused gates.
- `PYTEST-GOV-147`: Update docs, run final `make quality`, refresh local aiflow governance report, and complete the round.

### Verification

Each task should run the smallest useful Makefile-backed pytest governance check before committing. The final task must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.

## Round 14 Pytest Governance Plan

**Goal:** Continue shrinking ad-hoc pytest assertions by moving repeated path,
non-empty, lower-bound, status, and MCP result checks into shared helpers.

**Architecture:** Add only narrow helper surface where repeated patterns already
exist. Keep all changes test/doc/governance-only, preserve cleanwin runtime
behavior, and avoid any cleanup execution path changes.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests,
Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed.
`BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.kIiiYRlqlM`

Step2 status: completed. `LANG=python`; `EXEC_SOURCE` is empty. Project
conventions require pytest-native tests, shared helpers, and Makefile-backed
`.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "path and assertion helper support layer",
      "locator": "existing collection, exact, scalar, predicate, field, and returncode fixtures",
      "source": "explicit",
      "reason": "repeated path existence assertions should use shared helpers with consistent diagnostics",
      "hunks": []
    },
    {
      "file_path": "tests/test_delete_ops.py tests/test_ai_contracts.py tests/test_cli.py",
      "target_type": "file",
      "symbol": "path existence assertion clusters",
      "locator": "target/cache/trash path exists and missing checks",
      "source": "explicit",
      "reason": "these tests repeat stable path existence checks that can migrate without changing runtime behavior",
      "hunks": []
    },
    {
      "file_path": "tests/test_rule_catalog.py tests/test_ai_readiness.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "remaining scalar, status, and MCP result assertion clusters",
      "locator": "lower-bound, non-empty, status boolean, and structured MCP result checks",
      "source": "explicit",
      "reason": "small focused migrations continue reducing unittest-style assertion drift while preserving pytest-native style",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "pytest governance helper adoption checks",
      "locator": "helper family definitions and adoption evidence",
      "source": "explicit",
      "reason": "new helper families should be covered by governance smoke and adoption evidence",
      "hunks": []
    },
    {
      "file_path": "docs/doc/README.md docs/doc/README.CN.md AGENTS.md",
      "target_type": "file",
      "symbol": "pytest helper workflow documentation",
      "locator": "test workflow helper guidance",
      "source": "explicit",
      "reason": "workflow docs should stay aligned when shared helper guidance changes",
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

Filtered candidates: no production defect is claimed. The actionable risk is
duplicated pytest assertions that can drift from shared helper contracts.

### Round 14 Tasks

- `PYTEST-GOV-188`: Record this Round 14 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-189`: Add reusable path existence assertion helpers and governance coverage.
- `PYTEST-GOV-190`: Migrate delete-ops path existence assertions to shared helpers.
- `PYTEST-GOV-191`: Migrate AI contract execution path assertions to shared helpers.
- `PYTEST-GOV-192`: Migrate selected CLI path and non-empty assertions to shared helpers.
- `PYTEST-GOV-193`: Migrate rule catalog scalar, non-empty, and exclusion assertions to shared helpers.
- `PYTEST-GOV-194`: Migrate AI readiness boolean status assertions to shared helpers.
- `PYTEST-GOV-195`: Migrate MCP structured result assertions to shared helpers.
- `PYTEST-GOV-196`: Run focused pytest governance gates and tighten path helper adoption evidence.
- `PYTEST-GOV-197`: Update docs, run final `make quality`, refresh local aiflow governance report, and complete the round.

### Verification

Each task should run the smallest useful Makefile-backed pytest check before
committing. The final task must run `make quality` so lint, pytest, type
checking, compile, packaging, smoke tests, and pytest governance all execute
through the repository `.venv`.

## Round 12 Pytest Governance Plan

**Goal:** Migrate the remaining compact direct assertions in pytest suites into shared helper patterns for scalar membership, exact counts, and any-of text checks, then document and validate the tightened governance surface.

**Architecture:** Keep all changes test-only and documentation-only. Extend `tests/conftest.py` with narrowly scoped helper fixtures, make the helper family visible in `tests/test_pytest_governance.py`, migrate one small assertion cluster per commit, and use Makefile-backed `.venv` validation throughout.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.pDG1KJ56sM`

Step2 status: completed. `LANG=python`; `EXEC_SOURCE` is empty; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared scalar and count assertion helpers",
      "locator": "near existing exact, field, collection, and predicate helpers",
      "source": "explicit",
      "reason": "remaining tests repeat scalar membership, exact count, and text any-of checks",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "scalar helper adoption governance smoke",
      "locator": "helper registration and adoption checks",
      "source": "explicit",
      "reason": "new scalar/count helpers should be machine-visible and adopted by migrated files",
      "hunks": []
    },
    {
      "file_path": "tests/test_debloat_privacy.py",
      "target_type": "file",
      "symbol": "finding count assertions",
      "locator": "direct len(appx_findings) and len(oem_findings) checks",
      "source": "explicit",
      "reason": "read-only finding tests should use shared exact-count diagnostics",
      "hunks": []
    },
    {
      "file_path": "tests/test_rule_catalog.py",
      "target_type": "file",
      "symbol": "rationale any-of text assertion",
      "locator": "direct regenerated or recreated rationale check",
      "source": "explicit",
      "reason": "any-of text checks should be expressed through a shared helper",
      "hunks": []
    },
    {
      "file_path": "tests/test_identity.py",
      "target_type": "file",
      "symbol": "identity error text assertion",
      "locator": "direct substring assertion over validation errors",
      "source": "explicit",
      "reason": "error text checks should reuse shared text helper diagnostics",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_contracts.py",
      "target_type": "file",
      "symbol": "AI destructive tool sequence assertion",
      "locator": "direct destructive tool name list equality",
      "source": "explicit",
      "reason": "tool ordering contract should use shared exact sequence helper",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_readiness.py",
      "target_type": "file",
      "symbol": "AI readiness scalar membership assertions",
      "locator": "distribution version and recommended command membership checks",
      "source": "explicit",
      "reason": "scalar/list membership checks should use shared helper diagnostics",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py",
      "target_type": "file",
      "symbol": "CLI exact path set assertion",
      "locator": "direct path set equality check",
      "source": "explicit",
      "reason": "path set equality should use shared exact set helper",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest scalar helper workflow documentation",
      "locator": "pytest governance helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe when to use count, one-of, and text any-of helpers",
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

Filtered candidates: no production defect is claimed. The actionable risk is repeated compact assertion style that can drift from shared pytest diagnostics.

### Round 12 Tasks

- `PYTEST-GOV-168`: Record this Round 12 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-169`: Add reusable exact-count, scalar one-of, and any-of text assertion helpers.
- `PYTEST-GOV-170`: Add pytest governance smoke coverage for the scalar helper family and adoption evidence.
- `PYTEST-GOV-171`: Migrate debloat/privacy finding count assertions.
- `PYTEST-GOV-172`: Migrate rule-catalog rationale any-of text assertions.
- `PYTEST-GOV-173`: Migrate identity validation error text assertions.
- `PYTEST-GOV-174`: Migrate AI contract destructive tool sequence assertions.
- `PYTEST-GOV-175`: Migrate AI readiness scalar membership assertions.
- `PYTEST-GOV-176`: Migrate CLI exact path set assertions and run focused governance gates.
- `PYTEST-GOV-177`: Update pytest workflow docs, run final `make quality`, refresh local aiflow governance report, and complete the round.

### Verification

Each task should run the smallest useful Makefile-backed pytest governance check before committing. The final task must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.

## Round 11 Pytest Governance Plan

**Goal:** Continue shrinking repeated low-level assertions by introducing focused helpers for exact collection equality, subprocess return-code contracts, and non-empty collection expectations, then migrate the remaining compact assertion clusters.

**Architecture:** Keep this round test-only. Add narrowly scoped helper fixtures to `tests/conftest.py`, make helper adoption visible in `tests/test_pytest_governance.py`, migrate focused test files in small commits, and keep all validation through Makefile-backed `.venv` targets.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.nPuQo6jfre`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared exact collection, return-code, and non-empty assertion helpers",
      "locator": "near existing field, collection, predicate, and CLI helpers",
      "source": "explicit",
      "reason": "remaining tests repeat exact sequence/set equality, subprocess return-code checks, and non-empty collection checks",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "helper adoption governance smoke",
      "locator": "helper registration and adoption checks",
      "source": "explicit",
      "reason": "new helpers should be machine-visible and adopted by migrated files",
      "hunks": []
    },
    {
      "file_path": "tests/test_delete_ops.py tests/test_windows_integration.py",
      "target_type": "file",
      "symbol": "delete and Windows integration result field assertions",
      "locator": "direct recycled status and operation-log field equality checks",
      "source": "explicit",
      "reason": "small execution-safety tests can reuse shared field helpers without changing delete behavior",
      "hunks": []
    },
    {
      "file_path": "tests/test_system_health.py tests/test_debloat_privacy.py",
      "target_type": "file",
      "symbol": "exact command and evidence sequence assertions",
      "locator": "direct command list and registry export command equality checks",
      "source": "explicit",
      "reason": "read-only report tests repeat exact sequence contracts that should use shared diagnostics",
      "hunks": []
    },
    {
      "file_path": "tests/test_rule_catalog.py tests/test_file_reports.py",
      "target_type": "file",
      "symbol": "exact set and uniqueness assertions",
      "locator": "direct set equality and uniqueness checks",
      "source": "explicit",
      "reason": "catalog and report tests contain compact collection equality checks that can share helper behavior",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py tests/test_ai_contracts.py",
      "target_type": "file",
      "symbol": "CLI and AI subprocess return-code assertions",
      "locator": "direct result.returncode equality checks",
      "source": "explicit",
      "reason": "subprocess assertions should report stdout/stderr consistently through shared helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_readiness.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "AI readiness and MCP sequence/field assertions",
      "locator": "direct first/last tool and error-code equality checks",
      "source": "explicit",
      "reason": "contract-order and JSON-RPC response checks should reuse helper fixtures where intent stays clear",
      "hunks": []
    },
    {
      "file_path": "tests/test_safety.py",
      "target_type": "file",
      "symbol": "safety boolean assertions",
      "locator": "direct protected registry and sensitive path boolean checks",
      "source": "explicit",
      "reason": "remaining safety predicates can use pytest parametrization and shared status helpers without changing protection logic",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest helper workflow documentation",
      "locator": "pytest governance helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe when to use the new exact collection, non-empty, and return-code helpers",
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

Filtered candidates: no production defect is claimed. The actionable risk is repeated low-level assertion style that can drift from shared pytest diagnostics.

### Round 11 Tasks

- `PYTEST-GOV-158`: Record this Round 11 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-159`: Add reusable exact collection, non-empty collection, and subprocess return-code assertion helpers.
- `PYTEST-GOV-160`: Add pytest governance smoke coverage for the new helper family and adoption evidence.
- `PYTEST-GOV-161`: Migrate delete operation and Windows integration result field assertions.
- `PYTEST-GOV-162`: Migrate system-health and debloat/privacy exact command and evidence assertions.
- `PYTEST-GOV-163`: Migrate rule-catalog and file-report exact set and uniqueness assertions.
- `PYTEST-GOV-164`: Migrate CLI and AI contract subprocess return-code assertions.
- `PYTEST-GOV-165`: Migrate AI readiness and MCP sequence/field response assertions.
- `PYTEST-GOV-166`: Migrate safety boolean assertions through parametrization and shared helpers, then run focused pytest governance gates.
- `PYTEST-GOV-167`: Update pytest workflow docs, run final `make quality`, refresh local aiflow governance report, and complete the round.

### Verification

Each task should run the smallest useful Makefile-backed pytest governance check before committing. The final task must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.

## Round 10 Pytest Governance Plan

**Goal:** Move repeated structured field equality assertions into shared pytest helpers so tests express contract checks as compact field maps with better drift control.

**Architecture:** Keep all previous assertion budgets closed. Add nested field-value helpers in `tests/conftest.py`, introduce governance smoke coverage for helper availability, migrate focused high-density files, then document the workflow. This round stays test-only and does not change cleanup behavior or execution paths.

**Tech Stack:** Python, pytest fixtures, AST-based governance tests, Makefile-backed `.venv` tooling, local aiflow queue.

Step1 status: completed. `BITS_TMP_ROOT=/var/folders/57/pqx08bk577x758hnslxkfhm40000gn/T/tmp.BYRlt0FQGJ`

Step2 status: completed. `LANG=python`; project conventions require pytest-native tests, shared helpers, and Makefile-backed `.venv` tooling.

Step3 status: completed.

```json
{
  "scope_type": "non_diff",
  "TARGETS": [
    {
      "file_path": "tests/conftest.py",
      "target_type": "file",
      "symbol": "shared structured field assertion helpers",
      "locator": "near existing summary, collection, text, and predicate helpers",
      "source": "explicit",
      "reason": "many tests repeat payload['field'] == value and nested field equality assertions",
      "hunks": []
    },
    {
      "file_path": "tests/test_pytest_governance.py",
      "target_type": "file",
      "symbol": "field assertion helper adoption smoke",
      "locator": "helper registration and adoption checks",
      "source": "explicit",
      "reason": "new shared helpers should be machine-visible and covered by pytest governance smoke",
      "hunks": []
    },
    {
      "file_path": "tests/test_identity.py tests/test_browser_inventory.py tests/test_file_reports.py",
      "target_type": "file",
      "symbol": "inventory and identity field assertions",
      "locator": "direct replay, browser profile, and file report field equality clusters",
      "source": "explicit",
      "reason": "these tests contain small stable field maps that can migrate with low risk",
      "hunks": []
    },
    {
      "file_path": "tests/test_installed_apps.py",
      "target_type": "file",
      "symbol": "installed app field assertion clusters",
      "locator": "application, correlation, and uninstall strategy field assertions",
      "source": "explicit",
      "reason": "installed app tests contain repeated structured field checks over payload dictionaries",
      "hunks": []
    },
    {
      "file_path": "tests/test_ai_contracts.py tests/test_ai_readiness.py tests/test_mcp_server.py",
      "target_type": "file",
      "symbol": "AI and MCP structured field assertions",
      "locator": "tool metadata, route metadata, and MCP response field equality clusters",
      "source": "explicit",
      "reason": "AI/MCP contract tests should use shared field maps for repeated structured fields",
      "hunks": []
    },
    {
      "file_path": "tests/test_execution_contracts.py tests/test_debloat_privacy.py tests/test_official_commands.py tests/test_startup_inventory.py tests/test_scan_governance.py",
      "target_type": "file",
      "symbol": "safety and governance field assertions",
      "locator": "execution gate, privacy evidence, official command, startup, and scan governance fields",
      "source": "explicit",
      "reason": "safety reports contain repeated field equality clusters that benefit from shared helpers",
      "hunks": []
    },
    {
      "file_path": "tests/test_cli.py tests/test_presets.py tests/test_promotion_gates.py tests/test_rule_catalog.py tests/test_windows_smoke.py tests/test_recovery.py",
      "target_type": "file",
      "symbol": "remaining CLI and governance field assertion clusters",
      "locator": "direct rule, path, preset, gate, catalog, smoke, and recovery field equality checks",
      "source": "explicit",
      "reason": "remaining high-value field clusters should migrate in focused batches without broad rewrites",
      "hunks": []
    },
    {
      "file_path": "AGENTS.md docs/doc/README.md docs/doc/README.CN.md",
      "target_type": "file",
      "symbol": "pytest field helper documentation",
      "locator": "pytest workflow helper guidance",
      "source": "explicit",
      "reason": "workflow docs should describe when to use shared field-value helpers",
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

Filtered candidates: no production defect is claimed. The actionable risk is duplicated structured field assertions that can drift from shared pytest helper contracts.

### Round 10 Tasks

- `PYTEST-GOV-148`: Record this Round 10 plan and submit the next 10 governance tasks to aiflow.
- `PYTEST-GOV-149`: Add reusable nested field-value assertion helpers.
- `PYTEST-GOV-150`: Add pytest governance smoke coverage for field helper availability and adoption.
- `PYTEST-GOV-151`: Migrate identity, browser inventory, and file-report field assertion clusters.
- `PYTEST-GOV-152`: Migrate installed-app field assertion clusters.
- `PYTEST-GOV-153`: Migrate AI readiness, AI contracts, and MCP field assertion clusters.
- `PYTEST-GOV-154`: Migrate execution, debloat/privacy, official-command, startup, and scan-governance field clusters.
- `PYTEST-GOV-155`: Migrate CLI, preset, promotion-gate, rule-catalog, Windows-smoke, and recovery field clusters.
- `PYTEST-GOV-156`: Run focused pytest governance gates and tighten helper adoption evidence.
- `PYTEST-GOV-157`: Update docs, run final `make quality`, refresh local aiflow governance report, and complete the round.

### Verification

Each task should run the smallest useful Makefile-backed pytest governance check before committing. The final task must run `make quality` so lint, pytest, type checking, compile, packaging, smoke tests, and pytest governance all execute through the repository `.venv`.
