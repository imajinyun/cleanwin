from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows integration tests require Windows")
WriteTextFile = Callable[[Path, str], Path]


def test_native_identity_reports_windows_fields(tmp_path: Path, write_text_file: WriteTextFile) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    identity = capture_filesystem_identity(target)

    assert identity["windows_native_available"], identity
    assert identity["volume_serial_number"] is not None
    assert identity["windows_file_index"] is not None
    assert identity["windows_volume_serial_from_handle"] is not None


@pytest.mark.skipif(
    os.environ.get("CLEANWIN_RUN_WINDOWS_RECYCLE_INTEGRATION") != "1",
    reason="real Windows recycle integration is opt-in",
)
def test_real_windows_recycle_bin_smoke(tmp_path: Path, write_text_file: WriteTextFile) -> None:
    target = write_text_file(tmp_path / "candidate.tmp", "x")
    identity = capture_filesystem_identity(target)

    result = safe_delete(str(target), dry_run=False, mode="recycle", expected_identity=identity)

    assert result["status"] == "recycled"
    assert not target.exists()
