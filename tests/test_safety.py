from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from cleanwincli.protection import (
    is_protected_registry_key,
    is_sensitive_user_data,
    validate_filesystem_candidate,
    validate_path_text,
)

WriteTextFile = Callable[[Path, str], Path]


def dangerous_windows_paths() -> list[str]:
    fixture = Path(__file__).parent / "data" / "dangerous_paths.txt"
    return fixture.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("path", dangerous_windows_paths())
def test_dangerous_windows_paths_are_rejected(path: str) -> None:
    with pytest.raises(RuntimeError, match="Refusing (protected|sensitive)"):
        validate_path_text(path)


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("relative\\cache", "Refusing non-absolute path"),
        ("C:\\Users\\alice\\..\\Windows", "Refusing path with traversal component"),
        ("C:\\Temp\\bad\x00name", "Refusing path with control characters"),
    ],
)
def test_relative_traversal_and_control_paths_are_rejected(path: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        validate_path_text(path)


def test_registry_protected_prefixes_are_report_only() -> None:
    assert is_protected_registry_key(r"HKLM\SYSTEM\CurrentControlSet\Services") is True
    assert is_protected_registry_key(r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run") is True
    assert is_protected_registry_key(r"HKCU\Software\ExampleVendor\Cache") is False


def test_symlink_candidate_is_rejected(tmp_path: Path, write_text_file: WriteTextFile) -> None:
    target = write_text_file(tmp_path / "target" / "entry", "x").parent
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(RuntimeError, match="Refusing symlink/reparse-point candidate"):
        validate_filesystem_candidate(link)


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cache",
        r"C:\Users\alice\AppData\Local\Microsoft\Edge\User Data\Profile 1\Code Cache",
        r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Profile 2\Cache",
        r"C:\Users\alice\AppData\Local\Mozilla\Firefox\Profiles\abcd1234.work\cache2",
    ],
)
def test_browser_cache_suffix_is_allowed(path: str) -> None:
    assert is_sensitive_user_data(path) is False


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cookies",
        r"C:\Users\alice\AppData\Roaming\Mozilla\Firefox\Profiles",
    ],
)
def test_browser_profile_data_remains_sensitive(path: str) -> None:
    assert is_sensitive_user_data(path) is True
