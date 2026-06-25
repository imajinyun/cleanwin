# 🧹 cleanwin — Full Guide

> **Conservative Windows cleanup planner · dry-run first · plan-based execution · AI/MCP ready**

cleanwin is a Python CLI for inspecting Windows cleanup opportunities, producing machine-readable plans, validating those plans, and executing only after explicit human confirmation gates. It is intentionally conservative: the default path is read-only or dry-run, and real deletion is routed through one safety exit.

- Root README: [../../README.md](../../README.md)
- 中文文档: [README.CN.md](README.CN.md)

---

## 🚀 Quick Start

```bash
# Show capabilities, categories, and safety defaults
python3 cleanwin.py --json capabilities

# Preview safe cleanup candidates only
python3 cleanwin.py --json inspect --categories temp,dev-cache,package-cache,browser-cache,app-leftovers --max-items 10

# Generate a reusable cleanup plan
python3 cleanwin.py --json plan --categories temp,dev-cache,app-leftovers --older-than-days 7 --output /tmp/cleanwin-plan.json

# Validate and review before doing anything destructive
python3 cleanwin.py --json validate-plan --plan-file /tmp/cleanwin-plan.json
python3 cleanwin.py --json review-plan --plan-file /tmp/cleanwin-plan.json

# Dry-run the plan; this returns a confirmation token for a matching execution
python3 cleanwin.py --json execute-plan --plan-file /tmp/cleanwin-plan.json
```

> 🛡️ `execute-plan` without `--execute` does **not** delete files. A real execution requires `--execute`, `--yes`, an operation log, the exact confirmation phrase, and the dry-run confirmation token.

---

## 📦 Installation

cleanwin has no runtime dependencies and requires Python 3.10+.

```bash
# Run from source
python3 cleanwin.py --json capabilities

# Install as an editable Python package
python3 -m pip install -e .
cleanwin --json capabilities

# MCP entrypoint installed by pyproject.toml
cleanwin-mcp
```

Project metadata lives in `pyproject.toml`; the console scripts are `cleanwin` and `cleanwin-mcp`.

---

## ✨ Highlights

| Area | What cleanwin does |
|---|---|
| 🧹 Dry-run first | Inspection, planning, validation, review, and plan dry-run are safe defaults |
| 🪟 Windows-aware policy | Rejects Windows roots, profile roots, credentials, browser profile data, WSL/Docker data, and servicing stores |
| ♻️ Recycle-first deletion | Real execution uses Windows Recycle Bin; non-Windows real recycle execution fails closed outside test mode |
| 🧾 Plan integrity | Plans include `cleanwin.plan.v1`, source fingerprint, host context, filesystem identity, category, rule, and rationale metadata |
| 🤖 AI-native contracts | Exports 12 structured tools, provider formats, workflow routing, environment indexing, host policy, readiness, runbook, and self-test reports |
| 🏗️ MCP stdio server | Serves structured MCP tools and resources without accepting raw shell commands |
| 🔐 Single deletion exit | Destructive cleanup goes through `cleanwincli.delete_ops.safe_delete` |

---

## 🛡️ Safety Model

cleanwin is designed around fail-closed cleanup:

1. **No delete by default** — `inspect`, `plan`, `validate-plan`, `review-plan`, and `execute-plan` without `--execute` are non-destructive.
2. **Plan before execution** — execution consumes a previously generated plan instead of ad-hoc paths.
3. **Source fingerprint** — plan validation verifies that the payload still matches its `source_fingerprint`.
4. **Host/user context** — by default, plan validation rejects mismatched user/home context.
5. **Filesystem identity** — candidates record identity metadata; validation catches drift before execution.
6. **Recycle mode only in MVP execution** — supported execution plans must use `delete_mode: recycle`.
7. **Human gates** — real execution requires `--execute`, `--yes`, `--operation-log`, exact confirmation phrase, and dry-run token.
8. **Single destructive primitive** — only `cleanwincli.delete_ops.safe_delete` owns deletion routing.
9. **Fail-closed recycle routing** — if Recycle Bin routing is unavailable, fails, or is unsafe, cleanwin does not silently fall back to permanent deletion.

Real execution gates:

```text
validated plan
  + --execute
  + --yes
  + --operation-log <jsonl path>
  + --confirmation-phrase "确认执行 cleanwin 清理"
  + --confirmation-token <token emitted by matching dry-run>
  + delete_mode == recycle
```

---

## 🧹 Cleanup Categories

### Safe candidate categories

These categories may produce `candidates` when matching files/directories exist and pass path validation.

