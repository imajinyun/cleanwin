"""CleanWin package."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

__all__ = ["__version__"]


def _resolve_version() -> str:
    try:
        return importlib.metadata.version("cleanwin")
    except importlib.metadata.PackageNotFoundError:
        pass

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        in_project = False
        for raw_line in pyproject.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                in_project = line == "[project]"
                continue
            if in_project and line.startswith("version") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass

    return "0.0.0"


__version__ = _resolve_version()
