from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from cleanwincli.file_reports import FILE_REPORT_SCHEMA, file_report

JSONPayload = dict[str, Any]
CleanWinJSON = Callable[..., JSONPayload]
WriteBytesFile = Callable[[Path, bytes], Path]
AssertSchemaSample = Callable[[str], JSONPayload]


def test_file_report_finds_large_files_duplicates_extensions_and_onedrive(
    tmp_path: Path, write_bytes_file: WriteBytesFile
) -> None:
    downloads = tmp_path / "Downloads"
    onedrive = tmp_path / "OneDrive"
    downloads.mkdir()
    onedrive.mkdir()
    large = write_bytes_file(downloads / "installer.iso", b"a" * 128)
    duplicate_a = write_bytes_file(downloads / "copy-a.zip", b"duplicate-payload")
    duplicate_b = write_bytes_file(onedrive / "copy-b.zip", b"duplicate-payload")
    ignored = write_bytes_file(downloads / "node_modules" / "cache.bin", b"duplicate-payload")

    report = file_report(
        env={
            "CLEANWIN_FILE_REPORT_ROOTS": f"{downloads}{os.pathsep}{onedrive}",
            "ONEDRIVE": str(onedrive),
        },
        min_large_file_bytes=100,
        min_duplicate_bytes=8,
        max_files_scanned=20,
        hash_bytes=1024,
    )

    assert report["schema"] == FILE_REPORT_SCHEMA
    assert report["destructive"] is False
    assert report["executes_system_commands"] is False
    assert report["summary"]["file_count"] == 3
    assert report["summary"]["large_file_count"] == 1
    assert report["large_files"][0]["path"] == str(large)
    assert report["summary"]["duplicate_group_count"] == 1
    duplicate_group = report["duplicate_groups"][0]
    assert duplicate_group["safe_to_execute"] is False
    assert duplicate_group["potential_reclaimable_bytes"] == duplicate_a.stat().st_size
    assert {item["path"] for item in duplicate_group["files"]} == {str(duplicate_a), str(duplicate_b)}
    assert any(item["onedrive_or_cloud_path"] for item in duplicate_group["files"])
    assert {group["extension"] for group in report["extension_groups"]} >= {".iso", ".zip"}
    assert str(ignored) not in {item["path"] for group in report["duplicate_groups"] for item in group["files"]}


def test_file_report_traversal_budget_stops_scanning(tmp_path: Path, write_bytes_file: WriteBytesFile) -> None:
    root = tmp_path / "Downloads"
    for index in range(3):
        write_bytes_file(root / f"{index}.bin", b"x" * 10)

    report = file_report(env={"CLEANWIN_FILE_REPORT_ROOTS": str(root)}, min_duplicate_bytes=1, max_files_scanned=2)

    assert report["summary"]["file_count"] == 2
    assert report["traversal_budget"]["limit_reached"] is True


@pytest.mark.parametrize(
    "args",
    [
        ("file-report",),
        ("ai-tools", "--provider", "file-report"),
    ],
)
def test_cli_provider_exposes_file_report(
    args: tuple[str, ...], tmp_path: Path, cleanwin_json: CleanWinJSON, write_bytes_file: WriteBytesFile
) -> None:
    root = tmp_path / "Downloads"
    write_bytes_file(root / "large.bin", b"x" * 128)
    env = {"CLEANWIN_FILE_REPORT_ROOTS": str(root)}

    assert cleanwin_json(*args, env=env)["schema"] == FILE_REPORT_SCHEMA


def test_schema_registry_exposes_file_report(assert_schema_sample: AssertSchemaSample) -> None:
    assert_schema_sample(FILE_REPORT_SCHEMA)
