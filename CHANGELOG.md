# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed

- `.gitignore` no longer ignores all JSON files; only generated artifact
  directories are excluded
- `aiflow.yaml` workspace globs use recursive `**/*` patterns
- Portable release workflow also triggers on `v*` tag pushes

### Security

- Installer verifies SHA256 checksum before extraction
- Installer refuses to replace non-empty directories that do not look like
  existing cleanwin installs

[Unreleased]: https://github.com/imajinyun/cleanwin/compare/v0.1.0...HEAD
