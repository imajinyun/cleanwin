# CleanWin Common App Uninstall Leftovers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative safe category for common Windows software uninstall leftovers, focusing on cache and log garbage while avoiding profiles, credentials, documents, and active installations.

**Architecture:** Extend the existing collector model with an `app-leftovers` safe category. Implement rule-driven known app cache/log paths in `cleanwincli/collectors.py`, keep category exposure in `cleanwincli/protection_data.py` and `cleanwincli/core.py`, and validate behavior through CLI tests and schema samples.

**Tech Stack:** Python 3.10+ stdlib runtime, pytest, existing JSON CLI contracts, existing dry-run/plan/validate/execute safety gates.

---

## File Structure

- Modify: `cleanwincli/protection_data.py` — add `app-leftovers` to `DEFAULT_SAFE_CATEGORIES`.
- Modify: `cleanwincli/collectors.py` — add rule data and collector logic for common app cache/log leftovers.
- Modify: `cleanwincli/ai_versioning.py` — add a schema sample candidate for `app-leftovers`.
- Modify: `tests/test_cli.py` — add tests for candidate discovery, active-install guard, rule filtering, and plan review.
- Modify: `README.md`, `README.CN.md`, `docs/doc/README.md`, `docs/doc/README.CN.md` — document the new category.

---

### Task 1: Add failing CLI coverage for app leftovers

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add a test that discovers common app cache/log leftovers.**

Add this pytest function:

```python
def test_app_leftovers_scans_common_uninstalled_app_cache_and_logs(tmp_path, cleanwin_json) -> None:
    roaming = tmp_path / "Roaming"
    local = tmp_path / "LocalAppData"

    slack_cache = roaming / "Slack" / "Cache"
    slack_cache.mkdir(parents=True)
    (slack_cache / "entry").write_text("slack", encoding="utf-8")

    teams_logs = roaming / "Microsoft" / "Teams" / "logs"
    teams_logs.mkdir(parents=True)
    (teams_logs / "current.log").write_text("teams", encoding="utf-8")

    vscode_cache = roaming / "Code" / "CachedData"
    vscode_cache.mkdir(parents=True)
    (vscode_cache / "cache.bin").write_text("code", encoding="utf-8")

    jetbrains_logs = local / "JetBrains" / "PyCharm2024.1" / "log"
    jetbrains_logs.mkdir(parents=True)
    (jetbrains_logs / "idea.log").write_text("jetbrains", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(tmp_path / "User")},
    )

    paths = {candidate["path"] for candidate in payload["candidates"]}
    assert payload["summary"]["candidate_count"] == 4
    assert {str(slack_cache), str(teams_logs), str(vscode_cache), str(jetbrains_logs)} <= paths
    assert all(candidate["category"] == "app-leftovers" for candidate in payload["candidates"])
    assert all(candidate["delete_mode"] == "recycle" for candidate in payload["candidates"])
```

- [ ] **Step 2: Add a test that active install markers prevent cleanup candidates.**

Add this pytest function:

```python
def test_app_leftovers_skips_when_active_install_marker_exists(tmp_path, cleanwin_json) -> None:
    roaming = tmp_path / "Roaming"
    local = tmp_path / "LocalAppData"
    slack_cache = roaming / "Slack" / "Cache"
    slack_cache.mkdir(parents=True)
    (slack_cache / "entry").write_text("slack", encoding="utf-8")

    active_marker = local / "slack" / "slack.exe"
    active_marker.parent.mkdir(parents=True)
    active_marker.write_text("exe", encoding="utf-8")

    payload = cleanwin_json(
        "inspect",
        "--categories",
        "app-leftovers",
        "--older-than-days",
        "0",
        env={"APPDATA": str(roaming), "LOCALAPPDATA": str(local), "USERPROFILE": str(tmp_path / "User")},
    )

    assert payload["summary"]["candidate_count"] == 0
```

