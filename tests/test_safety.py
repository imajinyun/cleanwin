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
JSONPayload = dict[str, object]
AssertFieldValues = Callable[[JSONPayload, dict[str, object]], JSONPayload]


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


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (r"HKLM\SYSTEM\CurrentControlSet\Services", True),
        (r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run", True),
        (r"HKCU\Software\ExampleVendor\Cache", False),
    ],
)
def test_registry_protected_prefixes_are_report_only(
    key: str, expected: bool, assert_field_values: AssertFieldValues
) -> None:
    assert_field_values({"protected": is_protected_registry_key(key)}, {"protected": expected})


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
    ("path", "expected"),
    [
        (r"C:\Users\alice\AppData\Local\npm-cache\_cacache", False),
        (r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cache", False),
        (r"C:\Users\alice\AppData\Local\Microsoft\Edge\User Data\Profile 1\Code Cache", False),
        (r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Profile 2\Cache", False),
        (r"C:\Users\alice\AppData\Local\Mozilla\Firefox\Profiles\abcd1234.work\cache2", False),
        (r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cookies", True),
        (r"C:\Users\alice\AppData\Roaming\Mozilla\Firefox\Profiles", True),
    ],
)
def test_browser_profile_sensitivity_is_classified(
    path: str, expected: bool, assert_field_values: AssertFieldValues
) -> None:
    assert_field_values({"sensitive": is_sensitive_user_data(path)}, {"sensitive": expected})


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\alice\.ssh\id_rsa",
        r"C:\Users\alice\.gnupg\private-keys-v1.d",
        r"C:\Users\alice\.aws\credentials",
        r"C:\Users\alice\.kube\config",
        r"C:\Users\alice\.azure\azureProfile.json",
        r"C:\Users\alice\.config\gcloud\credentials.db",
        r"C:\Users\alice\AppData\Roaming\Thunderbird\Profiles\xxxxxxxx.default-release",
        r"C:\Users\alice\AppData\Local\Microsoft\Outlook\outlook.pst",
    ],
)
def test_sensitive_user_data_paths_are_detected(path: str) -> None:
    assert is_sensitive_user_data(path)


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\alice\AppData\Local\npm-cache",
        r"C:\Users\alice\AppData\Local\Temp",
        r"C:\Users\alice\AppData\Local\Google\Chrome\User Data\Default\Cache",
    ],
)
def test_non_sensitive_paths_pass(path: str) -> None:
    assert not is_sensitive_user_data(path)