| Category | Scope | Notes |
|---|---|---|
| `temp` | `%TEMP%`, `%TMP%`, `%LOCALAPPDATA%\Temp` | Only older entries, skips symlinks/reparse points |
| `dev-cache` | pip, npm, Yarn, pnpm, NuGet, Cargo, Go, Gradle, Maven caches | Includes owner, rule ID, official cleanup command, and safe-to-delete rationale |
| `package-cache` | WinGet, Scoop, Chocolatey, uv caches | Targets package payload/cache artifacts that can be re-downloaded |
| `browser-cache` | Cache-only directories for Chrome, Edge, and Firefox | Protects cookies, passwords, sessions, extensions, and profile databases |
| `app-leftovers` | Common app cache/log leftovers after uninstall | Covers reviewed leftovers like Slack, Teams classic, Discord, Zoom, VS Code, JetBrains logs, Docker Desktop logs, Postman, Notion, Figma, OBS Studio, and Spotify cache/logs; skips paths when active install markers still exist, including globbed versioned install markers such as `app-*` and `*.exe` |

Example:

```bash
python3 cleanwin.py --json inspect --categories app-leftovers --rule-id app-leftovers.vscode.cached-data --older-than-days 0
```

### Read-only report categories

These categories intentionally produce `findings`, not deletion candidates.

| Category | Why read-only |
|---|---|
| `registry-report` | Registry deletion is high risk and should use backups/vendor tools/manual review |
| `startup-report` | Startup entries may be policy-managed or required by security/update tooling |
| `windows-report` | WinSxS, Installer, SoftwareDistribution, Defender, and Delivery Optimization require official Windows tools |
| `large-files` | Downloads, Desktop, Documents, OneDrive, and SharePoint often contain user data |
| `docker-report` | Volumes, images, BuildKit cache, and WSL disk images may contain durable state |
| `wsl-report` | Distributions and `ext4.vhdx` files must not be deleted directly |
| `visual-studio-report` | Installer state and workloads should be managed by Visual Studio Installer / official commands |
| `browser-cache-report` | Browser profile roots mix cache with credentials, sessions, and synced data |

---

## 💻 CLI Reference

### `capabilities`

Show machine-readable capabilities and safety defaults.

```bash
python3 cleanwin.py --json capabilities
```

Key fields include `default_dry_run`, `safe_categories`, `read_only_categories`, `never_auto_execute`, `default_delete_mode`, and the AI confirmation phrase.

### `inspect`

Preview candidates and findings.

```bash
python3 cleanwin.py --json inspect \
  --categories temp,dev-cache,package-cache,browser-cache,app-leftovers \
  --older-than-days 7 \
  --max-items 100
```

Options:

| Option | Description |
|---|---|
| `--categories` | Comma-separated category list; defaults to safe categories |
| `--older-than-days` | Only consider entries older than this threshold |
| `--max-items` | Maximum candidate count |
| `--rule-id` | Filter by one or more rule IDs; repeatable and comma-separated |

### `plan`

Create a reusable `cleanwin.plan.v1` payload.

```bash
python3 cleanwin.py --json plan \
  --categories temp,dev-cache,app-leftovers \
  --older-than-days 7 \
  --max-items 50 \
  --output /tmp/cleanwin-plan.json
```

### `validate-plan`

Validate schema, fingerprint, host context, candidate safety, identity, and execution mode.

```bash
python3 cleanwin.py --json validate-plan --plan-file /tmp/cleanwin-plan.json
```

Use `--no-require-plan-context` only for controlled tests where plan context intentionally differs.

### `review-plan`

Summarize a plan for human or AI review.

```bash
python3 cleanwin.py --json review-plan --plan-file /tmp/cleanwin-plan.json
```

The review output includes candidate summaries, rule summaries, official cleanup commands, sensitive exclusions, and execution handoff requirements.

### `execute-plan`

Dry-run by default:

```bash
python3 cleanwin.py --json execute-plan --plan-file /tmp/cleanwin-plan.json
```

The dry-run response contains:

- `dry_run: true`
- per-candidate dry-run results
- `confirmation.required_phrase`
- `confirmation.confirmation_token`

Real execution example structure:

```bash
python3 cleanwin.py --json execute-plan \
  --plan-file /tmp/cleanwin-plan.json \
  --execute \
  --yes \
  --operation-log "$HOME/.cleanwin/operations.jsonl" \
  --confirmation-phrase "确认执行 cleanwin 清理" \
  --confirmation-token "<token-from-matching-dry-run>"
```

> On non-Windows platforms, real recycle execution fails closed unless `CLEANWIN_TEST_MODE=1` is used for tests.

### AI and governance commands

