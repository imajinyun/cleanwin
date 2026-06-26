from __future__ import annotations

import ast
from collections.abc import Callable, Collection, Iterable, Sequence
from pathlib import Path
from typing import Any, NamedTuple

AssertContainsAll = Callable[[Collection[Any], Sequence[Any]], None]
AssertTextContainsAll = Callable[[str, Sequence[str]], None]
AssertExactSequence = Callable[[Sequence[Any], Sequence[Any]], Sequence[Any]]
AssertAtLeast = Callable[[int, int], int]
AssertNoneMatch = Callable[[Sequence[str], Callable[[str], bool]], Sequence[str]]

HELPER_MODULES = {"conftest.py", "test_pytest_governance.py"}
AD_HOC_FILESYSTEM_METHODS = {"mkdir", "write_text", "write_bytes"}
CLI_SUBPROCESS_ALLOWLIST = {"conftest.py", "test_mcp_server.py"}
PROVIDER_SCHEMA_ALLOWLIST = {
    ("test_ai_contracts.py", "test_cli_ai_tools_and_host_policy_are_valid"),
    ("test_ai_readiness.py", "test_cli_exposes_readiness_self_test_and_runbook"),
}
DIRECT_SCHEMA_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
READONLY_BOOLEAN_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
READONLY_BOOLEAN_KEYS = {
    "destructive": False,
    "dry_run": True,
    "executes_system_commands": False,
}
SAFE_TO_EXECUTE_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
EXECUTION_DISABLED_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
STATUS_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
SUMMARY_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
PREDICATE_ASSERTION_ALLOWLIST: dict[tuple[str, str], int] = {}
COLLECTION_ASSERTION_HELPERS = {
    "assert_contains_all",
    "assert_contains_none",
    "assert_text_contains_all",
    "assert_any_text_contains",
    "assert_any_match",
    "assert_all_match",
    "assert_none_match",
}
FIELD_ASSERTION_HELPERS = {
    "field_value",
    "assert_field_values",
    "assert_fields_present",
    "assert_fields_not_none",
}
EXACT_ASSERTION_HELPERS = {
    "assert_exact_sequence",
    "assert_exact_set",
    "assert_unique_items",
    "assert_non_empty",
    "assert_returncode",
}
SCALAR_ASSERTION_HELPERS = {
    "assert_at_least",
    "assert_exact_count",
    "assert_one_of",
    "assert_text_contains_any",
}
PATH_ASSERTION_HELPERS = {
    "assert_path_exists",
    "assert_path_missing",
}
GOVERNANCE_HELPER_ADOPTION_FILES = {
    "test_pytest_governance.py",
}
MIN_FIELD_HELPER_ADOPTION_FILES = 18
MIN_FIELD_HELPER_CALLS = 102
MIN_NONNULL_FIELD_HELPER_ADOPTION_FILES = 1
MIN_EXACT_HELPER_ADOPTION_FILES = 7
MIN_SCALAR_HELPER_ADOPTION_FILES = 2
MIN_PATH_HELPER_ADOPTION_FILES = 5
COLLECTION_HELPER_ADOPTION_FILES = {
    "test_ai_readiness.py",
    "test_ai_contracts.py",
    "test_mcp_server.py",
    "test_cli.py",
    "test_execution_contracts.py",
    "test_official_commands.py",
    "test_presets.py",
    "test_promotion_gates.py",
    "test_system_health.py",
    "test_windows_smoke.py",
    "test_file_reports.py",
    "test_browser_inventory.py",
    "test_installed_apps.py",
    "test_startup_inventory.py",
    "test_debloat_privacy.py",
    "test_recovery.py",
    "test_rule_catalog.py",
    "test_scan_governance.py",
}
FIELD_HELPER_ADOPTION_FILES = {
    "test_ai_contracts.py",
    "test_ai_readiness.py",
    "test_browser_inventory.py",
    "test_cli.py",
    "test_debloat_privacy.py",
    "test_execution_contracts.py",
    "test_file_reports.py",
    "test_identity.py",
    "test_installed_apps.py",
    "test_mcp_server.py",
    "test_official_commands.py",
    "test_presets.py",
    "test_promotion_gates.py",
    "test_recovery.py",
    "test_rule_catalog.py",
    "test_safety.py",
    "test_scan_governance.py",
    "test_startup_inventory.py",
    "test_windows_smoke.py",
}
NONNULL_FIELD_HELPER_ADOPTION_FILES = {
    "test_windows_integration.py",
}
EXACT_HELPER_ADOPTION_FILES = {
    "test_ai_contracts.py",
    "test_ai_readiness.py",
    "test_cli.py",
    "test_debloat_privacy.py",
    "test_file_reports.py",
    "test_rule_catalog.py",
    "test_system_health.py",
}
SCALAR_HELPER_ADOPTION_FILES = {
    "test_ai_readiness.py",
    "test_debloat_privacy.py",
    "test_rule_catalog.py",
}
PATH_HELPER_ADOPTION_FILES = {
    "test_ai_contracts.py",
    "test_cli.py",
    "test_delete_ops.py",
    "test_identity.py",
    "test_windows_integration.py",
}
STATUS_KEYS = {"valid", "ready", "passed", "allowed"}
EXECUTION_DISABLED_KEYS = {
    "ai_auto_call_allowed",
    "auto_executable",
    "backup_delete_execution_enabled",
    "cache_execution_enabled",
    "disable_revert_execution_enabled",
    "execution_enabled",
    "executes_by_report",
    "preset_execution_enabled",
    "system_execution_enabled",
    "system_repair_execution_enabled",
}


