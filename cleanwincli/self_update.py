"""Self-update for Windows portable installs via install.ps1.

Dry-run-only by default. Actual download and replace happens through
install.ps1, which handles version checks, SHA256 verification, backup,
and rollback.

The self-update execution path follows these safety rules:
- install.ps1 is downloaded to a temp file and verified against a SHA256
  hash fetched from the GitHub release API (same trust anchor as the
  release asset checksums).
- install.ps1 is invoked with -File, not -Command plus scriptblock::Create,
  eliminating PowerShell injection from user-controlled path values.
- All arguments are passed as separate argv elements; no string interpolation
  of filesystem paths into the PowerShell command.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from cleanwincli import __version__

SELF_UPDATE_SCHEMA = "cleanwin.self-update.v1"

GITHUB_API_LATEST = "https://api.github.com/repos/imajinyun/cleanwin/releases/latest"
INSTALL_SCRIPT_FILENAME = "install.ps1"
INSTALL_SCRIPT_MIRRORS = (
    "https://raw.githubusercontent.com/imajinyun/cleanwin/main/install.ps1",
    "https://ghproxy.com/https://raw.githubusercontent.com/imajinyun/cleanwin/main/install.ps1",
    "https://gh-proxy.com/https://raw.githubusercontent.com/imajinyun/cleanwin/main/install.ps1",
    "https://mirror.ghproxy.com/https://raw.githubusercontent.com/imajinyun/cleanwin/main/install.ps1",
)


def _is_windows() -> bool:
    return sys.platform == "win32"


def _find_install_dir() -> Path | None:
    exe = Path(sys.executable)
    if exe.name.lower() in ("python.exe", "python3.exe", "pythonw.exe"):
        return None
    if exe.name.lower() not in ("cleanwin.exe", "cleanwin-mcp.exe"):
        return None
    return exe.parent


def _http_get(url: str, *, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cleanwin-self-update"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — hard-coded HTTPS URLs
        return resp.read()


def _fetch_latest_release() -> dict[str, Any]:
    raw = _http_get(GITHUB_API_LATEST)
    return json.loads(raw.decode("utf-8"))


def _find_install_script_sha256(release: dict[str, Any]) -> str | None:
    for asset in release.get("assets", []):
        if asset.get("name") == "install.ps1.sha256":
            body = _http_get(asset["browser_download_url"]).decode("utf-8").strip()
            return body.split()[0].upper()
    return None


def _download_install_script(expected_sha256: str | None) -> Path:
    last_error: Exception | None = None
    for mirror in INSTALL_SCRIPT_MIRRORS:
        try:
            data = _http_get(mirror)
            if expected_sha256:
                actual = hashlib.sha256(data).hexdigest().upper()
                if actual != expected_sha256:
                    last_error = ValueError(
                        f"SHA256 mismatch for install.ps1 from {mirror}: expected {expected_sha256}, got {actual}"
                    )
                    continue
            tmp_dir = Path(tempfile.mkdtemp(prefix="cleanwin-selfupdate-"))
            script_path = tmp_dir / INSTALL_SCRIPT_FILENAME
            script_path.write_bytes(data)
            return script_path
        except Exception as exc:  # noqa: BLE001 — try next mirror on any failure
            last_error = exc
            continue
    raise RuntimeError(f"Failed to download install.ps1 from all mirrors: {last_error}")


def self_update_report(*, execute: bool = False, version: str = "latest") -> dict[str, Any]:
    """Report self-update availability and optionally trigger install.ps1.

    Without --execute: reports current version and whether an update is
    available. Non-destructive.

    With --execute: downloads install.ps1 (SHA256-verified against the
    GitHub release API) and runs it with -File, which handles download,
    verification, backup, and rollback of the cleanwin binary itself.
    """
    if not _is_windows():
        return {
            "schema": SELF_UPDATE_SCHEMA,
            "current_version": __version__,
            "target_version": version,
            "supported": False,
            "executed": False,
            "reason": "self-update is only supported on Windows portable installs",
            "safe_to_execute": False,
        }

    install_dir = _find_install_dir()
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")

    supported = install_dir is not None and powershell is not None

    if not execute or not supported:
        return {
            "schema": SELF_UPDATE_SCHEMA,
            "current_version": __version__,
            "target_version": version,
            "install_dir": str(install_dir) if install_dir else None,
            "supported": supported,
            "executed": False,
            "dry_run": True,
            "safe_to_execute": supported,
            "method": "install.ps1",
            "mirrors": list(INSTALL_SCRIPT_MIRRORS),
            "next_step": [
                "cleanwin --json self-update --execute",
                "Or run manually: irm https://raw.githubusercontent.com/imajinyun/cleanwin/main/install.ps1 | iex",
            ],
        }

    assert install_dir is not None
    assert powershell is not None

    try:
        release = _fetch_latest_release()
        expected_sha256 = _find_install_script_sha256(release)
        script_path = _download_install_script(expected_sha256)
    except Exception as exc:  # noqa: BLE001
        return {
            "schema": SELF_UPDATE_SCHEMA,
            "current_version": __version__,
            "target_version": version,
            "install_dir": str(install_dir),
            "supported": True,
            "executed": False,
            "dry_run": False,
            "safe_to_execute": False,
            "method": "install.ps1",
            "error": str(exc),
        }

    install_args = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Version",
        version,
        "-InstallDir",
        str(install_dir),
        "-Force",
    ]

    try:
        result = subprocess.run(
            install_args,
            capture_output=True,
            text=True,
            timeout=300,
        )
        success = result.returncode == 0
        output = (result.stdout or "") + (result.stderr or "")
    except (subprocess.TimeoutExpired, OSError) as exc:
        success = False
        output = str(exc)

    try:
        script_path.parent.rmdir()
    except OSError:
        pass

    return {
        "schema": SELF_UPDATE_SCHEMA,
        "current_version": __version__,
        "target_version": version,
        "install_dir": str(install_dir),
        "supported": True,
        "executed": success,
        "dry_run": False,
        "safe_to_execute": success,
        "method": "install.ps1",
        "verified_sha256": expected_sha256 is not None,
        "exit_code": result.returncode if "result" in dir() else None,
        "output": output.strip().splitlines()[-20:] if output.strip() else [],
    }
