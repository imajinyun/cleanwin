from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cleanwincli.core import validate_plan_payload
from cleanwincli.delete_ops import safe_delete
from cleanwincli.identity import capture_filesystem_identity, compare_identity
from cleanwincli.models import plan_from_dict
from cleanwincli.windows_identity import capture_windows_native_identity

ROOT = Path(__file__).resolve().parents[1]


class IdentityTests(unittest.TestCase):
    def run_cleanwin(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged = dict(os.environ)
        if env:
            merged.update(env)
        return subprocess.run(
            [sys.executable, str(ROOT / "cleanwin.py"), "--json", *args],
            cwd=ROOT,
            env=merged,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_capture_identity_contains_replay_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            identity = capture_filesystem_identity(target)
            self.assertEqual(identity["schema"], "cleanwin.filesystem-identity.v1")
            self.assertTrue(identity["exists"])
            self.assertEqual(identity["file_type"], "file")
            self.assertEqual(identity["size_bytes"], 1)
            self.assertIn("canonical_path", identity)
            self.assertIn("file_id", identity)
            self.assertIn("volume_serial_number", identity)
            self.assertIn("windows_file_index", identity)

    def test_windows_native_identity_falls_back_off_windows(self) -> None:
        if os.name == "nt":
            self.skipTest("fallback assertion is for non-Windows hosts")
        with TemporaryDirectory() as tmp:
            identity = capture_windows_native_identity(Path(tmp) / "candidate.tmp")
            self.assertFalse(identity["windows_native_available"])
            self.assertEqual(identity["windows_native_error"], "not-windows")
            self.assertIsNone(identity["volume_serial_number"])

    def test_compare_identity_detects_content_replacement(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            planned = capture_filesystem_identity(target)
            target.write_text("changed", encoding="utf-8")
            current = capture_filesystem_identity(target)
            mismatches = compare_identity(planned, current)
            self.assertTrue(any("size_bytes" in mismatch for mismatch in mismatches), mismatches)

    def test_generated_plan_contains_identity_and_validate_rejects_drift(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp_root = root / "Temp"
            temp_root.mkdir()
            target = temp_root / "stale.tmp"
            target.write_text("x", encoding="utf-8")
            plan_file = root / "plan.json"
            env = {"TEMP": str(temp_root), "TMP": str(temp_root)}
            plan_result = self.run_cleanwin("plan", "--categories", "temp", "--older-than-days", "0", "--output", str(plan_file), env=env)
            self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
            raw = json.loads(plan_file.read_text(encoding="utf-8"))
            self.assertEqual(raw["candidates"][0]["identity"]["schema"], "cleanwin.filesystem-identity.v1")
            plan = plan_from_dict(raw)
            self.assertTrue(validate_plan_payload(plan, raw, require_context=False)["valid"])

            target.write_text("changed", encoding="utf-8")
            validation = validate_plan_payload(plan, raw, require_context=False)
            self.assertFalse(validation["valid"])
            self.assertIn("Filesystem identity mismatch", "\n".join(validation["errors"]))

    def test_safe_delete_fails_closed_on_identity_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "candidate.tmp"
            target.write_text("x", encoding="utf-8")
            planned = capture_filesystem_identity(target)
            target.write_text("changed", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                safe_delete(
                    str(target),
                    dry_run=False,
                    mode="recycle",
                    trash_root=root / "trash",
                    expected_identity=planned,
                )
            self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
