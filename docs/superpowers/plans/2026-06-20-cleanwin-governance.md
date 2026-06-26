# Cleanwin Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add executable engineering governance gates for local development, CI, documentation smoke checks, AI readiness, and doctor recommendations without changing cleanup behavior.

**Architecture:** Keep governance outside cleanup planning/execution paths. Add a root `Makefile` as the canonical local entrypoint, expand the existing Windows smoke workflow to run the same quality categories, and make `doctor_report()` advertise the governance commands as machine-readable recommendations.

**Tech Stack:** Python 3.10+, pytest, `compileall`, Ruff, mypy, setuptools build, GitHub Actions on `windows-latest`, PowerShell.

---

## File Structure

- Create `Makefile`: canonical developer and CI command aliases (`test`, `lint`, `type`, `quality`, `package-smoke`, `docs-smoke`, `ai-smoke`, `mcp-smoke`).
- Modify `.github/workflows/windows-smoke.yml`: install dev tooling and run lint/type/package/docs/AI/MCP smoke gates in addition to current Windows destructive-safety smoke tests.
- Modify `cleanwincli/core.py`: extend `doctor_report()` `recommended_commands` with governance commands.
- Modify `tests/test_ai_readiness.py`: assert doctor recommendations include governance gates.

## Tasks

### Task 1: Add local governance entrypoints

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create the Makefile with explicit commands**

```makefile
PYTHON ?= python3
VENV ?= .venv
DEV_PYTHON ?= $(VENV)/bin/python

.PHONY: test lint type compile quality package-smoke docs-smoke ai-smoke mcp-smoke

venv:
	$(PYTHON) -m venv $(VENV)

dev-install: venv
	$(DEV_PYTHON) -m pip install --upgrade pip build
	$(DEV_PYTHON) -m pip install -e ".[dev]"

test:
	$(DEV_PYTHON) -m pytest -q

lint:
	$(DEV_PYTHON) -m ruff check cleanwin.py cleanwincli tests

type:
	$(DEV_PYTHON) -m mypy cleanwin.py cleanwincli tests

compile:
	$(DEV_PYTHON) -m compileall -q cleanwin.py cleanwincli tests

package-smoke:
	$(DEV_PYTHON) -m build --sdist --wheel

docs-smoke:
	test -f docs/doc/README.md
	test -f docs/doc/README.CN.md
	test -s docs/doc/README.md
	test -s docs/doc/README.CN.md

ai-smoke:
	$(DEV_PYTHON) cleanwin.py --json ai-tools --provider validation
	$(DEV_PYTHON) cleanwin.py --json ai-readiness --validate
	$(DEV_PYTHON) cleanwin.py --json ai-self-test
	$(DEV_PYTHON) cleanwin.py --json ai-runbook
	$(DEV_PYTHON) cleanwin.py --json doctor

mcp-smoke:
	$(DEV_PYTHON) -m compileall -q cleanwincli/mcp_server.py

quality: dev-install lint type test compile docs-smoke ai-smoke mcp-smoke package-smoke
```

- [ ] **Step 2: Run local Makefile smoke targets**

Run: `make test docs-smoke ai-smoke mcp-smoke`

Expected: all targets pass.

### Task 2: Expand CI quality gates

**Files:**
- Modify: `.github/workflows/windows-smoke.yml`

- [ ] **Step 1: Install package with dev dependencies**

Insert after Python setup:

```yaml
      - name: Install dev dependencies
        shell: pwsh
        run: |
          python -m venv .venv
          .\.venv\Scripts\python.exe -m pip install --upgrade pip build
          .\.venv\Scripts\python.exe -m pip install -e .[dev]
```

- [ ] **Step 2: Add lint, type, docs, AI, MCP, and package smoke steps**

Add steps before the Windows identity/recycle smoke checks:

