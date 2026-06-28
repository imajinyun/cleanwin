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
`make pytest` and `make pytest-governance-smoke` run pytest through `.venv`,
then remove pytest caches, coverage files, and `__pycache__` while preserving
the test exit code. `.venv` is the managed tool environment and should not be
removed as routine test cleanup. Use `make clean` for build/cache cleanup after
packaging or broader local gates.

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
- Use the collection and text assertion helpers in `tests/conftest.py` for
  repeated expected membership, absence, and substring checks. Keep direct
  `in`/`not in` assertions for isolated one-off checks where a helper would add
  no diagnostic value.
- Use predicate assertion helpers such as `assert_any_match`,
  `assert_all_match`, and `assert_none_match` for repeated `any(...)` /
  `all(...)` style checks over structured collections.
- Use field assertion helpers such as `assert_field_values`,
  `assert_fields_present`, `assert_fields_not_none`, and `field_value` for
  repeated structured payload field checks. Dot paths may target nested
  dictionaries and numeric path segments may target list indexes, for example
  `rule_summary.0.rule_id`.
- Use exact assertion helpers such as `assert_exact_sequence`,
  `assert_exact_set`, `assert_unique_items`, `assert_non_empty`, and
  `assert_returncode` for repeated strict sequence, set, uniqueness,
  non-empty, and subprocess return-code checks.
- Use path assertion helpers such as `assert_path_exists` and
  `assert_path_missing` for repeated filesystem existence checks.
- Keep subprocess tests diagnostic: include stderr/stdout details when a helper
  fails.
- Keep Windows-only behavior behind explicit skip conditions or injectable test
  mode.
- Keep pytest governance budgets in `tests/test_pytest_governance.py` aligned
  when retiring legacy direct schema, read-only boolean, `safe_to_execute`, or
  execution-disabled flag assertions; do not add new direct assertions when a
  shared helper exists. Current direct assertion budgets for those categories,
  including direct status, summary, predicate, and migrated field assertions,
  should remain empty unless a migration plan explicitly reopens one. Keep the
  collection/text/predicate/field/exact helper adoption smoke updated when
  adding new migrated test files.

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

Use the local aiflow checkout when requested to queue, track, or validate work.
The root `aiflow.yaml` is the repository workflow profile. Keep it validation-only
unless the user explicitly asks for a broader workflow:

- `store_path` should point at `.aiflow/store.json`.
- `require_command_approval` should stay enabled so command execution appears
  in the latest approval-request evidence contract.
- `allow_commit`, `allow_push`, and automatic fix attempts should stay disabled.
- Register `cleanwin-mcp` as the local stdio MCP provider so governance reports
  include MCP provider catalog evidence.
- Keep generated reports, traces, local run evidence, and temporary state under
  `.aiflow/`.

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

go run ./cmd/aiflow doctor -root /Users/bytedance/Codes/sw/cleanwin

go run ./cmd/aiflow report -root /Users/bytedance/Codes/sw/cleanwin \
  -output /Users/bytedance/Codes/sw/cleanwin/.aiflow/governance.json \
  -validation-output /Users/bytedance/Codes/sw/cleanwin/.aiflow/contract-validation.json \
  -fail-on-invalid

go run ./cmd/aiflow advisory -root /Users/bytedance/Codes/sw/cleanwin \
  -fail-on-warning-id contract-validation
```

Keep `aiflow.yaml` in the repository root and commit workflow changes with the
code or governance change they support.
The `.aiflow/` directory is local generated governance state only; do not stage
or commit it.

## Documentation Updates

Update README or `docs/doc` when changes affect:

- User-visible commands.
- Safety gates or execution requirements.
- Cleanup categories or report inventory scope.
- AI/MCP tool behavior.
- Development or CI workflow.

Keep root README concise and link to deeper documentation instead of duplicating
the full command reference.
