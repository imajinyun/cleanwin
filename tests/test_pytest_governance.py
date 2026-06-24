from __future__ import annotations

import ast
from pathlib import Path

HELPER_MODULES = {"conftest.py", "test_pytest_governance.py"}
AD_HOC_FILESYSTEM_METHODS = {"mkdir", "write_text", "write_bytes"}


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
