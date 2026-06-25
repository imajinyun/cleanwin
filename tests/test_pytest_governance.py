from __future__ import annotations

import ast
from pathlib import Path

HELPER_MODULES = {"conftest.py", "test_pytest_governance.py"}
AD_HOC_FILESYSTEM_METHODS = {"mkdir", "write_text", "write_bytes"}
PROVIDER_SCHEMA_ALLOWLIST = {
    ("test_ai_contracts.py", "test_cli_ai_tools_and_host_policy_are_valid"),
    ("test_ai_readiness.py", "test_cli_exposes_readiness_self_test_and_runbook"),
}


def test_tests_remain_pytest_native(repo_root: Path) -> None:
    violations: list[str] = []
    for path in sorted((repo_root / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
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
    for path in sorted((repo_root / "tests").glob("test_*.py")):
        if path.name in HELPER_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in AD_HOC_FILESYSTEM_METHODS
            ):
                violations.append(f"{path.name}: uses {node.func.attr} instead of shared fixture")

    assert violations == []


def test_tests_use_shared_provider_schema_helpers(repo_root: Path) -> None:
    violations: list[str] = []
    for path in sorted((repo_root / "tests").glob("test_*.py")):
        if path.name in HELPER_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(tree):
            if not _is_schema_subscript(node) or not _is_cleanwin_json_call(_subscript_root(node)):
                continue
            test_name = _enclosing_test_name(node, parents)
            if test_name and (path.name, test_name) in PROVIDER_SCHEMA_ALLOWLIST:
                continue
            violations.append(f"{path.name}:{test_name or '<module>'}: use shared provider schema helper")

    assert violations == []


def _is_cleanwin_json_call(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cleanwin_json"
    )


def _is_schema_subscript(node: ast.AST) -> bool:
    return isinstance(node, ast.Subscript) and _slice_value(node.slice) == "schema"


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
