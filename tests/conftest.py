from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
JSONPayload = dict[str, Any]
RunCleanWin = Callable[..., subprocess.CompletedProcess[str]]
CleanWinResultJSON = Callable[[subprocess.CompletedProcess[str]], JSONPayload]
CleanWinJSON = Callable[..., JSONPayload]
CleanWinPlanFile = Callable[..., JSONPayload]


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def run_cleanwin(repo_root: Path) -> RunCleanWin:
    def _run_cleanwin(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)
        merged_env["PYTHONPATH"] = str(repo_root)
        return subprocess.run(
            [sys.executable, str(repo_root / "cleanwin.py"), "--json", *args],
            cwd=repo_root,
            env=merged_env,
            text=True,
            capture_output=True,
            check=False,
        )

    return _run_cleanwin


def load_json_stdout(result: subprocess.CompletedProcess[str]) -> JSONPayload:
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def cleanwin_result_json() -> CleanWinResultJSON:
    return load_json_stdout


@pytest.fixture
def cleanwin_json(run_cleanwin: RunCleanWin) -> CleanWinJSON:
    def _cleanwin_json(*args: str, env: dict[str, str] | None = None) -> JSONPayload:
        result = run_cleanwin(*args, env=env)
        assert result.returncode == 0, result.stderr
        return load_json_stdout(result)

    return _cleanwin_json


@pytest.fixture
def cleanwin_plan_file(run_cleanwin: RunCleanWin) -> CleanWinPlanFile:
    def _cleanwin_plan_file(plan_file: Path, *args: str, env: dict[str, str] | None = None) -> JSONPayload:
        result = run_cleanwin("plan", *args, "--output", str(plan_file), env=env)
        assert result.returncode == 0, result.stderr
        payload = json.loads(plan_file.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        return payload

    return _cleanwin_plan_file
