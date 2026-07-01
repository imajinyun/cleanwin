# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-02

### Added

- Windows portable release workflow producing `cleanwin-<version>-windows-x64.zip`
  with `cleanwin.exe`, `cleanwin-mcp.exe`, `LICENSE`, and `README.md`
- PowerShell installer (`install.ps1`) that downloads the latest portable
  release, verifies SHA256, installs under `%LOCALAPPDATA%\Programs\cleanwin`,
  and updates the user PATH
- Installer supports `-Version`, `-InstallDir`, `-NoPathUpdate`, `-Uninstall`,
  and `-Force` flags
- PyPI release workflow with Trusted Publisher OIDC publishing
- Windows quality matrix in main CI (Python 3.10 and 3.12 on windows-latest)
- End-to-end installer smoke test in the portable release workflow
- App-leftovers rules for common Windows applications
- Scoop bucket distribution at `imajinyun/cleanwin-bucket` with
  China-friendly mirror fallback chain
- Automatic Scoop bucket version bump on release via `repository_dispatch`

### Changed

- `.gitignore` no longer ignores all JSON files; only generated artifact
  directories are excluded
- `aiflow.yaml` workspace globs use recursive `**/*` patterns
- Portable release workflow also triggers on `v*` tag pushes
- Scoop bump moved into portable release workflow to avoid race between
  asset upload and dispatch

### Security

- Installer verifies SHA256 checksum before extraction
- Installer refuses to replace non-empty directories that do not look like
  existing cleanwin installs

[Unreleased]: https://github.com/imajinyun/cleanwin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/imajinyun/cleanwin/releases/tag/v0.1.0
