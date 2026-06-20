"""Windows-native filesystem identity helpers for CleanWin."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path
from typing import Any


def _empty_native_identity(*, available: bool, reason: str | None = None) -> dict[str, Any]:
    return {
        "windows_native_available": available,
        "windows_native_error": reason,
        "volume_serial_number": None,
        "windows_file_index": None,
        "windows_file_index_high": None,
        "windows_file_index_low": None,
        "windows_volume_serial_from_handle": None,
        "windows_number_of_links": None,
        "windows_file_attributes_native": None,
        "windows_owner_sid": None,
        "windows_volume_name": None,
        "windows_filesystem_name": None,
        "windows_max_component_length": None,
        "windows_filesystem_flags": None,
    }


def _volume_root(path: Path) -> str:
    drive = path.drive or Path(path.resolve(strict=False)).drive
    if drive:
        return drive.rstrip("\\/") + "\\"
    return ""


def capture_windows_volume_identity(path: Path) -> dict[str, Any]:
    if os.name != "nt":
        return _empty_native_identity(available=False, reason="not-windows")
    root = _volume_root(path)
    if not root:
        return _empty_native_identity(available=False, reason="missing-volume-root")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    volume_name = ctypes.create_unicode_buffer(261)
    filesystem_name = ctypes.create_unicode_buffer(261)
    serial = ctypes.c_uint32(0)
    max_component = ctypes.c_uint32(0)
    flags = ctypes.c_uint32(0)
    ok = kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        volume_name,
        len(volume_name),
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem_name,
        len(filesystem_name),
    )
    if not ok:
        error = ctypes.get_last_error()
        return _empty_native_identity(available=False, reason=f"GetVolumeInformationW failed: {error}")
    payload = _empty_native_identity(available=True)
    payload.update(
        {
            "volume_serial_number": int(serial.value),
            "windows_volume_name": volume_name.value,
            "windows_filesystem_name": filesystem_name.value,
            "windows_max_component_length": int(max_component.value),
            "windows_filesystem_flags": int(flags.value),
        }
    )
    return payload


def capture_windows_handle_identity(path: Path) -> dict[str, Any]:
    if os.name != "nt":
        return _empty_native_identity(available=False, reason="not-windows")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):  # type: ignore[misc]
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    generic_read = 0x80000000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    file_flag_open_reparse_point = 0x00200000
    invalid_handle_value = ctypes.c_void_p(-1).value

    handle = kernel32.CreateFileW(
        ctypes.c_wchar_p(str(path)),
        generic_read,
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_flag_backup_semantics | file_flag_open_reparse_point,
        None,
    )
    if handle == invalid_handle_value:
        error = ctypes.get_last_error()
        return _empty_native_identity(available=False, reason=f"CreateFileW failed: {error}")
    try:
        info = BY_HANDLE_FILE_INFORMATION()
        ok = kernel32.GetFileInformationByHandle(handle, ctypes.byref(info))
        if not ok:
            error = ctypes.get_last_error()
            return _empty_native_identity(available=False, reason=f"GetFileInformationByHandle failed: {error}")
        file_index = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
        payload = _empty_native_identity(available=True)
        payload.update(
            {
                "windows_file_index": file_index,
                "windows_file_index_high": int(info.nFileIndexHigh),
                "windows_file_index_low": int(info.nFileIndexLow),
                "windows_volume_serial_from_handle": int(info.dwVolumeSerialNumber),
                "windows_number_of_links": int(info.nNumberOfLinks),
                "windows_file_attributes_native": int(info.dwFileAttributes),
            }
        )
        return payload
    finally:
        kernel32.CloseHandle(handle)


def capture_windows_native_identity(path: Path) -> dict[str, Any]:
    if os.name != "nt":
        return _empty_native_identity(available=False, reason="not-windows")
    volume = capture_windows_volume_identity(path)
    handle = capture_windows_handle_identity(path)
    merged = dict(volume)
    merged.update({key: value for key, value in handle.items() if value is not None or key == "windows_native_error"})
    if volume.get("windows_native_available") or handle.get("windows_native_available"):
        merged["windows_native_available"] = True
        merged["windows_native_error"] = handle.get("windows_native_error") or volume.get("windows_native_error")
    return merged