```bash
python3 cleanwin.py --json ai-tools
python3 cleanwin.py --json ai-tools --provider openai
python3 cleanwin.py --json ai-tools --provider anthropic
python3 cleanwin.py --json schema-registry
python3 cleanwin.py --json host-policy --validate
python3 cleanwin.py --json ai-readiness --validate
python3 cleanwin.py --json ai-self-test
python3 cleanwin.py --json ai-runbook
python3 cleanwin.py --json doctor
python3 cleanwin.py --json recovery-readiness
python3 cleanwin.py --json installed-app-inventory
python3 cleanwin.py --json official-command-plan
python3 cleanwin.py --json debloat-privacy-report
python3 cleanwin.py --json startup-service-inventory
```

---

## 🤖 AI Invocation Patterns

cleanwin exposes 8 AI tools:

| Tool | Risk | Auto-call | Purpose |
|---|---:|---:|---|
| `cleanwin_capabilities` | readonly | yes | Discover categories, schemas, and safety defaults |
| `cleanwin_inspect` | readonly | yes | Preview candidates/findings |
| `cleanwin_generate_plan` | planning | yes | Generate a plan file |
| `cleanwin_validate_plan` | planning | yes | Validate a plan before dry-run/execution |
| `cleanwin_review_plan` | planning | yes | Summarize a plan for review handoff |
| `cleanwin_policy_simulate` | planning | yes | Simulate AI host execution policy |
| `cleanwin_dry_run_plan` | dry-run | yes | Dry-run a plan and produce confirmation token |
| `cleanwin_execute_plan` | destructive | no | Execute only with human gates satisfied |

Recommended AI host flow:

```text
cleanwin_capabilities
  → cleanwin_inspect
  → cleanwin_generate_plan
  → cleanwin_validate_plan
  → cleanwin_review_plan
  → cleanwin_policy_simulate
  → cleanwin_dry_run_plan
  → human approval
  → cleanwin_execute_plan
```

AI host rules:

- Never pass raw shell commands; tool arguments are structured JSON only.
- Never auto-call `cleanwin_execute_plan`.
- Require `delete_mode: recycle` for destructive execution.
- Require `operation_log`, `confirmation_phrase`, and `confirmation_token`.
- Use `policy-simulate` before execution to verify host-side gates.

---

## 🏗️ MCP Server

cleanwin includes a stdio MCP server:

```bash
python3 -m cleanwincli.mcp_server
# or after installation
cleanwin-mcp
```

The server:

- Exposes the cleanwin AI tool catalog as MCP tools.
- Builds argv from registered templates.
- Rejects unknown tools and invalid arguments.
- Denies raw command arguments.
- Applies cleanwin host-policy checks before calling the CLI.
- Exposes resources such as `cleanwin://ai/tools`, `cleanwin://ai/host-policy`, `cleanwin://ai/readiness`, `cleanwin://ai/self-test`, `cleanwin://engineering/doctor`, `cleanwin://engineering/recovery-readiness`, `cleanwin://inventory/installed-apps`, `cleanwin://plan/official-command-plan`, `cleanwin://inventory/debloat-privacy`, and `cleanwin://inventory/startup-services`.

To point the MCP server at a specific CLI script or binary:

```bash
CLEANWIN_CLI=/absolute/path/to/cleanwin.py python3 -m cleanwincli.mcp_server
```

---

## 🧪 Safe Test-mode Execution

Test mode is for controlled development and CI only. It routes recycle operations to a sandbox trash directory instead of the Windows Recycle Bin.

```bash
tmpdir=$(mktemp -d)
mkdir -p "$tmpdir/Temp"
printf 'cache' > "$tmpdir/Temp/stale.tmp"

TEMP="$tmpdir/Temp" TMP="$tmpdir/Temp" CLEANWIN_TEST_MODE=1 \
  python3 cleanwin.py --json plan --categories temp --older-than-days 0 --output "$tmpdir/plan.json"

TEMP="$tmpdir/Temp" TMP="$tmpdir/Temp" CLEANWIN_TEST_MODE=1 \
  python3 cleanwin.py --json execute-plan --plan-file "$tmpdir/plan.json" --no-require-plan-context
```

Use the dry-run output token only for the same plan payload.

---

## ✅ Development & CI

Common local checks run through a project virtual environment:

```bash
make dev-install
make ci-smoke
make quality
```

