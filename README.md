# Novel Agent Workbench / 小说创作工作台

> A local-first AI writing workbench for web-novel authors, long-form novelists, and serial-fiction creators.
>
> 面向网文、长篇小说和系列故事创作者的本地优先 AI 写作工作台。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

## What it is / 它是什么

Novel Agent Workbench is a Windows desktop application for organizing the full long-form writing loop—not just generating an isolated paragraph:

Novel Agent Workbench 是一个面向长篇创作完整流程的 Windows 桌面应用，不只是生成一段孤立文字：

- outlines, characters, world-building, chapter plans, and Memory Bank;
- draft generation, AI review, revision requests, and rewrite candidates;
- candidate comparison and explicit promotion to a confirmed chapter;
- provider configuration, dry-runs, audit metadata, safety gates, and pre-publication checks;
- local project storage with recoverable write boundaries and a modern Windows desktop UI.

- 管理大纲、人物、世界观、章节规划和 Memory Bank；
- 生成草稿、AI 审稿、修订请求和重写候选；
- 对候选进行比较，并显式提交为确认稿；
- 管理 Provider、dry-run、审计元数据、安全 gate 和发布前检查；
- 使用本地项目存储、可恢复写入边界和现代 Windows 桌面界面。

It is designed for human-led writing workflows. It does not silently replace confirmed text, call real providers in the background, or decide which draft becomes canon.

它服务于“人主导、AI 辅助”的创作流程：不会静默替换确认稿，不会在后台调用真实 Provider，也不会自动决定哪一版草稿成为正文。

## Highlights / 核心能力

| Capability / 能力 | What it protects or enables / 作用 |
|---|---|
| Local-first projects / 本地优先 | Projects, drafts, confirmed chapters, settings, and runtime data stay on the local machine by default / 项目、草稿、确认稿、配置和运行数据默认保存在本机 |
| Draft → review → confirm / 草稿到确认稿 | Generated or rewritten text remains a candidate until the user explicitly promotes it / 生成或重写内容必须经过显式确认才会成为正文 |
| Memory Bank and context assembly / 记忆库与上下文装配 | Build metadata-first context packages, stream Memory Bank generation/compression progress, and require an explicit save gate / 默认以元数据构建上下文包，支持记忆生成/压缩进度，并要求显式保存 |
| AI review and revision / AI 审稿与修订 | Record review requests, compare rewrite candidates, and preserve decision gates / 记录审稿请求、比较重写候选并保留决策 gate |
| Model Settings v2 / 模型设置 v2 | Manage provider profiles, refreshable and cached model catalogs, manual models, and per-feature assignments / 管理 Provider 档案、可刷新与缓存的模型目录、手工模型和按功能分配 |
| DeepSeek prefix stability / DeepSeek 前缀稳定化 | Keep low-change context ahead of dynamic instructions and expose cache hit/miss usage; actual hit rate depends on service behavior / 稳定低频上下文并把动态指令放在末尾，保留命中/未命中统计；实际命中率取决于服务行为 |
| Provider safety boundary / Provider 安全边界 | Mock and dry-run paths are available; real network execution requires explicit user action and preflight gates / 提供 mock 与 dry-run，真实网络调用必须由用户显式触发并通过 preflight |
| Modern desktop UI / 现代桌面界面 | Rounded glass panels, theme/font settings, and in-app studios for model settings, Memory Bank, outline, and world materials / 圆角磨砂面板、主题与字体设置，以及模型设置、记忆库、大纲和世界观工作室 |
| Responsive Windows desktop workflow / 响应式 Windows 桌面流程 | Build a local EXE with the included scripts; the user package lives in `dist\NovelAgentWorkbench` and keeps existing `用户数据` / 使用仓库内脚本构建本地 EXE；用户包位于 `dist\NovelAgentWorkbench`，会保留已有 `用户数据` |

## Workflow / 工作流

```text
Project → outline / characters / world-building
        → chapter plan → draft candidate
        → AI review or manual rewrite request
        → rewrite candidates → human comparison
        → explicit confirmed-chapter commit
```