class ParsedTestModule(NamedTuple):
    path: Path
    tree: ast.AST


def iter_test_modules(repo_root: Path) -> Iterable[ParsedTestModule]:
    for path in sorted((repo_root / "tests").glob("test_*.py")):
        yield ParsedTestModule(path=path, tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))


def test_tests_remain_pytest_native(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                if any(alias.name == "unittest" for alias in node.names):
                    violations.append(f"{path.name}: imports unittest")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "unittest":
                    violations.append(f"{path.name}: imports from unittest")
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "TestCase":
                        violations.append(f"{path.name}:{node.name}: subclasses TestCase")
                    if (
                        isinstance(base, ast.Attribute)
                        and base.attr == "TestCase"
                        and isinstance(base.value, ast.Name)
                        and base.value.id == "unittest"
                    ):
                        violations.append(f"{path.name}:{node.name}: subclasses unittest.TestCase")
            elif isinstance(node, ast.Attribute):
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                    and node.attr.startswith("assert")
                ):
                    violations.append(f"{path.name}: uses self.{node.attr}")

    assert_exact_sequence(violations, [])


def test_python_test_files_stay_pytest_discoverable(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for path in sorted((repo_root / "tests").rglob("*.py")):
        relative = path.relative_to(repo_root).as_posix()
        if path.name in {"__init__.py", "conftest.py"}:
            continue
        if path.parent.name == "__pycache__":
            continue
        if not path.name.startswith("test_"):
            violations.append(f"{relative}: test files must use pytest-discoverable test_*.py naming")

    assert_exact_sequence(violations, [])


def test_pyproject_defines_pytest_dev_contract(
    repo_root: Path,
    assert_none_match: AssertNoneMatch,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert_text_contains_all(
        pyproject,
        [
            "[project.optional-dependencies]",
            "dev = [",
            '"pytest>=8.3"',
            '"ruff>=0.8"',
            '"mypy>=1.13"',
            "[tool.pytest.ini_options]",
            'minversion = "8.0"',
            'testpaths = ["tests"]',
            'addopts = "--strict-config --strict-markers"',
        ],
    )
    assert_none_match([pyproject], lambda text: "unittest" in text)


def test_makefile_keeps_pytest_entrypoints_in_repo_venv(
    repo_root: Path,
    assert_none_match: AssertNoneMatch,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")

    assert_text_contains_all(
        makefile,
        [
            "DEV_PYTHON ?= $(VENV_PYTHON)",
            "test: dev-install",
            "pytest: dev-install",
            "lint: dev-install",
            "type: dev-install",
            "compile: dev-install",
            "pytest-governance-smoke: dev-install",
            "$(DEV_PYTHON) -m pytest -q",
            "$(DEV_PYTHON) -m ruff check cleanwin.py cleanwincli tests",
            "$(DEV_PYTHON) -m mypy cleanwin.py cleanwincli tests",
            "$(DEV_PYTHON) -m compileall -q cleanwin.py cleanwincli tests",
            "ci-smoke: lint pytest type compile docs-smoke ai-smoke mcp-smoke version-smoke pytest-governance-smoke",
        ],
    )
    command_lines = [line for line in makefile.splitlines() if line.startswith("\t")]
    assert_none_match(
        command_lines,
        lambda line: line.strip().startswith(
            ("$(DEV_PYTHON) -m unittest", "$(PYTHON) -m unittest", "python -m unittest", "unittest discover")
        ),
    )


def test_linux_ci_and_docker_use_pytest_governance_entrypoints(
    repo_root: Path,
    assert_none_match: AssertNoneMatch,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (repo_root / "Dockerfile.test").read_text(encoding="utf-8")

    assert_text_contains_all(
        workflow,
        [
            "python-version: [\"3.10\", \"3.12\"]",
            "run: make lint",
            "run: make pytest",
            "run: make type",
            "run: make compile",
            "run: make pytest-governance-smoke",
            "run: make docker-quality",
        ],
    )
    assert_none_match([workflow], lambda text: "python -m pytest" in text or "unittest" in text)
    assert_text_contains_all(
        dockerfile,
        [
            ".venv/bin/python -m ruff check cleanwin.py cleanwincli tests",
            ".venv/bin/python -m pytest -q",
            ".venv/bin/python -m mypy cleanwin.py cleanwincli tests",
            ".venv/bin/python -m compileall -q cleanwin.py cleanwincli tests",
            ".venv/bin/python -m pytest tests/test_pytest_governance.py",
        ],
    )
    assert_none_match([dockerfile], lambda text: "unittest" in text)


def test_windows_smoke_uses_repo_venv_pytest_entrypoints(
    repo_root: Path,
    assert_none_match: AssertNoneMatch,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    workflow = (repo_root / ".github" / "workflows" / "windows-smoke.yml").read_text(encoding="utf-8")

    assert_text_contains_all(
        workflow,
        [
            "runs-on: windows-latest",
            "python -m venv .venv",
            r".\.venv\Scripts\python.exe -m pip install -e .[dev]",
            r".\.venv\Scripts\python.exe -m pytest -q",
            r".\.venv\Scripts\python.exe -m ruff check cleanwin.py cleanwincli tests",
            r".\.venv\Scripts\python.exe -m mypy cleanwin.py cleanwincli tests",
            r".\.venv\Scripts\python.exe -m compileall -q cleanwin.py cleanwincli tests",
        ],
    )
    assert_none_match([workflow], lambda text: "python -m pytest" in text or "unittest" in text)


def test_tests_use_shared_filesystem_fixtures(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        for node in ast.walk(module.tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in AD_HOC_FILESYSTEM_METHODS
            ):
                violations.append(f"{path.name}: uses {node.func.attr} instead of shared fixture")

    assert_exact_sequence(violations, [])


def test_cli_subprocess_calls_stay_in_shared_helpers(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in CLI_SUBPROCESS_ALLOWLIST:
            continue
        for node in ast.walk(module.tree):
            if _is_subprocess_call(node):
                violations.append(f"{path.name}: use shared CLI/MCP subprocess helper")

    assert_exact_sequence(violations, [])


def test_workflows_use_makefile_venv_pytest_contract(
    repo_root: Path,
    assert_none_match: AssertNoneMatch,
    assert_text_contains_all: AssertTextContainsAll,
) -> None:
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")
    workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (repo_root / "Dockerfile.test").read_text(encoding="utf-8")

    assert_text_contains_all(
        makefile,
        ["pytest: dev-install", "$(DEV_PYTHON) -m pytest -q", "$(DEV_PYTHON) -m ruff check", "$(DEV_PYTHON) -m mypy"],
    )
    assert_text_contains_all(workflow, ["make pytest"])
    assert_none_match([workflow], lambda text: "python -m pytest" in text or "unittest" in text)
    assert_none_match([dockerfile], lambda text: "unittest discover" in text)
    assert_text_contains_all(
        dockerfile,
        [".venv/bin/python -m pytest -q", ".venv/bin/python -m ruff check", ".venv/bin/python -m mypy"],
    )


def test_pytest_raises_assertions_match_messages(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        for node in ast.walk(module.tree):
            if _is_pytest_raises_call(node) and not _has_keyword(node, "match"):
                violations.append(f"{path.name}: pytest.raises must assert match=")

    assert_exact_sequence(violations, [])


def test_tests_use_shared_provider_schema_helpers(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_schema_subscript(node) or not _is_cleanwin_json_call(_subscript_root(node)):
                continue
            test_name = _enclosing_test_name(node, parents)
            if test_name and (path.name, test_name) in PROVIDER_SCHEMA_ALLOWLIST:
                continue
            violations.append(f"{path.name}:{test_name or '<module>'}: use shared provider schema helper")

    assert_exact_sequence(violations, [])


def test_tests_use_shared_schema_registry_helpers(repo_root: Path, assert_exact_sequence: AssertExactSequence) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        assignments = _assigned_cleanwin_json_commands(module.tree)
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if _is_schema_registry_call(node):
                test_name = _enclosing_test_name(node, parents)
                violations.append(f"{path.name}:{test_name or '<module>'}: use shared schema registry helper")
            elif _is_registry_sample_subscript(node, assignments):
                test_name = _enclosing_test_name(node, parents)
                violations.append(f"{path.name}:{test_name or '<module>'}: use shared schema sample helper")

    assert_exact_sequence(violations, [])


def test_direct_schema_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_schema_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(DIRECT_SCHEMA_ASSERTION_ALLOWLIST.items()))


def test_direct_readonly_boolean_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_readonly_boolean_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(READONLY_BOOLEAN_ASSERTION_ALLOWLIST.items()))


def test_direct_safe_to_execute_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_safe_to_execute_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(SAFE_TO_EXECUTE_ASSERTION_ALLOWLIST.items()))


def test_direct_execution_disabled_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_execution_disabled_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(EXECUTION_DISABLED_ASSERTION_ALLOWLIST.items()))


def test_direct_status_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_status_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(STATUS_ASSERTION_ALLOWLIST.items()))


def test_direct_summary_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_summary_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(SUMMARY_ASSERTION_ALLOWLIST.items()))


def test_direct_predicate_assertions_stay_in_migration_budget(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    observed: dict[tuple[str, str], int] = {}
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(module.tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(module.tree):
            if not _is_direct_predicate_assertion(node):
                continue
            key = (path.name, _enclosing_test_name(node, parents) or "<module>")
            observed[key] = observed.get(key, 0) + 1

    assert_exact_sequence(list(observed.items()), list(PREDICATE_ASSERTION_ALLOWLIST.items()))


def test_collection_and_text_assertion_helpers_are_adopted(
    repo_root: Path,
    assert_contains_all: AssertContainsAll,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    conftest_tree = ast.parse((repo_root / "tests" / "conftest.py").read_text(encoding="utf-8"))
    helper_defs = {node.name for node in ast.walk(conftest_tree) if isinstance(node, ast.FunctionDef)}
    assert_contains_all(helper_defs, sorted(COLLECTION_ASSERTION_HELPERS))

    adopted: dict[str, set[str]] = {filename: set() for filename in COLLECTION_HELPER_ADOPTION_FILES}
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in COLLECTION_ASSERTION_HELPERS:
                    adopted[module.path.name].add(node.func.id)

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])


def test_pytest_governance_uses_shared_assertion_helpers(
    repo_root: Path,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    governance_helpers = (
        COLLECTION_ASSERTION_HELPERS
        | FIELD_ASSERTION_HELPERS
        | EXACT_ASSERTION_HELPERS
        | SCALAR_ASSERTION_HELPERS
        | PATH_ASSERTION_HELPERS
    )
    adopted: dict[str, set[str]] = {filename: set() for filename in GOVERNANCE_HELPER_ADOPTION_FILES}
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in governance_helpers:
                    adopted[module.path.name].add(node.func.id)

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])


def test_field_assertion_helpers_are_adopted(
    repo_root: Path,
    assert_at_least: AssertAtLeast,
    assert_contains_all: AssertContainsAll,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    conftest_tree = ast.parse((repo_root / "tests" / "conftest.py").read_text(encoding="utf-8"))
    helper_defs = {node.name for node in ast.walk(conftest_tree) if isinstance(node, ast.FunctionDef)}
    assert_contains_all(helper_defs, sorted(FIELD_ASSERTION_HELPERS))
    assert_at_least(len(FIELD_HELPER_ADOPTION_FILES), MIN_FIELD_HELPER_ADOPTION_FILES)

    adopted: dict[str, set[str]] = {filename: set() for filename in FIELD_HELPER_ADOPTION_FILES}
    helper_call_count = 0
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FIELD_ASSERTION_HELPERS:
                    adopted[module.path.name].add(node.func.id)
                    helper_call_count += 1

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])
    assert_at_least(helper_call_count, MIN_FIELD_HELPER_CALLS)


def test_non_null_field_assertion_helpers_are_adopted(
    repo_root: Path,
    assert_at_least: AssertAtLeast,
    assert_contains_all: AssertContainsAll,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    conftest_tree = ast.parse((repo_root / "tests" / "conftest.py").read_text(encoding="utf-8"))
    helper_defs = {node.name for node in ast.walk(conftest_tree) if isinstance(node, ast.FunctionDef)}
    assert_contains_all(helper_defs, ["assert_fields_not_none"])
    assert_at_least(len(NONNULL_FIELD_HELPER_ADOPTION_FILES), MIN_NONNULL_FIELD_HELPER_ADOPTION_FILES)

    adopted: dict[str, set[str]] = {filename: set() for filename in NONNULL_FIELD_HELPER_ADOPTION_FILES}
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "assert_fields_not_none":
                    adopted[module.path.name].add(node.func.id)

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])


def test_exact_assertion_helpers_are_adopted(
    repo_root: Path,
    assert_at_least: AssertAtLeast,
    assert_contains_all: AssertContainsAll,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    conftest_tree = ast.parse((repo_root / "tests" / "conftest.py").read_text(encoding="utf-8"))
    helper_defs = {node.name for node in ast.walk(conftest_tree) if isinstance(node, ast.FunctionDef)}
    assert_contains_all(helper_defs, sorted(EXACT_ASSERTION_HELPERS))
    assert_at_least(len(EXACT_HELPER_ADOPTION_FILES), MIN_EXACT_HELPER_ADOPTION_FILES)

    adopted: dict[str, set[str]] = {filename: set() for filename in EXACT_HELPER_ADOPTION_FILES}
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in EXACT_ASSERTION_HELPERS:
                    adopted[module.path.name].add(node.func.id)

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])


