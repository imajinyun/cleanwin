from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity


@unittest.skipUnless(os.name == "nt", "Windows integration tests require Windows")
class WindowsIntegrationTests(unittest.TestCase):
    def test_native_identity_reports_windows_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            identity = capture_filesystem_identity(target)
            self.assertTrue(identity["windows_native_available"], identity)
            self.assertIsNotNone(identity["volume_serial_number"])
            self.assertIsNotNone(identity["windows_file_index"])
            self.assertIsNotNone(identity["windows_volume_serial_from_handle"])

    @unittest.skipUnless(
        os.environ.get("CLEANWIN_RUN_WINDOWS_RECYCLE_INTEGRATION") == "1",
        "real Windows recycle integration is opt-in",
    )
    def test_real_windows_recycle_bin_smoke(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            identity = capture_filesystem_identity(target)
            result = safe_delete(str(target), dry_run=False, mode="recycle", expected_identity=identity)
            self.assertEqual(result["status"], "recycled")
            self.assertFalse(target.exists())
