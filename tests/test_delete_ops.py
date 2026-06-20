from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity


class DeleteOpsTests(unittest.TestCase):
    def test_recycle_fails_closed_outside_windows_without_test_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            with patch.dict(os.environ, {"CLEANWIN_TEST_MODE": "0"}, clear=False):
                if os.name != "nt":
                    with self.assertRaises(RuntimeError):
                        safe_delete(str(target), dry_run=False, mode="recycle")
                    self.assertTrue(target.exists())

    def test_recycle_routes_to_test_trash_and_logs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            trash = root / "trash"
            log = root / "ops.jsonl"
            with patch.dict(os.environ, {"CLEANWIN_TEST_MODE": "1"}, clear=False):
                result = safe_delete(str(target), dry_run=False, mode="recycle", trash_root=trash, operation_log=log)
            self.assertEqual(result["status"], "recycled")
            self.assertFalse(target.exists())
            self.assertTrue(Path(result["destination"]).exists())
            record = json.loads(log.read_text(encoding="utf-8").strip())
            self.assertEqual(record["status"], "recycled")

    def test_symlinked_trash_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            real_trash = root / "real-trash"
            real_trash.mkdir()
            trash_link = root / "trash-link"
            try:
                trash_link.symlink_to(real_trash, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            with patch.dict(os.environ, {"CLEANWIN_TEST_MODE": "1"}, clear=False):
                with self.assertRaises(RuntimeError):
                    safe_delete(str(target), dry_run=False, mode="recycle", trash_root=trash_link)
            self.assertTrue(target.exists())

    def test_permanent_delete_requires_explicit_allow(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                safe_delete(str(target), dry_run=False, mode="permanent", allow_permanent=False)
            self.assertTrue(target.exists())

    def test_safe_delete_rechecks_expected_identity(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            identity = capture_filesystem_identity(target)
            target.write_text("changed", encoding="utf-8")
            with patch.dict(os.environ, {"CLEANWIN_TEST_MODE": "1"}, clear=False):
                with self.assertRaises(RuntimeError):
                    safe_delete(
                        str(target),
                        dry_run=False,
                        mode="recycle",
                        trash_root=root / "trash",
                        expected_identity=identity,
                    )
            self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