The `dev-install` target creates `.venv`, installs `.[dev]`, and uses that environment for pytest, Ruff, mypy, compile, package, AI, and MCP checks. `make ci-smoke` mirrors the non-packaging CI gate, while `make quality` adds install/package smoke checks and cleanup. Equivalent manual commands:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check cleanwin.py cleanwincli tests
.venv/bin/python -m mypy cleanwin.py cleanwincli tests
.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests
.venv/bin/python cleanwin.py --json ai-readiness --validate
.venv/bin/python cleanwin.py --json doctor
```

New tests should prefer pytest function style with native `assert`, `tmp_path`, `monkeypatch`, `pytest.raises`, and `pytest.mark.parametrize`. Put reusable subprocess or JSON helpers in `tests/conftest.py` or focused MCP helpers instead of repeating `unittest.TestCase` setup methods. Reuse shared helpers for payload schemas, read-only payloads and reports, `safe_to_execute`, execution-disabled contracts, schema registry samples, command sequences, summary counts, dry-run result summaries, and boolean status fields such as `valid`, `ready`, `passed`, and `allowed`. Use the collection and text helpers for repeated expected membership, absence, and substring checks; keep direct `in`/`not in` assertions for isolated one-off checks. Use `assert_any_match`, `assert_all_match`, and `assert_none_match` for repeated `any(...)` / `all(...)` style checks over structured collections. Use `assert_field_values`, `assert_fields_present`, and `field_value` for repeated structured field checks; dot paths support nested dictionaries and numeric list indexes such as `rule_summary.0.rule_id`. Use `assert_exact_sequence`, `assert_exact_set`, `assert_unique_items`, `assert_non_empty`, and `assert_returncode` for repeated strict sequence, set, uniqueness, non-empty, and subprocess return-code checks. Use `assert_exact_count`, `assert_at_least`, `assert_one_of`, and `assert_text_contains_any` for repeated exact count, lower-bound, scalar membership, and any-fragment text checks. Use `assert_path_exists` and `assert_path_missing` for repeated filesystem existence checks. Exception-path tests should assert the error contract with `pytest.raises(..., match=...)`.

Pytest governance smoke:

```bash
make pytest-governance-smoke
```

This guard keeps test updates pytest-native, keeps direct CLI subprocess calls in shared helpers, requires `pytest.raises` message checks, keeps legacy direct schema, read-only boolean, `safe_to_execute`, execution-disabled flag, status, summary, and predicate assertion budgets empty, verifies collection/text/predicate/field/exact/scalar/path helper adoption for migrated files, and checks that CI and Docker sandbox paths do not reintroduce `unittest discover` or bypass the project `.venv`.

Optional Docker sandbox:

```bash
make docker-quality
```

CI entrypoint:

- `.github/workflows/ci.yml` runs Linux quality gates on Python 3.10 and 3.12, package install smoke checks, and the optional Docker sandbox gate.
- `.github/workflows/windows-smoke.yml` creates `.venv`, installs `.[dev]`, and runs pytest, Ruff, mypy, compile checks, identity drift smoke, and test-mode recycle smoke on `windows-latest`.

Governance roadmap:

- [Windows cleaner gap roadmap](../governance/windows-cleaner-gap-roadmap.md) tracks prioritized TODOs for cleaner coverage, read-only evidence, recovery gates, and future execution model expansion.

---

## 🗺️ Project Map

| Path | Responsibility |
|---|---|
| `cleanwin.py` | Thin CLI entrypoint |
| `cleanwincli/cli.py` | Argument parsing and command dispatch |
| `cleanwincli/core.py` | Inspect/plan/validate/review/execute orchestration and reports |
| `cleanwincli/collectors.py` | Conservative candidate and read-only finding collectors |
| `cleanwincli/rule_catalog.py` | Versioned cleanup rule catalog loader and validation |
| `cleanwincli/rules/cleanup_rules.v1.json` | Governed cleanup rule catalog data |
| `cleanwincli/recovery.py` | Recovery readiness gates and snapshot format declarations |
| `cleanwincli/installed_apps.py` | Read-only installed app inventory and leftover correlation |
| `cleanwincli/official_commands.py` | Read-only official Windows cleanup command plans |
| `cleanwincli/debloat_privacy.py` | Read-only debloat and privacy telemetry reporting |
| `cleanwincli/startup_inventory.py` | Read-only startup, service, and task inventory |
| `cleanwincli/protection_data.py` | Windows safety policy data |
| `cleanwincli/protection.py` | Path and filesystem candidate validation |
| `cleanwincli/delete_ops.py` | Single destructive exit and recycle/permanent routing primitives |
| `cleanwincli/operation_log.py` | JSONL operation log writer |
| `cleanwincli/ai_schema.py` | AI tool contracts and provider exports |
| `cleanwincli/ai_host_policy.py` | AI host allow/deny gates |
| `cleanwincli/mcp_server.py` | MCP stdio server |
| `tests/` | Unit and contract tests |

---

## 🔒 Non-goals

cleanwin intentionally does not:

- Clean the Windows Registry automatically.
- Disable startup entries automatically.
- Delete Windows component stores directly.
- Delete browser credentials, cookies, sessions, or profile databases.
- Delete user Documents/Desktop/Downloads/OneDrive/SharePoint automatically.
- Accept raw shell commands through AI/MCP tools.
