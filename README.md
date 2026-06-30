# 🧹 cleanwin

> **Windows cleanup planner · Dry-run first · AI-native MCP integration**

AI-friendly Windows cleanup CLI with safe dry-runs, reusable cleanup plans,
read-only inventory reports, governed execution gates, and machine-readable
contracts for agents and automation.

- [📗 English Docs](/docs/doc/README.md)
- [📕 中文文档](/docs/doc/README.CN.md)
- [🤖 Agent Workflow](AGENTS.md)
- [📄 License](LICENSE)

---

## 🚀 TL;DR

```bash
# 🧪 Safe preview
python3 cleanwin.py --json inspect --categories temp,dev-cache,package-cache,browser-cache,app-leftovers --max-items 10

# 🧭 Create a reusable cleanup plan
python3 cleanwin.py --json plan --categories temp,dev-cache,app-leftovers --older-than-days 7 --output /tmp/cleanwin-plan.json

# ✅ Validate and review before any execution
python3 cleanwin.py --json validate-plan --plan-file /tmp/cleanwin-plan.json
python3 cleanwin.py --json review-plan --plan-file /tmp/cleanwin-plan.json

# 🤖 AI tool definitions (12 tools)
python3 cleanwin.py --json ai-tools --provider anthropic

# 🏗️ MCP stdio server
python3 -m cleanwincli.mcp_server
```

> 🛡️ **Safety principle:** Nothing is deleted by default. `execute-plan` without `--execute` is always a dry-run. Real execution requires a validated plan, `--execute`, `--yes`, an operation log, recycle mode, the exact confirmation phrase, and a dry-run confirmation token.

---

## ✨ Highlights

| 🏷️ | Description |
|---|---|
| 🧹 **Dry-run first** | Inspect, plan, validate, review, and dry-run are the default workflow |
| 🪟 **Windows-aware safety** | Protects Windows roots, user libraries, credentials, browser profiles, WSL, Docker, and servicing stores |
| 🗑️ **Uninstall leftover cleanup** | Expands safe cleanup for reviewed common app cache/log leftovers after uninstall, including Electron apps, IDEs, text editors, Git clients, database/API clients, network debugging tools, Kubernetes/container desktop tools, virtualization/emulator tools, local AI/model tools, remote access/VPN tools, game streaming tools, game launchers, sync/backup clients, backup clients, cloud transfer clients, media servers, eBook/audiobook apps, audio/media players, search tools, password managers, PDF readers, mail clients, reference managers, note apps, collaboration/chat/meeting tools, terminal caches, terminal/SSH client diagnostics, transfer clients, archive tools, boot media/image writer tools, screenshot/scanner tools, live capture tools, audio workstation tools, 3D printing/modeling/CAD tools, image viewers, image/media tools, video editors, design tools, Markdown tools, cleaner utilities, disk analyzers, hardware diagnostics, OEM support tools, creator utilities, printing utilities, peripheral utilities, security tools, and diagnostic logs |
| ♻️ **Recycle by default** | Real cleanup routes to Windows Recycle Bin; non-Windows execution fails closed outside test mode |
| 🧾 **Plan contract** | `cleanwin.plan.v1` captures source fingerprint, host/user context, rule metadata, and filesystem identity |
| 🤖 **AI-native · 12 tools** | Provider exports for Anthropic / OpenAI plus workflow routing, environment indexing, host-policy simulation, and readiness reports |
| 🏗️ **MCP Server** | Built-in Model Context Protocol stdio server with structured tool arguments only |
| 🔐 **Multi-layer gates** | Confirmation phrase, dry-run token, operation log, context validation, and single deletion exit |
| 📦 **Zero deps** | Pure Python 3.10+, no runtime dependencies |

---

## 📖 Documentation

| Guide | Link |
|---|---|
| 📗 **English** — full CLI reference, safety model, AI/MCP patterns, development | [docs/doc/README.md](docs/doc/README.md) |
| 📕 **中文** — 完整命令参考、安全模型、AI/MCP 调用姿势、开发验证 | [docs/doc/README.CN.md](docs/doc/README.CN.md) |
| 🤖 **Agent workflow** — repository guardrails for AI coding agents and maintainers | [AGENTS.md](AGENTS.md) |

---

## 🧩 Quick Index

- [🛡️ Safety Model](docs/doc/README.md#️-safety-model)
- [🧹 Cleanup Categories](docs/doc/README.md#-cleanup-categories)
- [💻 CLI Reference](docs/doc/README.md#-cli-reference)
- [🤖 AI Invocation Patterns](docs/doc/README.md#-ai-invocation-patterns)
- [🏗️ MCP Server](docs/doc/README.md#️-mcp-server)
- [✅ Development & CI](docs/doc/README.md#-development--ci)
- [🤖 Agent Workflow](AGENTS.md)
- [📕 中文安全模型](docs/doc/README.CN.md#️-安全模型)
- [📕 中文 AI 调用姿势](docs/doc/README.CN.md#-ai-调用姿势)

---

## 💻 Installation

```bash
# ▶️ Run directly
python3 cleanwin.py --json capabilities

# 🪟 Install from the Windows portable release
# Download cleanwin-<version>-windows-x64.zip from GitHub Releases, unzip it,
# then run:
.\cleanwin.exe --json doctor
.\cleanwin.exe --json inspect --categories temp,dev-cache --max-items 10

# 🧰 Install the Windows portable release into the user PATH
irm https://github.com/imajinyun/cleanwin/releases/latest/download/install.ps1 -OutFile install-cleanwin.ps1
powershell -ExecutionPolicy Bypass -File .\install-cleanwin.ps1
cleanwin --json doctor

# 📦 Install from PyPI with pipx after publication
pipx install cleanwin
cleanwin --json doctor
cleanwin-mcp

# 📥 Install as editable package
python3 -m pip install -e .
cleanwin --json capabilities
cleanwin-mcp
```

> Requires Python 3.10+. Runtime dependencies: none.

Windows portable releases are produced as `cleanwin-<version>-windows-x64.zip`
with `cleanwin.exe`, `cleanwin-mcp.exe`, `LICENSE`, `README.md`, and a SHA256
checksum. `install.ps1` is attached to the GitHub Release; download it first,
then run it locally. It downloads the latest portable release, verifies the
published checksum, installs under `%LOCALAPPDATA%\Programs\cleanwin`, updates
the user `PATH`, and runs `cleanwin.exe --json doctor`.

---

## ✅ Development Workflow

Use the repository Makefile so tooling is installed and executed inside `.venv`:

```bash
make lint
make pytest
make type
make compile
make ci-smoke
```

`make ci-smoke` mirrors the Linux CI quality gate. `make quality` runs the full
local gate, including packaging, smoke checks, and cleanup. `make pytest` and
`make pytest-governance-smoke` remove pytest caches, coverage files, and
`__pycache__` after pytest finishes while preserving the test exit code. `.venv`
is kept as the managed tool environment, not treated as a test leftover. Use
`make clean` for build/cache cleanup and `make docker-quality` when Docker is
installed and image pulls are allowed. See [AGENTS.md](AGENTS.md) for the full
agent workflow.

---

## 📄 License

cleanwin is released under the [MIT License](LICENSE).

---

## 🔗 Links

- [📗 Full English Guide](docs/doc/README.md)
- [📕 中文文档](docs/doc/README.CN.md)
- [🤖 Agent workflow](AGENTS.md)
- [📄 MIT License](LICENSE)
- [🧪 Windows smoke workflow](.github/workflows/windows-smoke.yml)
- [📦 Project metadata](pyproject.toml)
