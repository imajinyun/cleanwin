# 🧹 cleanwin — 完整指南

> **保守型 Windows 清理规划工具 · dry-run 优先 · 基于计划执行 · 面向 AI/MCP 集成**

cleanwin 是一个 Python CLI，用于检查 Windows 清理机会、生成机器可读计划、校验计划，并且只在明确人工确认门禁满足后执行。它的设计目标是“保守且可审计”：默认路径是只读或 dry-run，真实删除只能经过唯一安全出口。

- 根 README：[../../README.CN.md](../../README.CN.md)
- English docs: [README.md](README.md)

---

## 🚀 快速开始

```bash
# 查看能力、分类和安全默认值
python3 cleanwin.py --json capabilities

# 仅预览安全清理候选项
python3 cleanwin.py --json inspect --categories temp,dev-cache,package-cache,browser-cache,app-leftovers --max-items 10

# 生成可复用清理计划
python3 cleanwin.py --json plan --categories temp,dev-cache,app-leftovers --older-than-days 7 --output /tmp/cleanwin-plan.json

# 做任何破坏性动作前先校验和审查
python3 cleanwin.py --json validate-plan --plan-file /tmp/cleanwin-plan.json
python3 cleanwin.py --json review-plan --plan-file /tmp/cleanwin-plan.json

# dry-run 执行计划；返回匹配真实执行所需的确认 token
python3 cleanwin.py --json execute-plan --plan-file /tmp/cleanwin-plan.json
```

> 🛡️ `execute-plan` 不带 `--execute` 不会删除文件。真实执行必须同时提供 `--execute`、`--yes`、操作日志、精确确认短语和 dry-run 确认令牌。

---

## 📦 安装

cleanwin 无运行时依赖，需要 Python 3.10+。

```bash
# 从源码直接运行
python3 cleanwin.py --json capabilities

# 安装为可编辑 Python 包
python3 -m pip install -e .
cleanwin --json capabilities

# pyproject.toml 注册的 MCP 入口
cleanwin-mcp
```

项目元数据位于 `pyproject.toml`；命令入口是 `cleanwin` 和 `cleanwin-mcp`。

---

## ✨ 核心亮点

| 领域 | cleanwin 提供的能力 |
|---|---|
| 🧹 Dry-run 优先 | inspect、plan、validate、review 和计划 dry-run 都是安全默认路径 |
| 🪟 Windows 安全策略 | 拒绝 Windows 根目录、用户目录根、凭据、浏览器配置数据、WSL/Docker 数据和系统组件存储 |
| ♻️ 回收站优先 | 真实执行使用 Windows Recycle Bin；非 Windows 环境真实回收站执行在测试模式外 fail-closed |
| 🧾 计划完整性 | 计划包含 `cleanwin.plan.v1`、source fingerprint、主机上下文、文件身份、分类、规则和安全理由 |
| 🤖 AI 原生契约 | 导出 8 个结构化工具、provider 格式、host policy、readiness、runbook 和 self-test 报告 |
| 🏗️ MCP stdio server | 提供结构化 MCP 工具和资源，不接受 raw shell command |
| 🔐 唯一删除出口 | 破坏性清理只通过 `cleanwincli.delete_ops.safe_delete` |

---

## 🛡️ 安全模型

cleanwin 围绕 fail-closed 清理设计：

1. **默认不删除** — `inspect`、`plan`、`validate-plan`、`review-plan` 和不带 `--execute` 的 `execute-plan` 都是非破坏性的。
2. **先计划再执行** — 执行消费已生成的计划，而不是临时传入任意路径。
3. **Source fingerprint** — 计划校验会确认 payload 与 `source_fingerprint` 仍然匹配。
4. **主机/用户上下文** — 默认拒绝 user/home 上下文不匹配的计划。
5. **文件系统身份** — 候选项记录 identity 元数据；执行前可捕获文件变化。
6. **MVP 执行仅支持回收站模式** — 可执行计划必须使用 `delete_mode: recycle`。
7. **人工门禁** — 真实执行要求 `--execute`、`--yes`、`--operation-log`、精确确认短语和 dry-run token。
8. **唯一破坏性 primitive** — 只有 `cleanwincli.delete_ops.safe_delete` 拥有删除路由。
9. **回收站 fail-closed** — Recycle Bin 路由不可用、失败或不安全时，不会静默降级为永久删除。

真实执行门禁：

