# 🧹 cleanwin

> **Windows 清理规划工具 · Dry-run 优先 · AI 原生 MCP 集成**

AI 友好的 Windows 清理 CLI，提供安全 dry-run、可复用清理计划、只读
inventory/report、治理化执行门禁，以及面向 agent 和自动化的机器可读契约。

- [📗 English Docs](/docs/doc/README.md)
- [📕 中文文档](/docs/doc/README.CN.md)
- [🤖 Agent 工作流](AGENTS.md)
- [📄 License](LICENSE)

---

## 🚀 快速开始

```bash
# 🧪 安全预览
python3 cleanwin.py --json inspect --categories temp,dev-cache,package-cache,browser-cache,app-leftovers --max-items 10

# 🧭 生成可复用清理计划
python3 cleanwin.py --json plan --categories temp,dev-cache,app-leftovers --older-than-days 7 --output /tmp/cleanwin-plan.json

# ✅ 执行前校验与审查
python3 cleanwin.py --json validate-plan --plan-file /tmp/cleanwin-plan.json
python3 cleanwin.py --json review-plan --plan-file /tmp/cleanwin-plan.json

# 🤖 AI 工具清单（8 个工具）
python3 cleanwin.py --json ai-tools --provider anthropic
```

> 🛡️ **安全原则：** 默认不删除。`execute-plan` 不带 `--execute` 永远是 dry-run；真实执行必须同时满足计划校验、`--execute`、`--yes`、操作日志、回收站模式、精确确认短语和 dry-run 确认令牌。

---

## ✨ 核心亮点

| 🏷️ | 说明 |
|---|---|
| 🧹 **Dry-run 优先** | inspect、plan、validate、review 和 dry-run 是默认工作流 |
| 🪟 **Windows 安全策略** | 保护 Windows 根目录、用户库、凭据、浏览器配置、WSL、Docker 和系统组件存储 |
| 🗑️ **卸载残留清理增强** | 扩展对常用软件卸载后缓存/日志残留的安全清理覆盖 |
| ♻️ **默认走回收站** | 真实清理路由到 Windows Recycle Bin；非 Windows 环境真实执行默认 fail-closed |
| 🧾 **计划契约** | `cleanwin.plan.v1` 记录 source fingerprint、主机/用户上下文、规则元数据和文件身份 |
| 🤖 **AI 原生 · 8 个工具** | 支持 Anthropic / OpenAI 导出、Host Policy 模拟和 readiness 报告 |
| 🏗️ **MCP Server** | 内置 Model Context Protocol stdio server，只接受结构化工具参数 |
| 🔐 **多层门禁** | 确认短语、dry-run token、操作日志、上下文校验和唯一删除出口 |
| 📦 **零依赖** | 纯 Python 3.10+，无运行时依赖 |

---

## 📖 详细文档

| 文档 | 链接 |
|---|---|
| 📕 **中文指南** — 完整命令参考、安全模型、AI/MCP 调用姿势、开发验证 | [docs/doc/README.CN.md](docs/doc/README.CN.md) |
| 📗 **English Guide** — full CLI reference, safety model, AI/MCP patterns, development | [docs/doc/README.md](docs/doc/README.md) |
| 🤖 **Agent 工作流** — AI 编码 agent 和维护者的仓库工作流与安全边界 | [AGENTS.md](AGENTS.md) |

---

## 🧩 快速索引

- [🛡️ 安全模型](docs/doc/README.CN.md#️-安全模型)
- [🧹 清理分类](docs/doc/README.CN.md#-清理分类)
- [💻 CLI 参考](docs/doc/README.CN.md#-cli-参考)
- [🤖 AI 调用姿势](docs/doc/README.CN.md#-ai-调用姿势)
- [🏗️ MCP 服务器](docs/doc/README.CN.md#️-mcp-服务器)
- [✅ 开发与 CI](docs/doc/README.CN.md#-开发与-ci)
- [🤖 Agent 工作流](AGENTS.md)

---

## 💻 安装

```bash
# ▶️ 直接运行
python3 cleanwin.py --json capabilities

# 📥 安装为可编辑包
python3 -m pip install -e .
cleanwin --json capabilities
cleanwin-mcp
```

> 需要 Python 3.10+。运行时依赖：无。

---

## ✅ 开发工作流

使用仓库 Makefile，让工具安装和执行都发生在 `.venv` 中：

```bash
make lint
make pytest
make type
make compile
```

`make quality` 会运行完整本地质量门，包括打包和 smoke checks。Docker 已安装且允许拉取镜像时，可使用 `make docker-quality` 做沙箱验证。完整 agent 工作流见 [AGENTS.md](AGENTS.md)。

---

## 📄 License

cleanwin 使用 [MIT License](LICENSE) 发布。

---

## 🔗 链接

- [📕 详细中文文档](docs/doc/README.CN.md)
- [📗 English Documentation](docs/doc/README.md)
- [🤖 Agent 工作流](AGENTS.md)
- [📄 MIT License](LICENSE)
- [🧪 Windows smoke workflow](.github/workflows/windows-smoke.yml)
- [📦 项目元数据](pyproject.toml)
