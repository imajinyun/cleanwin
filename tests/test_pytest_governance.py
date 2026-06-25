from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

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
EXECUTION_DISABLED_ASSERTION_ALLOWLIST = {
    ("test_ai_contracts.py", "test_workflow_context_schema_samples_are_registered"): 1,
    ("test_ai_readiness.py", "test_workflow_trace_documents_required_artifact_chain"): 1,
    ("test_presets.py", "test_preset_catalog_is_read_only_and_non_executable"): 3,
    ("test_promotion_gates.py", "test_promotion_gates_are_non_destructive_and_keep_system_execution_disabled"): 1,
    ("test_promotion_gates.py", "test_promotion_gates_cover_high_risk_report_surfaces"): 1,
    ("test_system_health.py", "test_system_health_recommendations_use_official_tools_without_execution"): 1,
}
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


def test_tests_remain_pytest_native(repo_root: Path) -> None:
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

    assert violations == []


def test_tests_use_shared_filesystem_fixtures(repo_root: Path) -> None:
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

    assert violations == []


def test_cli_subprocess_calls_stay_in_shared_helpers(repo_root: Path) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in CLI_SUBPROCESS_ALLOWLIST:
            continue
        for node in ast.walk(module.tree):
            if _is_subprocess_call(node):
                violations.append(f"{path.name}: use shared CLI/MCP subprocess helper")

    assert violations == []


def test_workflows_use_makefile_venv_pytest_contract(repo_root: Path) -> None:
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")
    workflow = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (repo_root / "Dockerfile.test").read_text(encoding="utf-8")

    assert "pytest: dev-install" in makefile
    assert "$(DEV_PYTHON) -m pytest -q" in makefile
    assert "$(DEV_PYTHON) -m ruff check" in makefile
    assert "$(DEV_PYTHON) -m mypy" in makefile
    assert "make pytest" in workflow
    assert "python -m pytest" not in workflow
    assert "unittest" not in workflow
    assert ".venv/bin/python -m pytest -q" in dockerfile
    assert ".venv/bin/python -m ruff check" in dockerfile
    assert ".venv/bin/python -m mypy" in dockerfile
    assert "unittest discover" not in dockerfile


def test_pytest_raises_assertions_match_messages(repo_root: Path) -> None:
    violations: list[str] = []
    for module in iter_test_modules(repo_root):
        path = module.path
        if path.name in HELPER_MODULES:
            continue
        for node in ast.walk(module.tree):
            if _is_pytest_raises_call(node) and not _has_keyword(node, "match"):
                violations.append(f"{path.name}: pytest.raises must assert match=")

    assert violations == []


def test_tests_use_shared_provider_schema_helpers(repo_root: Path) -> None:
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

    assert violations == []


def test_tests_use_shared_schema_registry_helpers(repo_root: Path) -> None:
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

    assert violations == []


def test_direct_schema_assertions_stay_in_migration_budget(repo_root: Path) -> None:
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

    assert observed == DIRECT_SCHEMA_ASSERTION_ALLOWLIST


def test_direct_readonly_boolean_assertions_stay_in_migration_budget(repo_root: Path) -> None:
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

    assert observed == READONLY_BOOLEAN_ASSERTION_ALLOWLIST


def test_direct_safe_to_execute_assertions_stay_in_migration_budget(repo_root: Path) -> None:
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

    assert observed == SAFE_TO_EXECUTE_ASSERTION_ALLOWLIST


def test_direct_execution_disabled_assertions_stay_in_migration_budget(repo_root: Path) -> None:
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

    assert observed == EXECUTION_DISABLED_ASSERTION_ALLOWLIST


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
