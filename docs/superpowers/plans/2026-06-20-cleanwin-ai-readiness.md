# CleanWin AI Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add machine-readable AI readiness, self-test, and runbook outputs for CleanWin AI/MCP host integration.

**Architecture:** Keep readiness/self-test/runbook as small pure-report modules that compose existing AI schema, host policy, schema registry, and MCP checks. Expose them through CLI and MCP resources without adding destructive behavior.

**Tech Stack:** Python 3.10+ stdlib runtime, pytest, JSON CLI/MCP contracts.

---

### Task 1: Readiness reports

**Files:**
- Create: `cleanwincli/ai_readiness.py`
- Modify: `cleanwincli/ai_versioning.py`
- Test: `tests/test_ai_readiness.py`

- [ ] Add `ai_readiness_report()` that validates AI schema, host policy, schema registry, MCP resource declarations, and destructive tool deny gates.
- [ ] Register `cleanwin.ai-readiness.v1` and validation schemas.

### Task 2: Self-test reports

**Files:**
- Create: `cleanwincli/ai_self_test.py`
- Test: `tests/test_ai_readiness.py`

- [ ] Add `ai_self_test_report()` with deterministic pass/fail checks for schema parity, host policy, raw command denial, destructive denial, and confirmation gate presence.

### Task 3: Runbook reports

**Files:**
- Create: `cleanwincli/ai_runbook.py`
- Test: `tests/test_ai_readiness.py`

- [ ] Add `ai_runbook_report()` describing the safe AI host workflow: capabilities, inspect, plan, validate, policy simulate, dry-run token, execute with human gates.

### Task 4: CLI and MCP resources

**Files:**
- Modify: `cleanwincli/core.py`
- Modify: `cleanwincli/cli.py`
- Modify: `cleanwincli/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] Add `ai-readiness`, `ai-self-test`, and `ai-runbook` CLI commands.
- [ ] Expose `cleanwin://ai/readiness`, `cleanwin://ai/self-test`, and `cleanwin://ai/runbook` resources.

### Task 5: Verification

**Files:**
- Test: `tests/test_ai_readiness.py`
- Test: `tests/test_mcp_server.py`

- [ ] Run `make pytest` from `/Users/bytedance/Codes/sw/cleanwin`.
- [ ] Run `.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests`.
- [ ] Smoke CLI resources with `.venv/bin/python cleanwin.py --json ai-readiness --validate`, `.venv/bin/python cleanwin.py --json ai-self-test`, and `.venv/bin/python cleanwin.py --json ai-runbook`.

### Self-review

- Spec coverage: Covers readiness, self-test, runbook, CLI, MCP resource exposure, tests, and non-destructive safety posture.
- Placeholder scan: No placeholder steps remain.
- Type consistency: Uses `cleanwin.ai-readiness.v1`, `cleanwin.ai-self-test.v1`, and `cleanwin.ai-runbook.v1` consistently.