```text
已校验计划
  + --execute
  + --yes
  + --operation-log <jsonl path>
  + --confirmation-phrase "确认执行 cleanwin 清理"
  + --confirmation-token <匹配 dry-run 输出的 token>
  + delete_mode == recycle
```

---

## 🧹 清理分类

### 安全候选分类

这些分类在匹配文件/目录存在且通过路径校验时，会产生 `candidates`。

| 分类 | 范围 | 说明 |
|---|---|---|
| `temp` | `%TEMP%`、`%TMP%`、`%LOCALAPPDATA%\Temp` | 只考虑较旧条目，跳过 symlink/reparse point |
| `dev-cache` | pip、npm、Yarn、pnpm、NuGet、Cargo、Go、Gradle、Maven 缓存 | 包含 owner、rule ID、官方清理命令和可安全删除理由 |
| `package-cache` | WinGet、Scoop、Chocolatey、uv 缓存 | 面向可重新下载的软件包 payload/cache artifact |
| `browser-cache` | Chrome、Edge、Firefox 的 cache-only 目录 | 保护 cookies、密码、会话、扩展和 profile 数据库 |
| `app-leftovers` | 常用软件卸载后的缓存/日志残留 | 覆盖 Slack、经典/新版 Teams、Discord、Zoom、Skype、Webex、Viber、Element、VS Code、JetBrains/DataGrip 日志、Docker Desktop 日志、Postman、Notion、Figma、OBS Studio、Spotify、Adobe Creative Cloud、Office telemetry、游戏启动器、GPU shader cache、Telegram、Signal、WhatsApp、Cursor、Android Studio、VirtualBox 日志、VLC artwork cache、1Password/KeePassXC 诊断、GitHub Desktop、Obsidian、Unity Hub、Unreal/EA/GOG/Ubisoft 启动器缓存、Backblaze/Acronis/Macrium/FreeFileSync 诊断、Dropbox/Box/MEGAsync 日志、OneDrive/Google Drive/iCloud 诊断日志、Everything crash dump、SumatraPDF/Foxit 诊断、Thunderbird/Mailbird/eM Client 诊断、Zotero/Mendeley 诊断、DaVinci Resolve/Shotcut/Kdenlive 诊断或渲染缓存、Malwarebytes/NordVPN 诊断、Todoist、Linear、Canva、PowerShell startup cache、Windows Terminal diagnostics、Snagit/Camtasia/ShareX/Greenshot/Lightshot/ScreenToGif 日志、远程访问和 VPN 诊断日志、Wireshark/FileZilla/WinSCP 状态或日志、calibre cache、qBittorrent 日志、Git 客户端诊断日志、Kubernetes/容器桌面工具诊断日志、数据库/API 客户端诊断日志、笔记应用渲染缓存、图像/媒体工具缓存、设计工具缓存、Markdown 工具渲染缓存、扫描工具日志、OEM 支持工具诊断日志、创作辅助工具日志、打印工具日志、PowerToys 日志、Logitech G HUB 日志、Corsair iCUE 日志、SteelSeries GG 日志、Wacom 日志、Razer Synapse 日志等已审查残留；若仍检测到活动安装标记则跳过，并支持 `app-*`、package 版本目录、IDE 版本目录、`*.exe` 等带版本目录/文件名的通配安装标记 |

示例：

```bash
python3 cleanwin.py --json inspect --categories app-leftovers --rule-id app-leftovers.vscode.cached-data --older-than-days 0
```

### 只读报告分类

这些分类有意只生成 `findings`，不生成删除候选项。

| 分类 | 为什么只读 |
|---|---|
| `registry-report` | Registry 删除风险高，应先备份并优先使用厂商工具/人工审查 |
| `startup-report` | 启动项可能受策略管理，或属于安全/更新工具 |
| `windows-report` | WinSxS、Installer、SoftwareDistribution、Defender、Delivery Optimization 需要官方 Windows 工具处理 |
| `large-files` | Downloads、Desktop、Documents、OneDrive、SharePoint 通常包含用户数据 |
| `docker-report` | volumes、images、BuildKit cache、WSL 磁盘镜像可能包含持久状态 |
| `wsl-report` | 发行版和 `ext4.vhdx` 不能直接通过文件删除处理 |
| `visual-studio-report` | Installer 状态和 workloads 应通过 Visual Studio Installer / 官方命令管理 |
| `browser-cache-report` | 浏览器 profile 根目录混合缓存、凭据、会话和同步数据 |

---

## 💻 CLI 参考

### `capabilities`

输出机器可读能力和安全默认值。

```bash
python3 cleanwin.py --json capabilities
```