```text
项目 → 大纲 / 人物 / 世界观
    → 章节规划 → 草稿候选
    → AI 审稿或人工修订请求
    → 重写候选 → 人工比较
    → 显式提交为确认稿
```

Every high-impact transition is represented as a visible action or gate. The application favors recoverability and auditability over autonomous background automation.

每个高影响转换都通过可见操作或 gate 表达。应用优先保证可恢复和可审计，而不是追求后台自动化。

## Quick start on Windows / Windows 快速开始

### Requirements / 环境要求

- Windows 10/11;
- Python `>=3.10`;
- network access on the first build to install packaging dependencies;
- `py` or `python` available on `PATH`.

### Build the desktop EXE / 构建桌面 EXE

Clone the repository, enter its root, and run:

```cmd
BUILD_NovelAgentWorkbench.bat
```

构建完成后，给用户使用的目录是：

```text
dist\NovelAgentWorkbench\
  NovelAgentWorkbench.exe
  _internal\
  用户数据\          已有作品、设置和密钥会保留
```

重新打包只会替换 EXE 和 `_internal`，不会删除 `用户数据`。

The build script shows environment checks and packaging output in the foreground. To prepare only the development environment:

如果只准备开发环境、不构建 EXE：

```cmd
SETUP_ENV.bat
```

For non-interactive checks:

```cmd
SETUP_ENV.bat --no-pause
BUILD_NovelAgentWorkbench.bat --no-pause
```

### Run from source / 从源码运行

After environment setup:

```cmd
.venv\Scripts\novel-agent-workbench-desktop.exe
```

默认打开现代界面。如果还没安装 `pywebview`，会自动回退到经典 Tk 界面。

The default desktop entry opens the modern UI. If `pywebview` is missing, it falls back to the classic Tkinter UI.

现代界面入口：

- 顶栏：专注、模型设置、外观（字体/字号/浅色深色）
- 右侧：大纲与章节、世界观与人物、记忆库、打开文件夹、导出 TXT
- 稿纸：自动保存、重新生成、审稿、精修、确认稿

经典界面 / classic UI:

```cmd
.venv\Scripts\novel-agent-workbench-classic.exe
```

或 / or:

```cmd
START_ModernUI.cmd
```

实际生成的运行项目、`.venv`、本地密钥和构建输出不会提交到 GitHub。

Runtime projects, `.venv`, local secrets, and build outputs should not be committed to GitHub.

## Provider boundary / 模型调用边界

The codebase includes adapters and settings for OpenAI-compatible endpoints, DeepSeek, Chutes, SiliconFlow, OpenRouter, local OpenAI-compatible endpoints, and a deterministic mock provider. Availability and enablement are controlled by the current project configuration and safety gates.

代码包含 OpenAI-compatible endpoint、DeepSeek、Chutes、SiliconFlow、OpenRouter、本地 OpenAI-compatible endpoint 和确定性 mock Provider 的适配与设置。具体可用性由当前项目配置和安全 gate 决定。

The following are intentionally separate:

以下两类行为必须区分：

- implementation, tests, packaging, and documentation are local work and should not spend real API credits;
- product actions such as connection tests, draft generation, review, or revision may call a configured provider only after explicit user action.

- 实现、测试、打包和文档更新属于本地工作，不应消耗真实 API 额度；
- 连接测试、草稿生成、审稿和修订等产品动作，只有在用户明确触发后才可调用已配置 Provider。

Provider responses and logs are constrained by sanitizer, audit, metadata-only output, secret-reference, and preflight rules. Consult the provider contract before extending a real network path.

Provider 响应和日志受到 sanitizer、审计、元数据输出、密钥引用和 preflight 规则约束。扩展真实网络路径前，请先阅读 Provider 契约。

## Architecture at a glance / 架构速览

```text
src/novel_agent_workbench/
├── modern_desktop.py           modern WebView desktop host
├── modern_ui/                  HTML/CSS/JS workbench and studios
├── desktop_app.py              classic Tkinter fallback UI
├── application_service.py      UI/backend application boundary
├── cli.py                       backend CLI entrypoint
├── providers.py                 provider adapters and call policy
├── model_settings.py            model-role settings
├── storage.py                   local projects, checkpoints, registry
├── context_assembler.py        metadata-first context package assembly
├── drafts.py / reviews.py       draft and review workflows
├── revisions.py                rewrite candidates and decisions
└── audit.py / project_health.py publication and safety checks
```

