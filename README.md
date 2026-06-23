# 🧹 cleanwin

> **Windows cleanup planner · Dry-run first · AI-native MCP integration**

- [📗 English Docs](/docs/doc/README.md)
- [📕 中文文档](/docs/doc/README.CN.md)

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

# 🤖 AI tool definitions (8 tools)
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
| 🗑️ **Uninstall leftover cleanup** | Expands safe cleanup for reviewed common app cache/log leftovers after uninstall |
| ♻️ **Recycle by default** | Real cleanup routes to Windows Recycle Bin; non-Windows execution fails closed outside test mode |
| 🧾 **Plan contract** | `cleanwin.plan.v1` captures source fingerprint, host/user context, rule metadata, and filesystem identity |
| 🤖 **AI-native · 8 tools** | Provider exports for Anthropic / OpenAI plus host-policy simulation and readiness reports |
| 🏗️ **MCP Server** | Built-in Model Context Protocol stdio server with structured tool arguments only |
| 🔐 **Multi-layer gates** | Confirmation phrase, dry-run token, operation log, context validation, and single deletion exit |
| 📦 **Zero deps** | Pure Python 3.10+, no runtime dependencies |

---

## 📖 Documentation

| Guide | Link |
|---|---|
| 📗 **English** — full CLI reference, safety model, AI/MCP patterns, development | [docs/doc/README.md](docs/doc/README.md) |
| 📕 **中文** — 完整命令参考、安全模型、AI/MCP 调用姿势、开发验证 | [docs/doc/README.CN.md](docs/doc/README.CN.md) |
| 🗺️ **Governance roadmap** — prioritized Windows cleaner gap TODOs | [docs/governance/windows-cleaner-gap-roadmap.md](docs/governance/windows-cleaner-gap-roadmap.md) |

---

## 🧩 Quick Index

- [🛡️ Safety Model](docs/doc/README.md#️-safety-model)
- [🧹 Cleanup Categories](docs/doc/README.md#-cleanup-categories)
- [💻 CLI Reference](docs/doc/README.md#-cli-reference)
- [🤖 AI Invocation Patterns](docs/doc/README.md#-ai-invocation-patterns)
- [🏗️ MCP Server](docs/doc/README.md#️-mcp-server)
- [✅ Development & CI](docs/doc/README.md#-development--ci)
- [🗺️ Governance Roadmap](docs/governance/windows-cleaner-gap-roadmap.md)
- [📕 中文安全模型](docs/doc/README.CN.md#️-安全模型)
- [📕 中文 AI 调用姿势](docs/doc/README.CN.md#-ai-调用姿势)

---

## 💻 Installation

```bash
# ▶️ Run directly
python3 cleanwin.py --json capabilities

# 📥 Install as editable package
python3 -m pip install -e .
cleanwin --json capabilities
cleanwin-mcp
```

> Requires Python 3.10+. Runtime dependencies: none.

---

## 🔗 Links

- [📗 Full English Guide](docs/doc/README.md)
- [📕 中文文档](docs/doc/README.CN.md)
- [🗺️ Governance roadmap](docs/governance/windows-cleaner-gap-roadmap.md)
- [🧪 Windows smoke workflow](.github/workflows/windows-smoke.yml)
- [📦 Project metadata](pyproject.toml)
