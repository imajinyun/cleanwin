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
| `app-leftovers` | Common app cache/log leftovers after uninstall | Covers reviewed leftovers like Slack, Teams classic/new Teams, Discord, Zoom, Skype, Webex, Viber, Element, RingCentral, BlueJeans, VS Code, Visual Studio/DataGrip logs, Docker Desktop logs, Postman, Notion, Figma, OBS Studio, Streamlabs/XSplit/Bandicam/Action diagnostics, Spotify, Adobe Creative Cloud, Office telemetry, game launchers, GPU shader caches, Telegram, Signal, WhatsApp, Cursor, Android Studio, VirtualBox logs, VMware/Genymotion/BlueStacks/Nox/LDPlayer diagnostics, Ollama/LM Studio/Jan/GPT4All/Pinokio diagnostics, Fiddler/Charles diagnostics, Tailscale/ZeroTier/RustDesk diagnostics, Moonlight/Sunshine logs, VLC artwork cache, 1Password/KeePassXC/Bitwarden diagnostics, GitHub Desktop, Obsidian, Unity Hub, Unreal/EA/GOG/Ubisoft launcher caches, Backblaze/Acronis/Macrium/FreeFileSync diagnostics, Dropbox/Box/MEGAsync logs, Nextcloud/ownCloud/pCloud/Syncthing/Resilio Sync diagnostics, GoodSync/Duplicati/KopiaUI backup diagnostics, Cyberduck/Mountain Duck/TeraCopy/Rclone Browser logs, OneDrive/Google Drive/iCloud diagnostics, Plex/Jellyfin diagnostics, iTunes/Kindle/Audible diagnostics, Everything crash dumps, SumatraPDF/Foxit diagnostics, Thunderbird/Mailbird/eM Client diagnostics, Zotero/Mendeley diagnostics, DaVinci Resolve/Shotcut/Kdenlive diagnostics or renderer caches, REAPER/FL Studio/Ableton/Cubase/Voicemeeter/Voicemod diagnostics, Cura/PrusaSlicer/Bambu Studio/OrcaSlicer/CHITUBOX/Lychee Slicer logs, FreeCAD/SOLIDWORKS crash dumps, OpenSCAD/Fusion logs, CCleaner/Revo/BleachBit diagnostics, WinDirStat/WizTree/TreeSize leftovers, HWiNFO/CPU-Z/GPU-Z diagnostics, IrfanView/XnView MP/FastStone thumbnail caches, paint.net crash dumps, nomacs/mpv caches, foobar2000/AIMP/MPC-HC/PotPlayer logs, Notepad++ reviewed backup leftovers, Sublime Text cache, 7-Zip/WinRAR/PeaZip/Bandizip/NanaZip crash dumps, Rufus/Ventoy/Win32 Disk Imager crash dumps, balenaEtcher/Raspberry Pi Imager logs, PuTTY/Alacritty crash dumps, SuperPuTTY/mRemoteNG/Termius/MobaXterm/Royal TS/Bitvise SSH Client logs, Cygwin/MSYS2 setup logs, Malwarebytes/NordVPN/Proton VPN/Mullvad VPN diagnostics, Todoist, Linear, Canva, PowerShell startup cache, Windows Terminal diagnostics, Snagit/Camtasia/ShareX/Greenshot/Lightshot/ScreenToGif logs, remote access and VPN diagnostics, Wireshark/FileZilla/WinSCP state or logs, calibre cache, qBittorrent logs, Git client diagnostics, Git Extensions/GitAhead logs, Kubernetes/container desktop diagnostics, database/API client diagnostics, MongoDB Compass/RedisInsight renderer caches, note app renderer caches, image/media tool caches, design tool caches, Markdown tool renderer caches, scanner utility logs, OEM support diagnostics, creator utility logs, printing utility logs, PowerToys logs, Logitech G HUB logs, Corsair iCUE logs, SteelSeries GG logs, Wacom logs, and Razer Synapse logs; skips paths when active install markers still exist, including globbed versioned install markers such as `app-*`, package version folders, IDE version folders, and `*.exe` |

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
>
> Controlled execution is limited to low-risk regenerable cache categories:
> `temp`, `dev-cache`, `package-cache`, and `browser-cache`. Each executable
> candidate must remain `recycle` mode, non-admin scoped, identity-checked, and
> include a regeneration rationale. Higher-risk surfaces such as
> `app-leftovers`, registry, startup, services, tasks, AppX, Windows components,
> installer cache, and Recycle Bin remain report/plan/validation only.

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
python3 cleanwin.py --json windows-inventory
python3 cleanwin.py --json official-command-plan
python3 cleanwin.py --json rule-pack-catalog
python3 cleanwin.py --json rule-quality-dashboard
python3 cleanwin.py --json browser-profile-inventory
python3 cleanwin.py --json debloat-privacy-report
python3 cleanwin.py --json registry-privacy-plan
python3 cleanwin.py --json appx-removal-plan
python3 cleanwin.py --json service-task-disable-plan
python3 cleanwin.py --json rollback-drill-report
python3 cleanwin.py --json startup-service-inventory
python3 cleanwin.py --json windows-native-artifacts
python3 cleanwin.py --json external-rule-translate --input ./winapp2.ini --format winapp2
```

`installed-app-inventory` is read-only and correlates registry uninstall
entries, Scoop, Chocolatey, portable app locations, and cleanup rule ownership
before treating leftovers as cleanup candidates. Leftover correlations include
structured evidence links for publisher, install location, uninstall key,
product code, winget id, Scoop/Chocolatey package id, and package manager
source, while keeping all uninstall and cleanup actions disabled.

`windows-inventory` is read-only and includes a collection plan for every
Windows-native evidence source. Each section records the intended command argv,
collection method, Windows-only status, admin requirement, expected artifact
schema, promotion gate, and failure modes while keeping `executes_by_report`
false. AppX and provisioned AppX entries include a CleanWin classification
contract for `framework`, `system`, `consumer-app`, `oem`, and `unknown`
packages, with default protection, manual-review guidance, and future user
profile impact for provisioned packages. The AppX collection plans also expose
artifact contracts for `cleanwin.appx-package-snapshot.v1` and
`cleanwin.provisioned-appx-package-snapshot.v1`, including identity fields,
required snapshot fields, classification inputs, rollback reference fields, and
golden-fixture requirements. These contracts are report-only and do not run
PowerShell or remove packages.

`debloat-privacy-report` is report-only and now covers a 125-check Windows
privacy policy baseline including telemetry, Advertising ID, consumer features,
Copilot, Recall/WindowsAI, tailored experiences, activity history, feedback
prompts, Diagnostic Data Viewer, Cortana/Search, Search web/Bing/location
history, Spotlight and lock-screen content, ContentDeliveryManager suggestions,
Windows experimentation/preview builds, cloud clipboard and shared experiences,
location and Find My Device, speech and input personalization, app permissions,
SmartScreen, Widgets, and Edge SmartScreen/search/autofill/metrics/prediction
policies. It also classifies bundled AppX packages for manual review without
uninstalling or changing policy.

`registry-privacy-plan` turns review-recommended registry privacy findings into
a simulation-only change/revert plan. Each planned change carries registry
export requirements, previous value, target value, managed-device detection,
policy owner review, dry-run confirmation token requirements, and a restore
command. The validator reports missing evidence and keeps registry execution
disabled.

`appx-removal-plan` turns Windows inventory AppX classifications into a
simulation-only per-user remove/revert plan. Only consumer-app packages that are
not framework, system, dependency, non-removable, or provisioned targets can
enter the planned changes. Framework, unknown, OEM, system, dependency,
non-removable, and provisioned packages are reported as blocked with explicit
reasons. The report never runs PowerShell or removes packages.

`service-task-disable-plan` turns startup/service inventory findings into a
simulation-only disable/revert plan for curated third-party updater, helper,
agent, and launcher style services or scheduled tasks. Each planned change
requires service registry export or scheduled task XML export, current state,
dependency/trigger/recovery review, restore command, rollback metadata, and a
matching dry-run token before any future promotion. Microsoft, security,
driver, update, boot/system, SYSTEM principal, unresolved, and non-curated
targets are blocked with explicit reasons. The report never stops services,
disables scheduled tasks, edits registry values, or runs `sc.exe`/`schtasks`.

`rollback-drill-report` is fixture-only and verifies rollback metadata
completeness for the future execution surfaces: registry privacy import,
scheduled task XML restore, service start type restore, and AppX restore
metadata. Each drill records a snapshot-to-action-to-rollback-to-verification
chain with snapshot refs, restore command, required metadata, and post-rollback
checks. The registry privacy drill also exposes a
`cleanwin.registry-privacy-rollback-drill.v1` fixture with export/import
commands, before/target/after values, dry-run token evidence, managed-device and
policy-owner review requirements, and post-rollback assertions. The AppX drill
also exposes a `cleanwin.appx-per-user-rollback-drill.v1` fixture scoped to
per-user, non-provisioned packages, with package identity, snapshot ref,
Add-AppxPackage restore metadata, blocked target classes, dry-run token
evidence, and registration-state rollback assertions. The report never imports
registry files, recreates scheduled tasks, changes service start types, or
reinstalls AppX packages.

`startup-service-inventory` remains read-only and reports registry Run entries,
StartupApproved state, Winlogon/Shell extension surfaces, startup folders,
services, driver services, and scheduled tasks. Service and task entries include
target existence/status, start-type or run-level classification, dependency,
trigger/recovery, and required snapshot evidence fields such as `sc.exe qc`,
`Get-CimInstance Win32_Service`, and scheduled task XML exports. The report
never disables entries, stops services, edits registry values, or executes
`schtasks`/`sc.exe`.

`windows-native-artifacts` defines the read-only collection contracts and
fixture parsers for Windows-native evidence sources: PowerShell AppX and
provisioned AppX inventory, registry exports, scheduled task XML/CSV, `sc.exe
qc`, WinGet, Scoop, Chocolatey, DISM features, and DISM component-store
analysis. The report describes command argv, expected artifact schemas,
protected surfaces, parser names, and the implemented read-only wrapper
`scripts/collect-cleanwin-artifacts.ps1`. The wrapper writes artifacts only to
an operator-provided artifact root and emits a
`cleanwin.windows-native-collector-manifest.v1` JSON manifest with hashes,
availability, command display text, and collector metadata. It does not run
cleanup, repair, remove, import, disable, uninstall, or registry mutation
commands.

`promotion-gates` defines report-to-execution contracts for high-risk surfaces.
Windows inventory findings for AppX/provisioned packages, Windows Features,
Component Store, Installer cache, and Recycle Bin remain report-only until
snapshot evidence, rollback metadata, focused tests, and explicit human review
are present.
Startup, service, and scheduled task promotion gates now require the same
evidence emitted by `startup-service-inventory`, including target status,
service dependency/trigger/recovery review, service registry export, and
scheduled task XML export. These gates are still non-executable contracts.
The promotion gate validator can compare a source report schema and a proposed
action contract, then return missing evidence, snapshots, rollback metadata,
tests, and human confirmations without enabling execution.

`external-rule-translate` parses a local `winapp2.ini` or CleanerML XML file
into `cleanwin.external-rule-translation.v1` candidates. The translator is
read-only: it does not download catalogs, execute commands, or add rules to the
builtin catalog. Each candidate records upstream provenance, original pattern,
translated CleanWin review metadata, sensitive exclusions, dangerous path
flags, and `review_required=true` so external rules stay report-only until a
future owner review and promotion gate approves them.

`rule-pack-catalog` exposes the builtin cleanup rules as versioned read-only
packs for developer cache, package cache, browser cache, browser profile cache,
and app leftovers. Each rule includes a quality score with risk,
recoverability, owner evidence, official cleanup evidence, sensitive exclusion
scan results, test coverage, provenance, and review status. The report does not
import external packs, promote translated rules, or execute cleanup rules.

`rule-quality-dashboard` is a read-only governance report over the same builtin
rules. It summarizes quality buckets, risk and recoverability counts, evidence
gaps, per-pack quality health, and a review queue for lower-scored or higher-risk
rules without importing external catalogs or enabling execution. Rule metadata
also includes machine-readable `cache_layer` and `cache_layer_family` fields so
browser, developer, package, renderer, diagnostic, media, build, and dependency
cache surfaces can be reviewed separately by scripts and AI agents.

`browser-profile-inventory` reports browser cache layers and a structured
`cleanwin.locked-state.v1` contract for profile and cache-layer lock indicators,
including singleton locks, socket/cookie locks, and database WAL/SHM files. The
report does not scan processes, unlock files, close browsers, or delete cache
layers.

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
- Exposes resources such as `cleanwin://ai/tools`, `cleanwin://ai/host-policy`, `cleanwin://ai/readiness`, `cleanwin://ai/self-test`, `cleanwin://engineering/doctor`, `cleanwin://engineering/recovery-readiness`, `cleanwin://inventory/installed-apps`, `cleanwin://inventory/windows`, `cleanwin://plan/official-command-plan`, `cleanwin://inventory/debloat-privacy`, and `cleanwin://inventory/startup-services`.

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