def test_scalar_assertion_helpers_are_adopted(
    repo_root: Path,
    assert_at_least: AssertAtLeast,
    assert_contains_all: AssertContainsAll,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    conftest_tree = ast.parse((repo_root / "tests" / "conftest.py").read_text(encoding="utf-8"))
    helper_defs = {node.name for node in ast.walk(conftest_tree) if isinstance(node, ast.FunctionDef)}
    assert_contains_all(helper_defs, sorted(SCALAR_ASSERTION_HELPERS))
    assert_at_least(len(SCALAR_HELPER_ADOPTION_FILES), MIN_SCALAR_HELPER_ADOPTION_FILES)

    adopted: dict[str, set[str]] = {filename: set() for filename in SCALAR_HELPER_ADOPTION_FILES}
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in SCALAR_ASSERTION_HELPERS:
                    adopted[module.path.name].add(node.func.id)

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])


def test_path_assertion_helpers_are_adopted(
    repo_root: Path,
    assert_at_least: AssertAtLeast,
    assert_contains_all: AssertContainsAll,
    assert_exact_sequence: AssertExactSequence,
) -> None:
    conftest_tree = ast.parse((repo_root / "tests" / "conftest.py").read_text(encoding="utf-8"))
    helper_defs = {node.name for node in ast.walk(conftest_tree) if isinstance(node, ast.FunctionDef)}
    assert_contains_all(helper_defs, sorted(PATH_ASSERTION_HELPERS))
    assert_at_least(len(PATH_HELPER_ADOPTION_FILES), MIN_PATH_HELPER_ADOPTION_FILES)

    adopted: dict[str, set[str]] = {filename: set() for filename in PATH_HELPER_ADOPTION_FILES}
    for module in iter_test_modules(repo_root):
        if module.path.name not in adopted:
            continue
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in PATH_ASSERTION_HELPERS:
                    adopted[module.path.name].add(node.func.id)

    missing = [filename for filename, helpers in adopted.items() if not helpers]
    assert_exact_sequence(missing, [])