关键字段包括 `default_dry_run`、`safe_categories`、`read_only_categories`、`never_auto_execute`、`default_delete_mode` 和 AI 确认短语。

### `inspect`

预览候选项和只读发现项。

```bash
python3 cleanwin.py --json inspect \
  --categories temp,dev-cache,package-cache,browser-cache,app-leftovers \
  --older-than-days 7 \
  --max-items 100
```

选项：

| 选项 | 说明 |
|---|---|
| `--categories` | 逗号分隔分类列表；默认使用安全分类 |
| `--older-than-days` | 只考虑早于该天数阈值的条目 |
| `--max-items` | 最大候选项数量 |
| `--rule-id` | 按一个或多个规则 ID 过滤；可重复，也可逗号分隔 |

### `plan`

创建可复用 `cleanwin.plan.v1` payload。

```bash
python3 cleanwin.py --json plan \
  --categories temp,dev-cache,app-leftovers \
  --older-than-days 7 \
  --max-items 50 \
  --output /tmp/cleanwin-plan.json
```

### `validate-plan`

校验 schema、fingerprint、主机上下文、候选项安全性、文件身份和执行模式。

```bash
python3 cleanwin.py --json validate-plan --plan-file /tmp/cleanwin-plan.json
```

只有在受控测试中计划上下文故意不同，才应使用 `--no-require-plan-context`。

### `review-plan`

为人工或 AI 审查汇总计划。

```bash
python3 cleanwin.py --json review-plan --plan-file /tmp/cleanwin-plan.json
```

review 输出包含候选项汇总、规则汇总、官方清理命令、敏感排除项和执行交接要求。

### `execute-plan`

默认 dry-run：

```bash
python3 cleanwin.py --json execute-plan --plan-file /tmp/cleanwin-plan.json
```

dry-run 响应包含：

- `dry_run: true`
- 每个候选项的 dry-run 结果
- `confirmation.required_phrase`
- `confirmation.confirmation_token`

真实执行命令结构：

```bash
python3 cleanwin.py --json execute-plan \
  --plan-file /tmp/cleanwin-plan.json \
  --execute \
  --yes \
  --operation-log "$HOME/.cleanwin/operations.jsonl" \
  --confirmation-phrase "确认执行 cleanwin 清理" \
  --confirmation-token "<来自匹配 dry-run 的 token>"
```

> 在非 Windows 平台，真实 recycle 执行会 fail-closed，除非在测试中显式设置 `CLEANWIN_TEST_MODE=1`。

### AI 与治理命令

```bash
python3 cleanwin.py --json ai-tools
python3 cleanwin.py --json ai-tools --provider openai
python3 cleanwin.py --json ai-tools --provider anthropic
python3 cleanwin.py --json schema-registry
python3 cleanwin.py --json host-policy --validate
python3 cleanwin.py --json ai-readiness --validate
python3 cleanwin.py --json ai-self-test
python3 cleanwin.py --json ai-runbook
python3 cleanwin.py --json doctor
python3 cleanwin.py --json recovery-readiness
python3 cleanwin.py --json installed-app-inventory
python3 cleanwin.py --json official-command-plan
python3 cleanwin.py --json debloat-privacy-report
python3 cleanwin.py --json startup-service-inventory
```

---

## 🤖 AI 调用姿势

cleanwin 暴露 8 个 AI 工具：

| 工具 | 风险 | 可自动调用 | 用途 |
|---|---:|---:|---|
| `cleanwin_capabilities` | readonly | 是 | 发现分类、schema 和安全默认值 |
| `cleanwin_inspect` | readonly | 是 | 预览候选项/发现项 |
| `cleanwin_generate_plan` | planning | 是 | 生成计划文件 |
| `cleanwin_validate_plan` | planning | 是 | dry-run/执行前校验计划 |
| `cleanwin_review_plan` | planning | 是 | 为 review handoff 汇总计划 |
| `cleanwin_policy_simulate` | planning | 是 | 模拟 AI Host 执行策略 |
| `cleanwin_dry_run_plan` | dry-run | 是 | dry-run 计划并生成确认 token |
| `cleanwin_execute_plan` | destructive | 否 | 仅在人工门禁满足时执行 |

推荐 AI Host 流程：

```text
cleanwin_capabilities
  → cleanwin_inspect
  → cleanwin_generate_plan
  → cleanwin_validate_plan
  → cleanwin_review_plan
  → cleanwin_policy_simulate
  → cleanwin_dry_run_plan
  → 人工批准
  → cleanwin_execute_plan
```

