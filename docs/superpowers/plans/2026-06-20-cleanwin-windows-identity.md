# CleanWin Windows Identity Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add filesystem identity capture and plan replay checks so CleanWin refuses execution when a candidate changes after plan generation.

**Architecture:** Add a focused `cleanwincli.identity` module that captures stdlib-backed identity fields and compares planned vs current identity. Store identity on each `Candidate`, validate it during plan validation, and re-check it inside the single destructive exit before recycle/delete.

**Tech Stack:** Python 3.10+ stdlib runtime, pathlib/stat/os, pytest.

---

### Task 1: Identity module

**Files:**
- Create: `cleanwincli/identity.py`
- Test: `tests/test_identity.py`

- [ ] Implement `capture_filesystem_identity(path)` with canonical path, type, symlink/junction flags, size, mtime ns, device, file id/inode, mode, and platform-specific stat fields.
- [ ] Implement `compare_identity(planned, current)` and `assert_identity_matches(path, planned)`.

### Task 2: Plan schema integration

**Files:**
- Modify: `cleanwincli/models.py`
- Modify: `cleanwincli/collectors.py`
- Modify: `cleanwincli/core.py`

- [ ] Add optional `identity` to `Candidate` and include it in plan fingerprints.
- [ ] Capture identity in candidate discovery.
- [ ] Require identity for executable candidates and reject mismatches during validate-plan.

### Task 3: Destructive exit replay check

**Files:**
- Modify: `cleanwincli/delete_ops.py`
- Modify: `cleanwincli/core.py`

- [ ] Pass candidate identity into `safe_delete`.
- [ ] Re-check identity immediately before recycle/permanent delete.

### Task 4: Tests and verification

**Files:**
- Create: `tests/test_identity.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_delete_ops.py`

- [ ] Verify generated plan includes identity.
- [ ] Verify validate-plan fails if the candidate is modified after planning.
- [ ] Verify safe_delete fails closed when expected identity mismatches.
- [ ] Run `make pytest` and smoke commands through `.venv/bin/python`.

### Self-review

- Spec coverage: Captures identity, stores in plan, validates on replay, re-checks at destructive exit, and tests TOCTOU behavior.
- Placeholder scan: No placeholders remain.
- Type consistency: `identity` is consistently a JSON object or `None` on `Candidate`.
