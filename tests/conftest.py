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
CleanWinJSON = Callable[..., JSONPayload]


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def run_cleanwin(repo_root: Path) -> RunCleanWin:
    def _run_cleanwin(*args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo_root)
        return subprocess.run(
            [sys.executable, str(repo_root / "cleanwin.py"), "--json", *args],
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    return _run_cleanwin


def load_json_stdout(result: subprocess.CompletedProcess[str]) -> JSONPayload:
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def cleanwin_json(run_cleanwin: RunCleanWin) -> CleanWinJSON:
    def _cleanwin_json(*args: str) -> JSONPayload:
        return load_json_stdout(run_cleanwin(*args))

    return _cleanwin_json