AI Host 规则：

- 不传 raw shell command；工具参数只能是结构化 JSON。
- 不自动调用 `cleanwin_execute_plan`。
- 破坏性执行必须要求 `delete_mode: recycle`。
- 必须要求 `operation_log`、`confirmation_phrase` 和 `confirmation_token`。
- 执行前使用 `policy-simulate` 验证 host-side gates。

---

## 🏗️ MCP 服务器

cleanwin 内置 stdio MCP server：

```bash
python3 -m cleanwincli.mcp_server
# 或安装后
cleanwin-mcp
```

服务器能力：

- 将 cleanwin AI tool catalog 暴露为 MCP tools。
- 通过注册模板构造 argv。
- 拒绝未知工具和非法参数。
- 拒绝 raw command 参数。
- 调用 CLI 前应用 cleanwin host-policy 检查。
- 暴露 `cleanwin://ai/tools`、`cleanwin://ai/host-policy`、`cleanwin://ai/readiness`、`cleanwin://ai/self-test`、`cleanwin://engineering/doctor`、`cleanwin://engineering/recovery-readiness`、`cleanwin://inventory/installed-apps`、`cleanwin://plan/official-command-plan`、`cleanwin://inventory/debloat-privacy`、`cleanwin://inventory/startup-services` 等资源。

指定 MCP server 使用的 CLI 脚本或二进制：

```bash
CLEANWIN_CLI=/absolute/path/to/cleanwin.py python3 -m cleanwincli.mcp_server
```

---

## 🧪 安全测试模式执行

Test mode 仅用于受控开发和 CI。它会把 recycle 操作路由到沙箱 trash 目录，而不是 Windows Recycle Bin。

```bash
tmpdir=$(mktemp -d)
mkdir -p "$tmpdir/Temp"
printf 'cache' > "$tmpdir/Temp/stale.tmp"

TEMP="$tmpdir/Temp" TMP="$tmpdir/Temp" CLEANWIN_TEST_MODE=1 \
  python3 cleanwin.py --json plan --categories temp --older-than-days 0 --output "$tmpdir/plan.json"

TEMP="$tmpdir/Temp" TMP="$tmpdir/Temp" CLEANWIN_TEST_MODE=1 \
  python3 cleanwin.py --json execute-plan --plan-file "$tmpdir/plan.json" --no-require-plan-context
```

dry-run 输出的 token 只应复用于同一个计划 payload。

---

## ✅ 开发与 CI

常用本地检查通过项目虚拟环境运行：

```bash
make dev-install
make quality
```

