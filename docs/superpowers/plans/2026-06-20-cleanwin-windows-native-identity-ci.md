# CleanWin Windows Native Identity and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen CleanWin's Windows identity capture with native Win32 metadata and add Windows CI smoke coverage.

**Architecture:** Keep stdlib identity capture as the portable base and add a separate `windows_identity` backend that enriches identity only on Windows. Add Windows-only integration tests guarded by environment variables and a GitHub Actions workflow that runs pytest plus sandboxed smoke commands.

**Tech Stack:** Python 3.10+ stdlib runtime, ctypes Win32 calls, pytest, GitHub Actions Windows runner.

---

### Task 1: Native Windows identity backend

**Files:**
- Create: `cleanwincli/windows_identity.py`
- Modify: `cleanwincli/identity.py`
- Test: `tests/test_identity.py`

- [ ] Implement `capture_windows_native_identity(path)` using `CreateFileW`, `GetFileInformationByHandle`, and `GetVolumeInformationW`.
- [ ] Merge backend fields into `capture_filesystem_identity()` when `os.name == "nt"`.

### Task 2: Windows smoke tests

**Files:**
- Create: `tests/test_windows_integration.py`

- [ ] Add Windows-only tests for native identity fields.
- [ ] Add gated real recycle smoke skipped unless `CLEANWIN_RUN_WINDOWS_RECYCLE_INTEGRATION=1`.

### Task 3: Windows CI workflow

**Files:**
- Create: `.github/workflows/windows-smoke.yml`

- [ ] Create `.venv`, install `.[dev]`, and run pytest on Windows.
- [ ] Run `.venv\Scripts\python.exe -m compileall -q cleanwin.py cleanwincli tests`.
- [ ] Run identity drift smoke.
- [ ] Run test-mode recycle smoke.

### Task 4: Verification

- [ ] Run `make pytest` on the current platform.
- [ ] Run `.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests`.
- [ ] Run `.venv/bin/python cleanwin.py --json plan --categories temp --max-items 1` as an identity smoke command.

### Self-review

- Spec coverage: Native Windows identity backend, gated integration tests, and Windows CI smoke are covered.
- Placeholder scan: No placeholders remain.
- Type consistency: Native fields use `windows_native_*` prefixes and do not replace portable strict fields.
