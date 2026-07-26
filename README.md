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
- local project storage with recoverable write boundaries and a Tkinter desktop UI.

- 管理大纲、人物、世界观、章节规划和 Memory Bank；
- 生成草稿、AI 审稿、修订请求和重写候选；
- 对候选进行比较，并显式提交为确认稿；
- 管理 Provider、dry-run、审计元数据、安全 gate 和发布前检查；
- 使用本地项目存储、可恢复写入边界和 Tkinter 桌面界面。

It is designed for human-led writing workflows. It does not silently replace confirmed text, call real providers in the background, or decide which draft becomes canon.

它服务于“人主导、AI 辅助”的创作流程：不会静默替换确认稿，不会在后台调用真实 Provider，也不会自动决定哪一版草稿成为正文。

## Highlights / 核心能力

| Capability / 能力 | What it protects or enables / 作用 |
|---|---|
| Local-first projects / 本地优先 | Projects, drafts, confirmed chapters, settings, and runtime data stay on the local machine by default / 项目、草稿、确认稿、配置和运行数据默认保存在本机 |
| Draft → review → confirm / 草稿到确认稿 | Generated or rewritten text remains a candidate until the user explicitly promotes it / 生成或重写内容必须经过显式确认才会成为正文 |
| Memory Bank and context assembly / 记忆库与上下文装配 | Build metadata-first context packages and prompt previews without exposing text by default / 默认以元数据构建上下文包和 Prompt 预览，避免泄露正文 |
| AI review and revision / AI 审稿与修订 | Record review requests, compare rewrite candidates, and preserve decision gates / 记录审稿请求、比较重写候选并保留决策 gate |
| Provider safety boundary / Provider 安全边界 | Mock and dry-run paths are available; real network execution requires explicit user action and preflight gates / 提供 mock 与 dry-run，真实网络调用必须由用户显式触发并通过 preflight |
| Windows desktop workflow / Windows 桌面流程 | Build a local EXE with the included BAT and PowerShell scripts / 使用仓库内 BAT 与 PowerShell 脚本构建本地 EXE |

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

构建完成后，EXE 位于：

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

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
├── desktop_app.py              Tkinter desktop UI
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
codex_docs/   architecture notes, contracts, and operating constraints
codex_logs/   project development logs
src/          application source
tests/        unit and safety tests
scripts/      build helpers
```

## Verification / 验证

Run the unit test suite without enabling a real Provider:

不启用真实 Provider，运行单元测试：

```powershell
py -m unittest discover -s tests
```

The current main branch passes **32 tests** in the maintained test suite. Tests cover project storage, desktop helpers, draft and review gates, provider safety, Memory Bank/context behavior, and metadata-only output boundaries.

当前 main 分支维护的测试套件为 **32 个通过测试**，覆盖项目存储、桌面辅助逻辑、草稿与审稿 gate、Provider 安全、Memory Bank/上下文行为以及元数据输出边界。

## Developer entry points / 开发入口

| Path / 路径 | Purpose / 用途 |
|---|---|
| [`src/novel_agent_workbench/desktop_app.py`](src/novel_agent_workbench/desktop_app.py) | Tkinter desktop UI / 桌面界面 |
| [`src/novel_agent_workbench/application_service.py`](src/novel_agent_workbench/application_service.py) | UI/backend application-service boundary / UI 与后端应用服务边界 |
| [`src/novel_agent_workbench/cli.py`](src/novel_agent_workbench/cli.py) | Backend CLI / 后端 CLI |
| [`src/novel_agent_workbench/providers.py`](src/novel_agent_workbench/providers.py) | Provider adapters and call policy / Provider 适配与调用策略 |
| [`src/novel_agent_workbench/storage.py`](src/novel_agent_workbench/storage.py) | Local storage and checkpoints / 本地存储与 checkpoint |
| [`tests/README.md`](tests/README.md) | Test scope and safety assertions / 测试范围与安全断言 |
| [`codex_docs/CLI_QUICKSTART.md`](codex_docs/CLI_QUICKSTART.md) | CLI operations / CLI 操作 |
| [`codex_docs/APPLICATION_SERVICE_CONTRACT.md`](codex_docs/APPLICATION_SERVICE_CONTRACT.md) | Service contracts / 应用服务契约 |
| [`codex_docs/PROVIDER_ADAPTER_CONTRACT.md`](codex_docs/PROVIDER_ADAPTER_CONTRACT.md) | Provider extension rules / Provider 扩展规则 |
| [`codex_docs/IMPORTANT_OPEN_ISSUES.md`](codex_docs/IMPORTANT_OPEN_ISSUES.md) | Known issues and limits / 已知问题与限制 |

## Do not upload / 不要上传

Never commit the following to the public repository:

不要向公开仓库提交以下内容：

- local manuscripts, draft text, confirmed chapter text, or private corpora;
- API keys, tokens, endpoint secrets, or plaintext secret values;
- `.venv/`, build output, coverage output, or runtime project data;
- any private or unauthorized source material.

- 本地小说正文、草稿、确认稿或私人语料；
- API key、Token、Endpoint secret 或明文密钥；
- `.venv/`、构建产物、Coverage 产物或运行时项目数据；
- 任何私人或未经授权的源材料。

## Project status / 项目状态

The repository is an actively developed multi-stage MVP. The implemented path spans local project storage, model settings, draft generation, review and revision workflows, Memory Bank/context assembly, corpus profiling, manual rewrite, provider gates, audit, and Windows desktop packaging.

仓库目前是持续开发中的多阶段 MVP，已经覆盖本地项目存储、模型设置、草稿生成、审稿与修订、Memory Bank/上下文装配、语料分析、人工重写、Provider gate、审计和 Windows 桌面打包。

The public README intentionally summarizes the architecture rather than listing every internal development log. Historical implementation notes remain in [`codex_logs/`](codex_logs/) and the commit history.

公开 README 刻意总结架构，不逐条复制内部开发日志。历史实现记录保留在 [`codex_logs/`](codex_logs/) 和提交历史中。

## License / 许可证

GNU Affero General Public License v3.0 ([AGPL-3.0](LICENSE)).

GNU Affero General Public License v3.0（[AGPL-3.0](LICENSE)）。