The `dev-install` target creates `.venv`, installs `.[dev]`, and uses that environment for pytest, Ruff, mypy, compile, package, AI, and MCP checks. `make pytest` and `make pytest-governance-smoke` remove pytest caches, coverage files, and `__pycache__` after the test process finishes while preserving the pytest exit code; `.venv` is retained as the managed tool environment. `make ci-smoke` mirrors the non-packaging CI gate and finishes with the same test cleanup, while `make quality` adds install/package smoke checks and broader `make clean` cleanup. Equivalent manual commands:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check cleanwin.py cleanwincli tests
.venv/bin/python -m mypy cleanwin.py cleanwincli tests
.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests
.venv/bin/python cleanwin.py --json ai-readiness --validate
.venv/bin/python cleanwin.py --json doctor
```

New tests should prefer pytest function style with native `assert`, `tmp_path`, `monkeypatch`, `pytest.raises`, and `pytest.mark.parametrize`. Put reusable subprocess or JSON helpers in `tests/conftest.py` or focused MCP helpers instead of repeating `unittest.TestCase` setup methods. Reuse shared helpers for payload schemas, read-only payloads and reports, `safe_to_execute`, execution-disabled contracts, schema registry samples, command sequences, summary counts, dry-run result summaries, and boolean status fields such as `valid`, `ready`, `passed`, and `allowed`. Use the collection and text helpers for repeated expected membership, absence, and substring checks; keep direct `in`/`not in` assertions for isolated one-off checks. Use `assert_any_match`, `assert_all_match`, and `assert_none_match` for repeated `any(...)` / `all(...)` style checks over structured collections. Use `assert_field_values`, `assert_fields_present`, `assert_fields_not_none`, and `field_value` for repeated structured field checks; dot paths support nested dictionaries and numeric list indexes such as `rule_summary.0.rule_id`. Use `assert_exact_sequence`, `assert_exact_set`, `assert_unique_items`, `assert_non_empty`, and `assert_returncode` for repeated strict sequence, set, uniqueness, non-empty, and subprocess return-code checks. Use `assert_exact_count`, `assert_at_least`, `assert_one_of`, and `assert_text_contains_any` for repeated exact count, lower-bound, scalar membership, and any-fragment text checks. Use `assert_path_exists` and `assert_path_missing` for repeated filesystem existence checks. Exception-path tests should assert the error contract with `pytest.raises(..., match=...)`.

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

- `.github/workflows/ci.yml` runs Linux quality gates on Python 3.10 and 3.12 through Makefile targets, so pytest entrypoints clean test leftovers after completion.
- `.github/workflows/ci.yml` also runs package install smoke checks and the optional Docker sandbox gate.
- `.github/workflows/windows-smoke.yml` creates `.venv`, installs `.[dev]`, and runs pytest, Ruff, mypy, compile checks, identity drift smoke, and test-mode recycle smoke on `windows-latest`.
- `.github/workflows/windows-smoke.yml` uploads a `cleanwin-windows-json-evidence` artifact bundle with JSON reports for `windows-inventory`, `debloat-privacy-report`, `startup-service-inventory`, `system-health-report`, `promotion-gates`, promotion validation, `recovery-readiness`, `windows-smoke-matrix`, plus pytest and compile result summaries.
- `.github/workflows/windows-smoke.yml` has an `always()` cleanup step for build outputs, tool caches, pytest caches, coverage files, `htmlcov`, and `__pycache__`.
- `windows-smoke-matrix` tracks required Windows 10/11 evidence for read-only debloat/privacy, startup/service/task, and system-health diagnostics before any execution-model expansion.
- `system-health-report` remains diagnostic-only and uses scan/review commands such as DISM `ScanHealth`/`CheckHealth`, SFC scan, CHKDSK scan, Settings troubleshooters, and pending reboot registry queries without repair flags.
- `system-health-evidence` parser contracts convert captured DISM and pending reboot registry-query output into structured findings without running DISM, registry commands, or repair actions.
- `windows-evidence-bundle` emits a caller-managed JSONL evidence chain that links report refs, snapshot refs, simulated plan refs, rollback drill refs, promotion gate refs, recovery readiness refs, and Windows smoke CI refs. It does not write files, collect Windows artifacts, or run cleanup, registry, AppX, service, task, DISM, or PowerShell commands.

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
| `cleanwincli/rule_catalog.py` | Versioned cleanup rule catalog loader, rule pack report, and quality scoring |
| `cleanwincli/rules/cleanup_rules.v1.json` | Governed cleanup rule catalog data |
| `cleanwincli/recovery.py` | Recovery readiness gates and snapshot format declarations |
| `cleanwincli/installed_apps.py` | Read-only installed app inventory and leftover correlation |
| `cleanwincli/windows_inventory.py` | Read-only Windows inventory baseline for apps, AppX, features, update/cache, Defender, restore, Recycle Bin, Installer cache, and component store |
| `cleanwincli/debloat_privacy.py` | Read-only privacy/debloat report for Windows policy baselines, AppX review classification, and OEM app locations |
| `cleanwincli/execution_contracts.py` | Non-executable registry privacy, disable/revert, backup-delete, and permanent-delete denial contracts |
| `cleanwincli/startup_inventory.py` | Read-only startup, StartupApproved, Winlogon/Shell extension, service, driver service, and scheduled task inventory |
| `cleanwincli/promotion_gates.py` | Report-to-execution promotion contracts for registry, startup, service/task, official-command, Windows inventory, and browser-cache surfaces |
| `cleanwincli/official_commands.py` | Read-only official Windows cleanup command plans |
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