```yaml
      - name: Lint
        shell: pwsh
        run: .\.venv\Scripts\python.exe -m ruff check cleanwin.py cleanwincli tests

      - name: Type check
        shell: pwsh
        run: .\.venv\Scripts\python.exe -m mypy cleanwin.py cleanwincli tests

      - name: Docs smoke
        shell: pwsh
        run: |
          if (-not (Test-Path docs/doc/README.md)) { throw "missing docs/doc/README.md" }
          if (-not (Test-Path docs/doc/README.CN.md)) { throw "missing docs/doc/README.CN.md" }
          if ((Get-Item docs/doc/README.md).Length -le 0) { throw "empty docs/doc/README.md" }
          if ((Get-Item docs/doc/README.CN.md).Length -le 0) { throw "empty docs/doc/README.CN.md" }

      - name: AI readiness smoke
        shell: pwsh
        run: |
          .\.venv\Scripts\python.exe cleanwin.py --json ai-tools --provider validation | ConvertFrom-Json | Out-Null
          .\.venv\Scripts\python.exe cleanwin.py --json ai-readiness --validate | ConvertFrom-Json | Out-Null
          .\.venv\Scripts\python.exe cleanwin.py --json ai-self-test | ConvertFrom-Json | Out-Null
          .\.venv\Scripts\python.exe cleanwin.py --json ai-runbook | ConvertFrom-Json | Out-Null
          .\.venv\Scripts\python.exe cleanwin.py --json doctor | ConvertFrom-Json | Out-Null

      - name: MCP server compile smoke
        shell: pwsh
        run: .\.venv\Scripts\python.exe -m compileall -q cleanwincli/mcp_server.py

      - name: Package build smoke
        shell: pwsh
        run: .\.venv\Scripts\python.exe -m build --sdist --wheel
```

- [ ] **Step 3: Run YAML-independent checks locally**

Run: `.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests`

Expected: command exits 0.

### Task 3: Advertise governance commands through doctor

**Files:**
- Modify: `cleanwincli/core.py:361-366`
- Modify: `tests/test_ai_readiness.py:93-103`

- [ ] **Step 1: Update the failing doctor recommendation test**

Add assertions for these command lists:

```python
        assert ["python3", "-m", "ruff", "check", "cleanwin.py", "cleanwincli", "tests"] in report["recommended_commands"]
        assert ["python3", "-m", "mypy", "cleanwin.py", "cleanwincli", "tests"] in report["recommended_commands"]
        assert ["python3", "-m", "build", "--sdist", "--wheel"] in report["recommended_commands"]
        assert ["make", "docs-smoke"] in report["recommended_commands"]
        assert ["make", "ai-smoke"] in report["recommended_commands"]
```

- [ ] **Step 2: Run the focused test and confirm it fails before implementation**

Run: `.venv/bin/python -m pytest tests/test_ai_readiness.py::test_doctor_report_checks_static_safety_and_contracts -q`

Expected: FAIL until `doctor_report()` is updated.

- [ ] **Step 3: Update `doctor_report()` recommended commands**

Add lint, type, build, docs, AI, MCP, and quality aliases to the returned `recommended_commands` list.

- [ ] **Step 4: Run focused test again**

Run: `.venv/bin/python -m pytest tests/test_ai_readiness.py::test_doctor_report_checks_static_safety_and_contracts -q`

Expected: PASS.

### Task 4: Full validation

**Files:**
- Validate all changed files.

- [ ] **Step 1: Run unit tests**

Run: `make pytest`

Expected: PASS, with only expected platform skips.

- [ ] **Step 2: Run compile smoke**

Run: `.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests`

Expected: exits 0.

- [ ] **Step 3: Run doctor smoke**

Run: `.venv/bin/python cleanwin.py --json doctor`

Expected: JSON includes `"ready": true`.

- [ ] **Step 4: Run available quality gates**

Run: `make quality`

Expected: pass if dev dependencies and build backend are available locally; otherwise capture missing-tool failures as environment notes.

## Self-Review

- Spec coverage: plan covers local quality entrypoints, CI gates, docs smoke, AI readiness smoke, package build smoke, and doctor recommendations.
- Placeholder scan: no TBD/TODO/fill-in-later placeholders remain.
- Type consistency: `recommended_commands` remains a list of command-argument lists and tests assert exact list membership.