def _assigned_cleanwin_json_commands(tree: ast.AST) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if not _is_cleanwin_json_call(node.value):
            continue
        first_arg = node.value.args[0] if node.value.args else None
        if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = first_arg.value
    return assignments


def _is_subprocess_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"run", "Popen"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    )


def _is_pytest_raises_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "raises"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pytest"
    )


def _has_keyword(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Call) and any(keyword.arg == name for keyword in node.keywords)


def _is_schema_registry_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not _is_cleanwin_json_call(node):
        return False
    first_arg = node.args[0] if node.args else None
    return isinstance(first_arg, ast.Constant) and first_arg.value == "schema-registry"


def _is_registry_sample_subscript(node: ast.AST, assignments: dict[str, str]) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    value = node.value
    if not isinstance(value, ast.Subscript) or _slice_value(value.slice) != "samples":
        return False
    root = _subscript_root(value)
    return isinstance(root, ast.Name) and assignments.get(root.id) == "schema-registry"


def _is_cleanwin_json_call(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cleanwin_json"
    )


def _is_schema_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and _slice_value(node.slice) == "schema"


def _is_direct_schema_assertion(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
        return False
    if not any(isinstance(operator, ast.Eq) for operator in node.test.ops):
        return False
    return _is_schema_subscript(node.test.left) or any(
        _is_schema_subscript(comparator) for comparator in node.test.comparators
    )


def _is_direct_readonly_boolean_assertion(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assert):
        return False
    test = node.test
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _readonly_boolean_subscript_expected(test.operand) is False
    if not isinstance(test, ast.Compare):
        return False
    left_expected = _readonly_boolean_subscript_expected(test.left)
    for operator, comparator in zip(test.ops, test.comparators, strict=False):
        if not isinstance(operator, ast.Is):
            continue
        if left_expected is not None and _constant_bool(comparator) is left_expected:
            return True
        right_expected = _readonly_boolean_subscript_expected(comparator)
        if right_expected is not None and _constant_bool(test.left) is right_expected:
            return True
    return False


def _is_direct_safe_to_execute_assertion(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assert):
        return False
    return _contains_safe_to_execute_disabled_check(node.test)


def _is_direct_execution_disabled_assertion(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assert):
        return False
    return _contains_execution_disabled_check(node.test)


def _is_direct_status_assertion(node: ast.AST) -> bool:
    return isinstance(node, ast.Assert) and _contains_status_subscript(node.test)


def _is_direct_summary_assertion(node: ast.AST) -> bool:
    return isinstance(node, ast.Assert) and _contains_summary_subscript(node.test)


def _is_direct_predicate_assertion(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assert):
        return False
    return _contains_any_all_call(node.test)


def _contains_any_all_call(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"any", "all"}:
        return True
    return any(_contains_any_all_call(child) for child in ast.iter_child_nodes(node))


def _contains_safe_to_execute_disabled_check(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_safe_to_execute_subscript(node.operand)
    if isinstance(node, ast.Compare):
        left_is_safe_to_execute = _is_safe_to_execute_subscript(node.left)
        for operator, comparator in zip(node.ops, node.comparators, strict=False):
            if isinstance(operator, ast.Is):
                if left_is_safe_to_execute and _constant_bool(comparator) is False:
                    return True
                if _is_safe_to_execute_subscript(comparator) and _constant_bool(node.left) is False:
                    return True
            if isinstance(operator, ast.Eq):
                if left_is_safe_to_execute and _constant_bool(comparator) is False:
                    return True
                if _is_safe_to_execute_subscript(comparator) and _constant_bool(node.left) is False:
                    return True
    if isinstance(node, ast.Call):
        return any(_contains_safe_to_execute_disabled_check(child) for child in ast.iter_child_nodes(node))
    if isinstance(node, (ast.BoolOp, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
        return any(_contains_safe_to_execute_disabled_check(child) for child in ast.iter_child_nodes(node))
    return False


def _contains_execution_disabled_check(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_execution_disabled_subscript(node.operand)
    if isinstance(node, ast.Compare):
        left_is_disabled_flag = _is_execution_disabled_subscript(node.left)
        for operator, comparator in zip(node.ops, node.comparators, strict=False):
            if isinstance(operator, ast.Is):
                if left_is_disabled_flag and _constant_bool(comparator) is False:
                    return True
                if _is_execution_disabled_subscript(comparator) and _constant_bool(node.left) is False:
                    return True
            if isinstance(operator, ast.Eq):
                if left_is_disabled_flag and _constant_bool(comparator) is False:
                    return True
                if _is_execution_disabled_subscript(comparator) and _constant_bool(node.left) is False:
                    return True
    if isinstance(node, ast.Call):
        return any(_contains_execution_disabled_check(child) for child in ast.iter_child_nodes(node))
    if isinstance(node, (ast.BoolOp, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
        return any(_contains_execution_disabled_check(child) for child in ast.iter_child_nodes(node))
    return False


def _is_safe_to_execute_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and _slice_value(node.slice) == "safe_to_execute"


def _is_execution_disabled_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and (_slice_value(node.slice) in EXECUTION_DISABLED_KEYS)


def _contains_status_subscript(node: ast.AST) -> bool:
    if _is_status_subscript(node):
        return True
    return any(_contains_status_subscript(child) for child in ast.iter_child_nodes(node))


def _is_status_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and (_slice_value(node.slice) in STATUS_KEYS)


def _contains_summary_subscript(node: ast.AST) -> bool:
    if _is_summary_subscript(node):
        return True
    return any(_contains_summary_subscript(child) for child in ast.iter_child_nodes(node))


def _is_summary_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and (_slice_value(node.slice) == "summary")


def _readonly_boolean_subscript_expected(node: ast.AST) -> bool | None:
    if not isinstance(node, ast.Subscript):
        return None
    key = _slice_value(node.slice)
    if key not in READONLY_BOOLEAN_KEYS:
        return None
    return READONLY_BOOLEAN_KEYS[key]


def _constant_bool(node: ast.AST) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _slice_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _subscript_root(node: ast.AST) -> ast.AST | None:
    if not isinstance(node, ast.Subscript):
        return None
    value = node.value
    while isinstance(value, ast.Subscript):
        value = value.value
    return value


def _enclosing_test_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    current: ast.AST | None = node
    while current in parents:
        current = parents[current]
        if isinstance(current, ast.FunctionDef) and current.name.startswith("test_"):
            return current.name
    return None
