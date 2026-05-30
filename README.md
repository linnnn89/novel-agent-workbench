# Novel Agent Workbench / 小说创作工作台

[中文说明](#中文说明) | [English](#english)

---

## 中文说明

Novel Agent Workbench（小说创作工作台）是一个本地运行、可恢复、面向长篇小说和网文创作的 AI 辅助写作桌面工具。它强调项目隔离、本地数据优先、显式操作边界、草稿与确认稿分离，以及可审计的模型调用流程。

本项目适合用于：

- 长篇小说、网文、系列故事的本地创作管理。
- 角色设定、世界观设定、章节规划和记忆库管理。
- AI 草稿生成、AI 审稿、修改建议、重写候选和人工确认稿流程。
- 多模型 Provider 配置、连接测试、调用审计和安全发布前检查。
- Windows 本地桌面工具打包与个人工作流实验。

### 中文搜索关键词

小说创作工作台，AI 小说写作，AI 网文写作，长篇小说创作工具，本地小说写作软件，角色设定，世界观设定，章节规划，记忆库，AI 审稿，章节重写，重新生成章节，审稿精修，小说草稿管理，网文创作助手。

### 快速看点

- **一键 Windows 构建**：双击 `BUILD_NovelAgentWorkbench.bat` 即可生成本地桌面 EXE。
- **面向长篇创作**：支持项目隔离、章节规划、世界观/角色资料、Memory Bank 和确认稿导出。
- **草稿安全边界**：AI 生成、AI 审稿、人工重写和确认稿提交是分离流程，不自动覆盖正文。
- **多模型接入**：支持 OpenAI-compatible Provider、DeepSeek、Chutes、本地 OpenAI-compatible endpoint 和 mock Provider。
- **开源发布友好**：`.gitignore`、`prepublish-check` 和 `project-health` 用于避免上传密钥、构建产物和本地写作数据。

### 核心设计原则

- **Local-first**：项目数据、草稿、确认稿、记忆库和本地配置优先保存在本机。
- **Recoverable**：关键写入操作前尽量创建 checkpoint 或可恢复备份。
- **Explicit gates**：草稿生成、审稿、修改、确认稿提交、真实模型调用都需要明确动作触发。
- **Draft vs confirmed boundary**：AI 生成或人工重写的内容先进入草稿候选，不自动变成确认稿。
- **Metadata-only safety**：默认状态、日志、审计和预览尽量只输出元数据，避免泄露正文、提示词或密钥。
- **Provider call boundary**：实现、测试、打包和文档更新阶段默认不消耗真实 API；产品中的真实 Provider 调用必须由用户显式触发。

### 主要功能

- 多项目创建、打开和列表管理。
- 项目级配置和本地密钥分离。
- 角色、世界观、章节规划和 Memory Bank 的结构化管理。
- 草稿生成、审稿、修订请求、重写候选、候选比较和确认稿提交。
- 上下文包预览、最终提示词渲染 dry-run、Provider 执行 gate、runbook、authorization 和 preflight。
- OpenAI-compatible Provider、DeepSeek、Chutes、本地 OpenAI-compatible endpoint 和 mock Provider 适配框架。
- Provider 调用审计、smoke test、安全检查、prepublish-check 和 project-health。
- Windows Tkinter 桌面启动器和 PyInstaller 打包脚本。

### 当前实现状态

当前仓库已经完成从本地项目存储、Provider 配置、安全审计、草稿生成、审稿、修订、Memory Bank、上下文装配、语料分析、人工重写、最终 Provider gate，到 Windows 桌面启动器的多阶段 MVP 实现。

最新 README 不逐条列出所有内部 MVP 日志；详细开发过程可参考 `codex_docs/`、提交记录和测试用例。当前重点状态是：

- 最终 Provider 路径已经形成 gate -> runbook -> authorization -> preflight -> real execution -> postcheck 的显式链路。
- Provider 输出会经过 sanitizer，以避免 reasoning markup 等不应保存的内容进入草稿。
- Smoke-test drafts 仅保留为证据，不允许提升为确认稿。
- 上传发布前由 `.gitignore`、`prepublish-check` 和 `project-health` 共同保护。
- 桌面启动器保持 local-first，不应在启动时或隐藏后台流程中调用模型。

### 目录结构

```text
codex_docs/   持久化架构说明、接口契约、交班文档和重要问题记录
codex_logs/   操作日志
src/          应用源码
tests/        单元测试和安全测试
scripts/      构建脚本
workspace_projects/  本地运行项目目录，通常不上传 GitHub
```

### 模型调用边界

产品可以在用户明确触发动作时调用已配置的模型 Provider，例如连接测试、草稿生成、审稿、修订或未来的 Memory Bank 更新。此类调用应使用项目本地 Provider 设置、安全密钥引用、可见动作标签和审计元数据。

Codex 开发、测试、打包和文档更新与产品真实调用不同。在实现阶段，除非用户明确授权某一次真实调用，否则不应消耗 API 额度或访问真实 LLM/API Provider。

### 验证命令

```powershell
py -3.10 -m unittest discover -s tests
```

最近记录的结果：

```text
Ran 312 tests
OK
```

### 安装与运行（Windows）

最低环境：

- Windows 10/11。
- Python 3.10 或更新版本，并建议安装时勾选 `Add python.exe to PATH`。也可以使用 Windows Python Launcher，即 `py` 命令。
- 首次构建需要联网安装 Python 打包依赖：`pyinstaller` 和 `pillow`。

从 GitHub 下载或 clone 仓库后，进入仓库根目录，直接双击：

```cmd
BUILD_NovelAgentWorkbench.bat
```

该 BAT 使用仓库相对路径，会在前台窗口显示环境检查、依赖安装和 PyInstaller 打包步骤。构建完成后会提示：

```text
您的运行 EXE 在:
  <repo-root>\dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

随后可以双击该 EXE 运行，也可以在 BAT 末尾按提示选择立即启动。

如果只想安装开发环境、不打包 EXE，可运行：

```cmd
SETUP_ENV.bat
```

非交互验证可用：

```cmd
SETUP_ENV.bat --no-pause
BUILD_NovelAgentWorkbench.bat --no-pause
```

源码方式启动桌面程序：

```cmd
.venv\Scripts\novel-agent-workbench-desktop.exe
```

注意：仓库不上传 `.venv/`、运行时项目、本地密钥或构建输出；这些会在本机生成。桌面程序默认使用本地运行数据目录，真实 API 调用只应由用户在界面中明确触发。

### 后端 CLI smoke 示例

```powershell
$env:PYTHONPATH="<repo-root>\src"
py -3.10 -m novel_agent_workbench.cli --projects-root <repo-root>\workspace_projects smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
```

### 二次开发入口

面向开发者的主要入口如下：

```text
src/novel_agent_workbench/desktop_app.py          Tkinter 桌面界面
src/novel_agent_workbench/application_service.py  桌面 UI 与后端能力之间的应用服务层
src/novel_agent_workbench/cli.py                  后端 CLI 命令入口
src/novel_agent_workbench/providers.py            模型 Provider 适配层
src/novel_agent_workbench/storage.py              本地项目存储、checkpoint 和 registry
tests/                                            单元测试
codex_docs/                                       架构说明、接口契约和操作约束
```

开发者建议先运行：

```cmd
SETUP_ENV.bat
py -3.10 -m unittest discover -s tests
```

如果新增真实模型调用能力，请保持显式用户触发、metadata-only 审计、密钥不落日志、草稿不自动确认这四条边界。

### 操作文档

```text
codex_docs\CLI_QUICKSTART.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
codex_docs\IMPORTANT_OPEN_ISSUES.md
```

### 不上传的内容

请不要向 GitHub 上传以下内容：

- `.venv/`、构建产物、coverage 输出。
- 本地真实写作项目、草稿正文、确认稿正文。
- API key、token、endpoint secret 或明文密钥。
- 不适合公开的私人设定、私人语料或未授权文本。

### License

本项目使用 **GNU Affero General Public License v3.0（AGPL-3.0）**。详见根目录 `LICENSE` 文件。

AGPL-3.0 是强 copyleft 许可证，尤其适合 WebUI 或可能作为网络服务运行的软件。若修改版通过网络提供给用户使用，通常需要向这些远程用户提供对应修改版源码。

---

## English

Novel Agent Workbench is a local, recoverable AI-assisted writing workbench for long-form novels and serial fiction. It focuses on project isolation, local-first data management, explicit operation boundaries, separation between draft candidates and confirmed chapters, and auditable model-provider workflows.

This project is useful for:

- Managing long-form novels, web novels, and serial fiction projects locally.
- Organizing characters, world-building notes, chapter plans, and a Memory Bank.
- Generating AI drafts, running AI reviews, recording revision requests, comparing rewrite candidates, and promoting only approved drafts to confirmed chapters.
- Configuring multiple model providers with connection tests, audit metadata, and pre-publication safety checks.
- Experimenting with a Windows local desktop writing workflow.

### Chinese search keywords

小说创作工作台，AI 小说写作，AI 网文写作，长篇小说创作工具，本地小说写作软件，角色设定，世界观设定，章节规划，记忆库，AI 审稿，章节重写，重新生成章节，审稿精修，小说草稿管理，网文创作助手。

### Highlights

- **One-click Windows build**: double-click `BUILD_NovelAgentWorkbench.bat` to produce a local desktop EXE.
- **Built for long-form writing**: project isolation, chapter planning, world/character materials, Memory Bank, and confirmed-draft export.
- **Safe draft boundary**: AI generation, AI review, manual rewrite, and confirmed-chapter promotion are separate explicit workflows.
- **Multiple model backends**: OpenAI-compatible providers, DeepSeek, Chutes, local OpenAI-compatible endpoints, and a deterministic mock provider.
- **Open-source release guardrails**: `.gitignore`, `prepublish-check`, and `project-health` help keep secrets, build outputs, and local writing data out of GitHub.

### Core design principles

- **Local-first**: project data, drafts, confirmed chapters, memory files, and local configuration are stored locally by default.
- **Recoverable**: important write operations should create checkpoints or recoverable backups where possible.
- **Explicit gates**: draft generation, review, revision, confirmation, and real model-provider execution require explicit user-triggered actions.
- **Draft vs confirmed boundary**: AI-generated or manually rewritten text first becomes a draft candidate; it is not automatically promoted to confirmed text.
- **Metadata-only safety**: state summaries, logs, audits, and previews should default to metadata-only output to avoid leaking manuscript text, prompts, or secrets.
- **Provider call boundary**: implementation, testing, packaging, and documentation work should not spend real API credits unless the user explicitly authorizes a specific real run.

### Main features

- Multi-project creation, opening, and listing.
- Project-level configuration with local secret separation.
- Structured management for characters, world-building notes, chapter plans, and Memory Bank entries.
- Draft generation, review, revision requests, rewrite candidates, candidate comparison, and confirmed-chapter commit gates.
- Context package preview, final prompt render dry-run, Provider execution gate, runbook, authorization, and preflight checks.
- Adapter framework for OpenAI-compatible providers, DeepSeek, Chutes, local OpenAI-compatible endpoints, and a deterministic mock provider.
- Provider call audit, smoke tests, safety checks, prepublish checks, and project health summaries.
- Windows Tkinter desktop launcher and PyInstaller build script.

### Current status

The repository has implemented a multi-stage MVP from local project storage, Provider configuration, safety audit, draft generation, review, revision, Memory Bank, context assembly, corpus profiling, manual rewrite workflow, final Provider gate, and Windows desktop launcher.

This README no longer lists every internal MVP item line by line. For detailed development history, see `codex_docs/`, commit history, and the test suite. The current high-level status is:

- The final Provider path now has an explicit chain: gate -> runbook -> authorization -> preflight -> real execution -> postcheck.
- Provider output is passed through a sanitizer to prevent reasoning markup or other non-draft material from being saved into drafts.
- Smoke-test drafts are retained as evidence only and must not be promoted to confirmed chapters.
- Upload readiness is guarded by `.gitignore`, `prepublish-check`, and `project-health`.
- The desktop launcher is local-first and should not call models on startup or through hidden background flows.

### Folder map

```text
codex_docs/   durable architecture notes, interface contracts, handoff documents, and important issue records
codex_logs/   operation logs
src/          application source code
tests/        unit tests and safety tests
scripts/      build scripts
workspace_projects/  local runtime project directory, usually not uploaded to GitHub
```

### Provider call boundary

The product may call configured model providers when the user explicitly starts an action such as connection testing, draft generation, review, revision, or a future Memory Bank update. Those calls should use project-local provider settings, safe secret references, visible action labels, and audit metadata.

Codex development, testing, packaging, and documentation updates are different from real product calls. During implementation work, tests should not spend API credits or access real LLM/API providers unless the user explicitly authorizes that specific real run.

### Verification command

```powershell
py -3.10 -m unittest discover -s tests
```

Latest recorded result:

```text
Ran 312 tests
OK
```

### Installation and Running (Windows)

Minimum environment:

- Windows 10/11.
- Python 3.10 or newer. Select `Add python.exe to PATH` during installation when possible. The Windows Python Launcher, `py`, is also supported.
- The first build needs network access to install Python packaging dependencies: `pyinstaller` and `pillow`.

After downloading or cloning the repository from GitHub, enter the repository root and double-click:

```cmd
BUILD_NovelAgentWorkbench.bat
```

The BAT uses paths relative to the repository root and shows environment checks, dependency installation, and PyInstaller packaging steps in the foreground console. When the build finishes, it prints:

```text
Your runnable EXE is here:
  <repo-root>\dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

You can then double-click that EXE, or choose to launch it from the BAT prompt.

To install the development environment without building the EXE, run:

```cmd
SETUP_ENV.bat
```

For non-interactive verification:

```cmd
SETUP_ENV.bat --no-pause
BUILD_NovelAgentWorkbench.bat --no-pause
```

To run the desktop app from source:

```cmd
.venv\Scripts\novel-agent-workbench-desktop.exe
```

Note: the repository does not upload `.venv/`, runtime projects, local secrets, or build output. These are generated locally. The desktop app uses local runtime data by default, and real API calls should only happen after an explicit user action in the UI.

### Backend-only CLI smoke example

```powershell
$env:PYTHONPATH="<repo-root>\src"
py -3.10 -m novel_agent_workbench.cli --projects-root <repo-root>\workspace_projects smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
```

### Developer Entry Points

Main files for developers:

```text
src/novel_agent_workbench/desktop_app.py          Tkinter desktop UI
src/novel_agent_workbench/application_service.py  application-service layer between UI and backend workflows
src/novel_agent_workbench/cli.py                  backend CLI entrypoint
src/novel_agent_workbench/providers.py            model-provider adapter layer
src/novel_agent_workbench/storage.py              local project storage, checkpoints, and registry
tests/                                            unit tests
codex_docs/                                       architecture notes, interface contracts, and operating constraints
```

Recommended first checks:

```cmd
SETUP_ENV.bat
py -3.10 -m unittest discover -s tests
```

When adding real model-provider features, keep four boundaries intact: explicit user-triggered actions, metadata-only audit records, no plaintext secrets in logs, and no automatic draft-to-confirmed promotion.

### Operator docs

```text
codex_docs\CLI_QUICKSTART.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
codex_docs\IMPORTANT_OPEN_ISSUES.md
```

### Do not upload

Do not upload the following materials to GitHub:

- `.venv/`, build outputs, or coverage outputs.
- Local runtime writing projects, draft manuscript text, or confirmed manuscript text.
- API keys, tokens, endpoint secrets, or plaintext secret values.
- Private settings, private corpora, or unauthorized text materials.

### License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the root `LICENSE` file for details.

AGPL-3.0 is a strong copyleft license, especially relevant for WebUI or network-service software. If a modified version is made available to users over a network, the corresponding modified source code usually needs to be offered to those remote users.
