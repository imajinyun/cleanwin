# AGENTS.md

Repository workflow and guardrails for AI coding agents and maintainers working
on cleanwin.

## Project Shape

cleanwin is an AI-friendly Windows cleanup CLI. The default posture is
read-only inventory, dry-run planning, validation, and review before any cleanup
execution path.

Core principles:

- Preserve dry-run-first behavior.
- Keep destructive behavior gated by plan validation, explicit execution flags,
  operation logs, recycle mode, confirmation phrase, and dry-run confirmation
  token.
- Prefer read-only inventory/report additions before execution features.
- Keep AI/MCP contracts structured and machine-readable.
- Avoid runtime dependencies unless there is a clear project-level reason.

## Workspace Rules

- Do not revert user changes unless explicitly asked.
- Keep edits scoped to the requested files and behavior.
- Use `rg` or `rg --files` for repository search.
- Use `apply_patch` for manual file edits.
- Do not write generated caches, `.venv`, `.harness`, build outputs, or local
  tool state into commits.
- Do not add destructive cleanup execution paths without corresponding safety
  gates, tests, and documentation.

## Development Environment

All Python tooling must run through the repository virtual environment. Use the
Makefile targets because they create `.venv`, install the project in editable
mode, and install `ruff`, `mypy`, and `pytest` from the `dev` extra.

Common commands:

```bash
make lint
make pytest
make type
make compile
make ci-smoke
```

Full local gate:

```bash
make quality
```

Docker sandbox gate, when Docker is installed and image pulls are available:

```bash
make docker-quality
```

Do not run project tests against the system Python when changing code or tests.

## Test Workflow

Use pytest-native patterns for new or updated tests:

- Prefer fixtures over repeated setup.
- Prefer `pytest.mark.parametrize` for repeated rule/category assertions.
- Prefer plain `assert` and `pytest.raises`.
- Reuse shared helpers from `tests/conftest.py` for CLI JSON calls, schema
  assertions, read-only report assertions, execution-disabled contracts, command
  sequences, schema registry samples, summary count assertions, dry-run result
  summaries, and boolean status fields such as `valid`, `ready`, `passed`, and
  `allowed`.
- Keep subprocess tests diagnostic: include stderr/stdout details when a helper
  fails.
- Keep Windows-only behavior behind explicit skip conditions or injectable test
  mode.
- Keep pytest governance budgets in `tests/test_pytest_governance.py` aligned
  when retiring legacy direct schema, read-only boolean, `safe_to_execute`, or
  execution-disabled flag assertions; do not add new direct assertions when a
  shared helper exists. Current direct assertion budgets for those categories,
  including direct status and summary assertions, should remain empty unless a
  migration plan explicitly reopens one.

Minimum verification for ordinary code or test changes:

```bash
make lint
make pytest
make type
make compile
```

For release-facing or packaging changes, run:

```bash
make quality
```

For CI or workflow changes, run:

```bash
make ci-smoke
make pytest-governance-smoke
```

## AI and MCP Contract Changes

When changing AI tool schemas, MCP resources, host policy, readiness reports, or
execution contracts:

- Update schema/version tests with the behavior change.
- Keep tool arguments structured; do not add raw command escape hatches.
- Keep host-policy denial paths explicit for destructive tools.
- Validate both CLI JSON output and MCP resource/tool exposure where relevant.
- Update documentation links or examples when command names or contracts change.

## Safety Expectations

Cleanup execution must remain conservative:

- Default commands must not delete files.
- New inventory/report features should be read-only unless explicitly promoted
  later.
- New cleanup candidates need rule metadata, rationale, ownership, identity, and
  review coverage.
- Real deletion must continue through the single safe deletion exit.
- Non-Windows destructive execution should fail closed outside test mode.

## aiflow Governance

This repository is onboarded to aiflow through `aiflow.yaml`. Use the local
aiflow checkout when requested to queue or track work:

```bash
go run ./cmd/aiflow submit -root /Users/bytedance/Codes/sw/cleanwin \
  -kind test \
  -id TASK-ID \
  -title "short task title" \
  -description "concrete task description" \
  -priority 80

go run ./cmd/aiflow status -root /Users/bytedance/Codes/sw/cleanwin

go run ./cmd/aiflow complete -root /Users/bytedance/Codes/sw/cleanwin \
  -id TASK-ID \
  -reason "what landed and what passed"

go run ./cmd/aiflow report -root /Users/bytedance/Codes/sw/cleanwin \
  -output /Users/bytedance/Codes/sw/cleanwin/.aiflow/governance.json
```

The `.aiflow` directory is local governance state and should stay untracked.

## Documentation Updates

Update README or `docs/doc` when changes affect:

- User-visible commands.
- Safety gates or execution requirements.
- Cleanup categories or report inventory scope.
- AI/MCP tool behavior.
- Development or CI workflow.

Keep root README concise and link to deeper documentation instead of duplicating
the full command reference.
