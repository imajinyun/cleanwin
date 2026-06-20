from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cleanwincli.protection import is_protected_registry_key, is_sensitive_user_data, validate_filesystem_candidate, validate_path_text


class SafetyTests(unittest.TestCase):
    def test_dangerous_windows_paths_are_rejected(self) -> None:
        fixture = Path(__file__).parent / "data" / "dangerous_paths.txt"
        for line in fixture.read_text(encoding="utf-8").splitlines():
            with self.subTest(path=line):
                with self.assertRaises(RuntimeError):
                    validate_path_text(line)

    def test_relative_traversal_and_control_paths_are_rejected(self) -> None:
        for path in ["relative\\cache", "C:\\Users\\alice\\..\\Windows", "C:\\Temp\\bad\x00name"]:
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    validate_path_text(path)

    def test_registry_protected_prefixes_are_report_only(self) -> None:
        self.assertTrue(is_protected_registry_key(r"HKLM\SYSTEM\CurrentControlSet\Services"))
        self.assertTrue(is_protected_registry_key(r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"))
        self.assertFalse(is_protected_registry_key(r"HKCU\Software\ExampleVendor\Cache"))

    def test_symlink_candidate_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(RuntimeError):
                validate_filesystem_candidate(link)

    def test_browser_cache_suffix_is_allowed_but_profile_data_remains_sensitive(self) -> None:
        self.assertFalse(is_sensitive_user_data(r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cache"))
        self.assertFalse(is_sensitive_user_data(r"C:\Users\alice\AppData\Local\Microsoft\Edge\User Data\Profile 1\Code Cache"))
        self.assertFalse(is_sensitive_user_data(r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Profile 2\Cache"))
        self.assertFalse(is_sensitive_user_data(r"C:\Users\alice\AppData\Local\Mozilla\Firefox\Profiles\abcd1234.work\cache2"))
        self.assertTrue(is_sensitive_user_data(r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cookies"))
        self.assertTrue(is_sensitive_user_data(r"C:\Users\alice\AppData\Roaming\Mozilla\Firefox\Profiles"))


if __name__ == "__main__":
    unittest.main()