Repository-level folders:

仓库主要目录：

```text
src/          application source
scripts/      EXE build helpers
packaging/    desktop launcher
codex_docs/   architecture notes and contracts
docs/         current handoff notes
```

## Developer entry points / 开发入口

| Path / 路径 | Purpose / 用途 |
|---|---|
| [`src/novel_agent_workbench/modern_desktop.py`](src/novel_agent_workbench/modern_desktop.py) | Modern WebView desktop host / 现代桌面宿主 |
| [`src/novel_agent_workbench/modern_ui/`](src/novel_agent_workbench/modern_ui/) | Workbench and studio UI / 工作台与工作室界面 |
| [`src/novel_agent_workbench/desktop_app.py`](src/novel_agent_workbench/desktop_app.py) | Classic Tkinter fallback UI / 经典 Tk 回退界面 |
| [`docs/handoff.md`](docs/handoff.md) | Current product handoff / 当前产品交接 |
| [`src/novel_agent_workbench/application_service.py`](src/novel_agent_workbench/application_service.py) | UI/backend application-service boundary / UI 与后端应用服务边界 |
| [`src/novel_agent_workbench/cli.py`](src/novel_agent_workbench/cli.py) | Backend CLI / 后端 CLI |
| [`src/novel_agent_workbench/providers.py`](src/novel_agent_workbench/providers.py) | Provider adapters and call policy / Provider 适配与调用策略 |
| [`src/novel_agent_workbench/storage.py`](src/novel_agent_workbench/storage.py) | Local storage and checkpoints / 本地存储与 checkpoint |
| [`codex_docs/CLI_QUICKSTART.md`](codex_docs/CLI_QUICKSTART.md) | CLI operations / CLI 操作 |
| [`codex_docs/APPLICATION_SERVICE_CONTRACT.md`](codex_docs/APPLICATION_SERVICE_CONTRACT.md) | Service contracts / 应用服务契约 |
| [`codex_docs/PROVIDER_ADAPTER_CONTRACT.md`](codex_docs/PROVIDER_ADAPTER_CONTRACT.md) | Provider extension rules / Provider 扩展规则 |
| [`codex_docs/IMPORTANT_OPEN_ISSUES.md`](codex_docs/IMPORTANT_OPEN_ISSUES.md) | Known issues and limits / 已知问题与限制 |

## Do not upload / 不要上传

Never commit the following to the public repository:

不要向公开仓库提交以下内容：

- local manuscripts, draft text, confirmed chapter text, or private corpora;
- API keys, tokens, endpoint secrets, or plaintext secret values;
- `.venv/`, `dist/`, `old/`, build output, coverage output, or runtime project data;
- local UI preference files and historical MVP log markdown;
- any private or unauthorized source material.

- 本地小说正文、草稿、确认稿或私人语料；
- API key、Token、Endpoint secret 或明文密钥；
- `.venv/`、`dist/`、`old/`、构建产物、Coverage 产物或运行时项目数据；
- 本地界面偏好和历史 MVP 日志 markdown；
- 任何私人或未经授权的源材料。

## Project status / 项目状态

The repository is an actively developed multi-stage MVP. The implemented path spans local project storage, model settings, draft generation, review and revision, Memory Bank/context assembly, and a modern Windows desktop UI packaged as a local EXE.

仓库目前是持续开发中的多阶段 MVP，已经覆盖本地项目存储、模型设置、草稿生成、审稿与修订、Memory Bank/上下文装配，以及可打包为本地 EXE 的现代 Windows 桌面界面。

The default desktop product is the modern UI. Classic Tkinter remains as a fallback.

默认桌面产品是现代界面；经典 Tkinter 仅作回退。

## License / 许可证

GNU Affero General Public License v3.0 ([AGPL-3.0](LICENSE)).

GNU Affero General Public License v3.0（[AGPL-3.0](LICENSE)）。
