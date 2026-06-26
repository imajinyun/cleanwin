# CleanWin MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a conservative Windows cleanup CLI that ports CleanMac's dry-run, plan, validation, protected-path, recycle-bin fail-closed, and audit-log safety model to a Windows-specific MVP.

**Architecture:** Keep destructive operations behind `cleanwincli/delete_ops.py`; keep Windows policy data separate from logic; keep CLI orchestration in `cleanwincli/cli.py`. MVP supports safe current-user temp/dev-cache candidates, read-only system/startup/registry reports, JSON output, plan validation, and test-mode recycle routing.

**Tech Stack:** Python 3.10+, stdlib-only runtime, pytest tests, `ruff`/`mypy` compatible project metadata.

---

### Task 1: Project skeleton and entrypoint

**Files:**
- Create: `pyproject.toml`
- Create: `cleanwin.py`
- Create: `cleanwincli/__init__.py`
- Create: `cleanwincli/cli.py`

- [ ] **Step 1: Implement stdlib-only package metadata and `cleanwin` console script.**
- [ ] **Step 2: Implement a thin `cleanwin.py` entrypoint that delegates to `cleanwincli.cli.main`.**
- [ ] **Step 3: Add `capabilities`, `inspect`, `plan`, `validate-plan`, and `execute-plan` subcommands.**
- [ ] **Step 4: Run `.venv/bin/python cleanwin.py --json capabilities` and expect JSON with `default_dry_run: true`.**

### Task 2: Safety model and Windows path policy

**Files:**
- Create: `cleanwincli/protection_data.py`
- Create: `cleanwincli/protection.py`
- Create: `cleanwincli/paths.py`
- Test: `tests/test_safety.py`

- [ ] **Step 1: Add protected Windows roots, sensitive user-data segments, registry protected prefixes, and read-only categories.**
- [ ] **Step 2: Implement string-safe path normalization for Windows and host paths.**
- [ ] **Step 3: Reject empty, relative, traversal, control-character, Windows system roots, user profile roots, sensitive data paths, and reparse/symlink candidates.**
- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_safety.py -q` and expect protected paths to be rejected.**

### Task 3: Candidate discovery, plan schema, and reports

**Files:**
- Create: `cleanwincli/models.py`
- Create: `cleanwincli/collectors.py`
- Create: `cleanwincli/core.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add `cleanwin.plan.v1` models with host/user context and source fingerprint.**
- [ ] **Step 2: Discover only low-risk temp/dev-cache filesystem candidates by default.**
- [ ] **Step 3: Keep registry/startup/windows-system categories read-only with `safe_to_delete=false`.**
- [ ] **Step 4: Run `.venv/bin/python -m pytest tests/test_cli.py -q` and expect inspect/plan/validate flows to pass.**

### Task 4: Single destructive exit and audit log

**Files:**
- Create: `cleanwincli/delete_ops.py`
- Create: `cleanwincli/operation_log.py`
- Test: `tests/test_delete_ops.py`

- [ ] **Step 1: Implement recycle-bin routing via Windows Shell API only on Windows; in test mode route to a sandbox trash directory.**
- [ ] **Step 2: Fail closed when recycle routing is unavailable, trash root is a symlink, or validation rejects a path.**
- [ ] **Step 3: Implement permanent delete only behind explicit `allow_permanent=True` and `--yes`.**
- [ ] **Step 4: Write JSONL operation log records and surface log write failures.**
- [ ] **Step 5: Run `.venv/bin/python -m pytest tests/test_delete_ops.py -q` and expect recycle fail-closed tests to pass.**

### Task 5: End-to-end verification

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/data/dangerous_paths.txt`

- [ ] **Step 1: Add dangerous Windows path fixtures.**
- [ ] **Step 2: Run `make pytest` and expect all tests to pass.**
- [ ] **Step 3: Run `.venv/bin/python cleanwin.py --json capabilities`, `.venv/bin/python cleanwin.py --json inspect --categories temp`, and `.venv/bin/python cleanwin.py --json plan --categories temp --max-items 5`.**
- [ ] **Step 4: Confirm non-Windows real execution fails closed unless `CLEANWIN_TEST_MODE=1` is set.**

### Self-review

- Spec coverage: The plan covers conservative Windows cleanup MVP, dry-run default, plan/validate/execute flow, protected paths, no registry execution, no direct system-component deletion, recycle fail-closed, and audit logging.
- Placeholder scan: No TBD/TODO placeholder remains in executable task descriptions.
- Type consistency: `cleanwin.plan.v1`, `Candidate`, `Plan`, and single `delete_ops` exit are used consistently across tasks.