`dev-install` target 会创建 `.venv`，安装 `.[dev]`，并用该环境运行 pytest、Ruff、mypy、compile、package、AI 和 MCP 检查。`make pytest` 和 `make pytest-governance-smoke` 会在测试进程结束后删除 pytest cache、coverage 文件和 `__pycache__`，同时保留 pytest 的退出码；`.venv` 会作为受管理的工具环境保留。`make ci-smoke` 对齐非 packaging CI 门禁，并在结束时执行同样的测试残留清理；`make quality` 会额外运行 install/package smoke，并执行更完整的 `make clean` 清理。等价手动命令：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check cleanwin.py cleanwincli tests
.venv/bin/python -m mypy cleanwin.py cleanwincli tests
.venv/bin/python -m compileall -q cleanwin.py cleanwincli tests
.venv/bin/python cleanwin.py --json ai-readiness --validate
.venv/bin/python cleanwin.py --json doctor
```

新增测试优先使用 pytest 函数风格，包括原生 `assert`、`tmp_path`、`monkeypatch`、`pytest.raises` 和 `pytest.mark.parametrize`。可复用的 subprocess 或 JSON helper 放入 `tests/conftest.py` 或专用 MCP helper，不要继续复制 `unittest.TestCase` setup 方法。payload schema、只读 payload 和报告、`safe_to_execute`、禁用执行契约、schema registry sample、命令序列断言、summary count、dry-run result summary，以及 `valid`、`ready`、`passed`、`allowed` 等布尔状态字段应复用共享 helper。重复的 expected membership、absence 和 substring 检查应使用 collection/text helper；孤立的一次性 `in`/`not in` 断言可以保留直接写法。重复的结构化集合 `any(...)` / `all(...)` 风格检查应使用 `assert_any_match`、`assert_all_match` 和 `assert_none_match`。重复的结构化字段检查应使用 `assert_field_values`、`assert_fields_present`、`assert_fields_not_none` 和 `field_value`；dot path 支持嵌套 dict 和数字列表下标，例如 `rule_summary.0.rule_id`。重复的严格序列、集合、唯一性、非空集合和 subprocess returncode 检查应使用 `assert_exact_sequence`、`assert_exact_set`、`assert_unique_items`、`assert_non_empty` 和 `assert_returncode`。重复的精确数量、下界、标量成员关系和任一文本片段检查应使用 `assert_exact_count`、`assert_at_least`、`assert_one_of` 和 `assert_text_contains_any`。重复的文件系统存在性检查应使用 `assert_path_exists` 和 `assert_path_missing`。异常路径测试应使用 `pytest.raises(..., match=...)` 校验错误信息契约。

Pytest 治理 smoke：

```bash
make pytest-governance-smoke
```

该检查会保持测试 pytest-native，约束直接 CLI subprocess 调用收敛到共享 helper，要求 `pytest.raises` 校验错误信息，保持遗留的直接 schema、只读布尔、`safe_to_execute`、execution-disabled flag、状态字段、summary 字段和 predicate 断言预算为空，检查已迁移文件的 collection/text/predicate/field/exact/scalar/path helper 采用情况，同时防止 CI 和 Docker 沙箱重新引入 `unittest discover` 或绕过项目 `.venv`。

可选 Docker 沙箱：

```bash
make docker-quality
```

CI 入口：

- `.github/workflows/ci.yml` 通过 Makefile target 在 Python 3.10 和 3.12 上运行 Linux 质量门禁，因此 pytest 入口会在结束后清理测试残留。
- `.github/workflows/ci.yml` 还会运行 package install smoke 和可选 Docker sandbox gate。
- `.github/workflows/windows-smoke.yml` 创建 `.venv`，安装 `.[dev]`，并在 `windows-latest` 上运行 pytest、Ruff、mypy、compile checks、identity drift smoke 和 test-mode recycle smoke。
- `.github/workflows/windows-smoke.yml` 包含 `always()` cleanup step，用于清理 build outputs、tool caches、pytest caches、coverage 文件、`htmlcov` 和 `__pycache__`。

治理路线图：

- [Windows cleaner gap roadmap](../governance/windows-cleaner-gap-roadmap.md) 跟踪清理覆盖、只读证据、恢复门禁和后续执行模型扩展的优先级 TODO。

---

## 🗺️ 项目地图

| 路径 | 职责 |
|---|---|
| `cleanwin.py` | 极薄 CLI 入口 |
| `cleanwincli/cli.py` | 参数解析和命令分发 |
| `cleanwincli/core.py` | inspect/plan/validate/review/execute 编排和报告 |
| `cleanwincli/collectors.py` | 保守候选项和只读 finding 收集器 |
| `cleanwincli/rule_catalog.py` | versioned 清理规则 catalog 加载与校验 |
| `cleanwincli/rules/cleanup_rules.v1.json` | 治理化清理规则 catalog 数据 |
| `cleanwincli/recovery.py` | 恢复 readiness 门禁与 snapshot 格式声明 |
| `cleanwincli/installed_apps.py` | 只读已安装应用 inventory 与 leftover 关联 |
| `cleanwincli/official_commands.py` | 只读 Windows 官方清理命令计划 |
| `cleanwincli/debloat_privacy.py` | 只读 debloat 和隐私 telemetry 报告 |
| `cleanwincli/startup_inventory.py` | 只读启动项、服务和计划任务 inventory |
| `cleanwincli/protection_data.py` | Windows 安全策略数据 |
| `cleanwincli/protection.py` | 路径和文件系统候选项校验 |
| `cleanwincli/delete_ops.py` | 唯一破坏性出口和 recycle/permanent 路由 primitive |
| `cleanwincli/operation_log.py` | JSONL 操作日志写入 |
| `cleanwincli/ai_schema.py` | AI 工具契约和 provider 导出 |
| `cleanwincli/ai_host_policy.py` | AI Host allow/deny 门禁 |
| `cleanwincli/mcp_server.py` | MCP stdio server |
| `tests/` | 单测和契约测试 |

---

## 🔒 非目标

cleanwin 有意不做：

- 自动清理 Windows Registry。
- 自动禁用启动项。
- 直接删除 Windows component stores。
- 删除浏览器凭据、cookies、会话或 profile 数据库。
- 自动删除用户 Documents/Desktop/Downloads/OneDrive/SharePoint。
- 通过 AI/MCP 工具接受 raw shell command。
