"""Operation log writer for CleanWin execute flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cleanwincli.models import utc_now


def write_operation_log(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload.setdefault("timestamp", utc_now())
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
