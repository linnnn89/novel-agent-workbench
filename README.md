# Novel Agent Workbench / 小说创作工作台

[中文说明](#中文说明) | [English](#english)

---

## 中文说明

Novel Agent Workbench（小说创作工作台）是一个面向网文作者、长篇小说作者和系列故事创作者的本地优先 AI 创作工具。

如果你的故事会持续几十章、需要反复修改，或者不想每次打开聊天框都重新解释人物和世界观，这个项目就是为这种创作过程准备的：它把大纲、人物、世界观、章节计划、长期记忆、草稿、审稿和确认稿放在同一个可恢复的桌面工作台里。

它不是替你“一键写完一本书”的自动写作服务，而是把 AI 放进一个作者仍然掌握节奏和决定权的工作流中。草稿先作为候选保存，审稿和重写是独立步骤，只有你明确确认后，内容才会进入已确认章节。

### 适合谁

- 正在写网文、长篇小说或系列故事，希望持续管理几十章内容的作者。
- 需要同时维护人物关系、世界观、章节目标和长期记忆的创作者。
- 想在本机保存项目资料，并自行选择 DeepSeek、OpenRouter、Chutes、硅基流动或其他兼容服务的用户。
- 希望把自己的写作流程、模型配置和桌面工具一起掌握在手里的开发者。

### 你可以用它完成什么

- 从总纲、节拍表、世界观和人物设定开始，建立一个可持续更新的小说项目。
- 生成章节草稿，查看 AI 审稿意见，发起精修或重新生成，并比较不同候选版本。
- 用 Memory Bank 保存跨章节的重要事实、关系和风格提醒，减少长篇创作中的上下文断裂。
- 在“模型设置”中管理 API 提供商、刷新或手工维护模型目录，并分别指定正文生成、AI 审稿、AI 精修、记忆生成和记忆压缩使用的模型。
- 在 Windows 上直接构建和运行本地桌面版，不依赖在线编辑器或托管项目空间。

### 最新能力

- **本地优先**：项目、草稿、确认稿、记忆和运行配置默认保存在本机；私人正文不会因为使用这个仓库而自动上传。
- **可恢复的创作流程**：生成、审稿、重写和确认分开进行，避免 AI 输出意外覆盖正在使用的正文。
- **新的模型设置中心**：内置硅基流动、Chutes、OpenRouter，支持自定义 OpenAI 兼容 Provider；模型目录可主动刷新、本地缓存，也可以手工添加模型。
- **面向 DeepSeek 的前缀稳定化**：低频项目资料保持稳定顺序，动态指令放在请求末端，并保留缓存命中/未命中统计，便于长会话观察实际效果。
- **适配长篇写作的桌面界面**：三栏工作区、紧凑上下文检查器、可调整大小的模型设置窗口，以及窄窗口下仍会自动换行的关键操作按钮。

这是一个仍在持续完善的本地开源桌面项目，适合愿意自己配置模型服务、保留本地数据并参与迭代的作者和开发者。它不是托管式在线写作平台，也不会在后台自动调用模型、自动发布内容或自动把草稿变成定稿。

### 本地运行与开发者说明

下面开始是本地安装、实现边界和开发入口，主要供实际使用者与贡献者查阅；项目首页的产品定位和适用场景以上面的介绍为准。

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
- Memory Bank 总结与压缩，支持流式进度和手动保存门槛。
- 上下文包预览、最终提示词渲染 dry-run、Provider 执行 gate、runbook、authorization 和 preflight。
- Model Settings v2：Provider 档案、模型目录刷新与缓存、手工模型，以及正文、审稿、精修和记忆功能的模型分配。
- OpenAI-compatible Provider、DeepSeek、硅基流动、Chutes、OpenRouter、本地 OpenAI-compatible endpoint 和 mock Provider 适配框架。
- 面向 DeepSeek 的稳定请求前缀排序和缓存命中/未命中统计保留。
- Provider 调用审计、smoke test、安全检查、prepublish-check 和 project-health。
- Windows Tkinter 桌面启动器、可调整大小的设置窗口和 PyInstaller 打包脚本。

### 当前实现状态

当前仓库已经完成从本地项目存储、Provider 配置、安全审计、草稿生成、审稿、修订、Memory Bank、上下文装配、语料分析、人工重写、最终 Provider gate，到 Windows 桌面启动器的多阶段 MVP 实现。

最新 README 不逐条列出所有内部 MVP 日志；详细开发过程可参考 `codex_docs/`、提交记录和测试用例。当前重点状态是：

- 最终 Provider 路径已经形成 gate -> runbook -> authorization -> preflight -> real execution -> postcheck 的显式链路。
- Provider 输出会经过 sanitizer，以避免 reasoning markup 等不应保存的内容进入草稿。
- Smoke-test drafts 仅保留为证据，不允许提升为确认稿。
- 上传发布前由 `.gitignore`、`prepublish-check` 和 `project-health` 共同保护。
- 桌面启动器保持 local-first，不应在启动时或隐藏后台流程中调用模型。
- 模型设置中心已经支持 Provider 档案、模型目录缓存、手工模型和按功能分配模型；旧版角色配置会迁移到新结构。
- 针对 DeepSeek 的生成请求已经采用稳定资料优先、动态内容靠后的顺序，并保留服务端缓存统计；项目不承诺固定缓存命中率，实际结果取决于模型、缓存生命周期和请求内容。
- 最新桌面界面采用统一的冷灰/白色卡片、靛蓝主操作和绿色确认操作；右侧检查器保持紧凑，低频模型配置收纳在顶栏“模型设置”。

### 桌面界面与主要操作

当前 Windows 桌面版围绕长篇创作的高频路径组织：

- 左栏：搜索作品、创建作品、生成新章节，并以树形结构浏览章节与草稿版本。
- 中栏：编辑当前草稿，切换上一版/下一版，并直接使用“重新生成（随机）”“根据审稿意见精修”“AI审稿”和“确认稿件”。
- 右栏：只保留本章目标、作品概览和生成上下文入口，减少对正文宽度的占用。
- 顶栏：显示当前作品、模型配置、本地保存和字数状态；低频模型服务配置通过“模型设置”打开。
- 弹窗：生成草稿、模型服务、大纲、记忆库和生成设置等窗口使用统一的标题、表单与操作区样式，并适配 Windows 高 DPI 缩放。

界面美化只调整呈现和入口层级；API Key 的本地保存、掩码、读取和写入逻辑保持不变。

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
.venv\Scripts\python.exe -m unittest discover -s tests
```

最近记录的结果：

```text
Ran 32 tests
OK
```

### 安装与运行（Windows）

最低环境：

- Windows 10/11。
- Python 3.11-3.14 用于构建 Windows EXE，并建议安装时勾选 `Add python.exe to PATH`。也可以使用 Windows Python Launcher，即 `py` 命令。
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
.venv\Scripts\python.exe -m novel_agent_workbench.cli --projects-root <repo-root>\workspace_projects smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
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
.venv\Scripts\python.exe -m unittest discover -s tests
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

Novel Agent Workbench is a local-first AI writing workspace for web-novel authors, long-form novelists, and serial-fiction creators.

If your story runs for dozens of chapters, changes through repeated revision, or should not depend on re-explaining every character and world-building detail in a new chat, this project is designed for that process. It brings outlines, characters, world-building, chapter plans, long-term memory, drafts, reviews, and confirmed chapters into one recoverable desktop workspace.

It is not an automatic “write a whole book for me” service. Instead, it puts AI inside a workflow where the author keeps control: drafts remain candidates, review and rewriting are separate actions, and only an explicit confirmation promotes text to a confirmed chapter.

### Who it is for

- Authors writing web novels, long-form fiction, or serial stories across many chapters.
- Creators who need characters, world-building, chapter goals, and long-term story memory to stay connected.
- Users who want local project data and the freedom to choose DeepSeek, OpenRouter, Chutes, SiliconFlow, or another compatible service.
- Developers who want to own and adapt both their writing workflow and their model configuration.

### What you can do with it

- Start from outlines, beat sheets, world-building, and character notes, then keep the project evolving chapter by chapter.
- Generate drafts, review them with AI, request refinement or regeneration, and compare candidate versions before confirming one.
- Use the Memory Bank for cross-chapter facts, relationships, and style reminders so long-form context does not disappear between sessions.
- Manage providers in Model Settings, refresh or manually maintain model catalogs, and assign different models to drafting, review, refinement, memory generation, and memory compression.
- Build and run a local Windows desktop version without relying on a hosted editor or hosted project storage.

### Latest capabilities

- **Local-first by default**: projects, drafts, confirmed chapters, memory, and runtime configuration stay on the local machine; private manuscript text is not uploaded by this repository automatically.
- **Recoverable writing workflow**: generation, review, rewriting, and confirmation are separate steps, so an AI response does not silently replace the text you are working on.
- **Model Settings v2**: built-in SiliconFlow, Chutes, and OpenRouter profiles, custom OpenAI-compatible providers, refreshable and locally cached model catalogs, manual model entries, and per-feature model assignment.
- **DeepSeek prefix stability work**: low-change project context is kept in a stable order, dynamic instructions are placed near the end, and cache hit/miss usage is preserved for observing real service behavior.
- **Desktop workflow for long-form writing**: a three-column workspace, compact context inspector, resizable model settings, and responsive action buttons that remain available in narrow windows.

This is an actively evolving open-source desktop project for authors and developers who are comfortable configuring their own model services, keeping data local, and shaping the tool over time. It is not a hosted writing platform, and it does not silently call models, publish content, or turn drafts into final chapters in the background.

### Local use and contributor notes

The sections below cover local installation, implementation boundaries, and development entry points for users and contributors. The visitor-facing product positioning is the introduction above.

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
- Streaming Memory Bank generation and compression with an explicit manual save gate.
- Context package preview, final prompt render dry-run, Provider execution gate, runbook, authorization, and preflight checks.
- Model Settings v2 with provider profiles, refreshable and cached model catalogs, manual models, and per-feature assignments.
- Adapter framework for OpenAI-compatible providers, DeepSeek, SiliconFlow, Chutes, OpenRouter, local OpenAI-compatible endpoints, and a deterministic mock provider.
- DeepSeek-oriented stable prefix ordering with preserved cache hit/miss usage counters.
- Provider call audit, smoke tests, safety checks, prepublish checks, and project health summaries.
- Windows Tkinter desktop launcher, resizable settings windows, and PyInstaller build script.

### Current status

The repository has implemented a multi-stage MVP from local project storage, Provider configuration, safety audit, draft generation, review, revision, Memory Bank, context assembly, corpus profiling, manual rewrite workflow, final Provider gate, and Windows desktop launcher.

This README no longer lists every internal MVP item line by line. For detailed development history, see `codex_docs/`, commit history, and the test suite. The current high-level status is:

- The final Provider path now has an explicit chain: gate -> runbook -> authorization -> preflight -> real execution -> postcheck.
- Provider output is passed through a sanitizer to prevent reasoning markup or other non-draft material from being saved into drafts.
- Smoke-test drafts are retained as evidence only and must not be promoted to confirmed chapters.
- Upload readiness is guarded by `.gitignore`, `prepublish-check`, and `project-health`.
- The desktop launcher is local-first and should not call models on startup or through hidden background flows.
- Model Settings now supports provider profiles, cached and manual model catalogs, per-feature model assignment, and migration from the previous role-based configuration.
- DeepSeek-oriented generation requests keep stable project context ahead of dynamic content and preserve server-reported cache usage; no fixed hit-rate guarantee is implied.
- The latest desktop UI uses a consistent cool-gray/white surface system, indigo primary actions, green confirmation actions, a compact inspector, and a low-frequency model configuration entry in the top bar.

### Desktop UI and primary actions

The Windows desktop app is organized around the most frequent long-form writing workflow:

- Left pane: search and create projects, generate chapters, and browse chapters and draft versions in a tree.
- Center pane: edit the active draft, move between versions, and directly access random regeneration, review-driven refinement, AI review, and confirmed-draft promotion.
- Right pane: keep only chapter goals, project summary, and generation-context shortcuts so manuscript editing receives most of the window width.
- Top bar: show the active project, model configuration, local-save state, and character count; infrequent provider configuration opens through `Model Settings`.
- Dialogs: draft generation, model service, planning, Memory Bank, and generation settings share a consistent header, form, and action-area treatment with Windows high-DPI support.

The visual refresh changes presentation and action placement only. API-key storage, masking, reading, and writing behavior remains unchanged.

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
.venv\Scripts\python.exe -m unittest discover -s tests
```

Latest recorded result:

```text
Ran 32 tests
OK
```

### Installation and Running (Windows)

Minimum environment:

- Windows 10/11.
- Python 3.11-3.14 for building the Windows EXE. Select `Add python.exe to PATH` during installation when possible. The Windows Python Launcher, `py`, is also supported.
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
.venv\Scripts\python.exe -m novel_agent_workbench.cli --projects-root <repo-root>\workspace_projects smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
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
.venv\Scripts\python.exe -m unittest discover -s tests
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