- [ ] **Step 3: Run the targeted tests and verify they fail before implementation.**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_app_leftovers_scans_common_uninstalled_app_cache_and_logs tests/test_cli.py::test_app_leftovers_skips_when_active_install_marker_exists -q
```

Expected: fail because `app-leftovers` is not registered and no candidates are collected.

---

### Task 2: Implement rule-driven app-leftovers collection

**Files:**
- Modify: `cleanwincli/protection_data.py`
- Modify: `cleanwincli/collectors.py`

- [ ] **Step 1: Register the safe category.**

Change `DEFAULT_SAFE_CATEGORIES` to:

```python
DEFAULT_SAFE_CATEGORIES = frozenset({"temp", "dev-cache", "package-cache", "browser-cache", "app-leftovers"})
```

- [ ] **Step 2: Add app leftover rule data to `cleanwincli/collectors.py`.**

Add `APP_LEFTOVER_RULES` with paths for Slack, Teams classic, Discord, Zoom, VS Code, JetBrains, Docker Desktop logs, Postman, Notion, Figma, OBS Studio, and Spotify caches/logs. Each rule must include `rule_id`, `owner`, `default`, `active_markers`, `official_cleanup_command`, and `rationale`.

- [ ] **Step 3: Add helper functions for active install detection and wildcard paths.**

Implement helpers that resolve `local:`, `roaming:`, `programfiles:`, `programfilesx86:`, and `home:` prefixes, expand globbed path segments such as `*`, `app-*`, and `*.exe`, and skip rules when any active marker exists.

- [ ] **Step 4: Add `app-leftovers` to `collect_candidates`.**

For each matching rule root, create a `Candidate` with:

```python
category="app-leftovers"
reason=f"{rule['owner']} uninstall leftover cache/log at {root}"
rule_id=rule["rule_id"]
cache_owner=rule["owner"]
official_cleanup_command=rule["official_cleanup_command"]
safe_to_delete_rationale=rule["rationale"]
```

- [ ] **Step 5: Run targeted tests.**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_app_leftovers_scans_common_uninstalled_app_cache_and_logs tests/test_cli.py::test_app_leftovers_skips_when_active_install_marker_exists -q
```

Expected: both tests pass.

---

### Task 3: Add rule filtering, review, and schema sample coverage

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `cleanwincli/ai_versioning.py`

- [ ] **Step 1: Add a rule-id filtering and dry-run test.**

Add a test that creates Slack and VS Code leftovers, plans only `app-leftovers.vscode.cached-data`, reviews the plan, verifies the official cleanup command, and dry-runs the resulting plan.

- [ ] **Step 2: Update schema samples.**

Add `_sample_app_leftover_candidate()` and include it in the `cleanwin.inspect.v1` sample `categories`, `filters.rule_ids`, `candidates`, and `summary` count.

- [ ] **Step 3: Run schema and CLI targeted tests.**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_ai_contracts.py -q
```

Expected: pass.

---

### Task 4: Update docs and validate end-to-end

**Files:**
- Modify: `README.md`
- Modify: `README.CN.md`
- Modify: `docs/doc/README.md`
- Modify: `docs/doc/README.CN.md`

- [ ] **Step 1: Add `app-leftovers` to quick-start examples and highlights where categories are listed.**

- [ ] **Step 2: Document the category in the detailed cleanup category table.**

Describe it as common uninstalled app cache/log leftovers for Slack, Teams classic, Discord, Zoom, VS Code, JetBrains, Docker Desktop logs, Postman, Notion, Figma, OBS Studio, and Spotify, with active-install guards.

- [ ] **Step 3: Run full validation.**

Run:

```bash
make pytest
.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests
.venv/bin/python cleanwin.py --json capabilities
.venv/bin/python cleanwin.py --json inspect --categories app-leftovers --max-items 10
.venv/bin/python cleanwin.py --json ai-tools --provider parity
.venv/bin/python cleanwin.py --json ai-readiness --validate
```

Expected: all commands pass.

---

## Self-review

- Spec coverage: The plan adds next-stage implementation for common software uninstall cache/log cleanup, keeps dry-run/plan/recycle gates, and updates docs/tests.
- Placeholder scan: No TBD/TODO/placeholder steps remain.
- Type consistency: The category is consistently named `app-leftovers`; rule IDs use the `app-leftovers.<app>.<leaf>` pattern; candidates reuse existing `Candidate` fields.
