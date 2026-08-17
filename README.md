# Novel Agent Workbench

### 小说创作工作台

A **local-first** Windows desktop for long-form fiction.  
面向网文与长篇小说作者的 **本地优先** Windows 写作台。

Drafts stay candidates until you confirm them. Projects stay on your machine. Models are called only when you click.

草稿只是候选，必须由你确认才会成为正文。作品默认保存在本机。模型只有在你点击后才会被调用。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4.svg)](https://github.com/linnnn89/novel-agent-workbench)

---

## Features / 功能

- **One project, the full loop / 一本作品走完整流程**  
  Outline, characters, world-building, chapters, drafts, and confirmed text live in one workspace.  
  大纲、人物、世界观、章节、草稿和确认稿在同一工作台里完成。

- **Human-led confirmation / 人确认，才进正文**  
  Generate, rewrite, and refine create new versions. Nothing silently overwrites canon.  
  生成、重写、精修都先落成新版本，不会悄悄替换已确认章节。

- **Review, then revise / 先审稿，再改稿**  
  Ask the model to review a draft, then refine against that review — or edit by hand with autosave.  
  可以先让模型审稿，再按意见精修，也可以自己改。编辑会自动保存。

- **Context that travels with the book / 带着前文继续写**  
  Memory Bank, planning notes, and recent chapters are assembled on a token budget before generation.  
  记忆库、设定资料和前文章节会在生成前按预算组装。

- **Your models / 自己的模型**  
  SiliconFlow, DeepSeek, Chutes, OpenRouter, any OpenAI-compatible API, or a local LM Studio / Ollama endpoint.  
  硅基流动、DeepSeek、Chutes、OpenRouter、OpenAI 兼容接口，或本地 LM Studio / Ollama。

- **A modern Windows UI / 现代桌面界面**  
  Three-pane workbench, frosted panels, light/dark theme, and adjustable type.  
  三栏工作台、磨砂面板、浅色/深色主题，字体和字号可调。

This is not an agent that writes a novel unsupervised. You decide which version becomes the book.

这不是无人值守的自动写书程序。哪一版成为正文，由你决定。

---

## Workflow / 工作流

```text
Create a project
    → outline / characters / world
    → generate or write a chapter draft
    → review or refine
    → confirm the chapter
    → export TXT
```

```text
新建作品
    → 大纲 / 人物 / 世界观
    → 生成或手写章节草稿
    → 审稿或精修
    → 确认这一章
    → 导出 TXT
```

Right-click a project or chapter for more actions: delete, inspect generation context, or open project-specific settings.

在作品或章节上右键，可以删除、查看生成上下文，或打开项目专属设置。

---

## Quick start / 快速开始

**Requirements / 环境**

- Windows 10 or 11
- Python 3.10+
- Network only for the first build and later model calls

**Build / 构建**

```cmd
git clone https://github.com/linnnn89/novel-agent-workbench.git
cd novel-agent-workbench
BUILD_NovelAgentWorkbench.bat
```

Then open:

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

Projects, settings, and API keys live in `用户数据` next to the EXE. Rebuilding replaces only the app binaries, never that folder.

作品、设置和 API Key 保存在 EXE 同目录的 `用户数据` 里。重新打包只会替换程序文件，不会清空这份数据。

**First run / 第一次使用**

1. Open **Model Settings / 模型设置** and add an endpoint plus key.  
   打开「模型设置」，填写接口和 Key。
2. Create a project, then **Generate chapter / 生成新章节**.  
   新建作品，再点「生成新章节」。

Saving settings does not call the network.

保存设置不会联网。

---

## Run from source / 从源码运行

```cmd
SETUP_ENV.bat
START_ModernUI.cmd
```

The modern UI is the default. If `pywebview` is missing, the app falls back to the classic Tk window.

默认打开现代界面。未安装 `pywebview` 时会回到经典 Tk 窗口。

---

## Model boundary / 模型调用边界

Supported adapters: OpenAI-compatible cloud APIs, SiliconFlow, DeepSeek, Chutes, OpenRouter, local OpenAI-compatible ports, and an offline mock.

支持的接入：OpenAI 兼容云端、硅基流动、DeepSeek、Chutes、OpenRouter、本地兼容端口，以及不联网的离线测试。

These actions may call a model **after an explicit click**:

只有下列动作会在你点击后访问模型：

- generate a draft / 生成草稿
- AI review / AI 审稿
- refine from review / 按审稿精修
- refresh the model catalog / 刷新模型目录
- generate or compress Memory Bank / 生成或压缩记忆库

Opening the app, editing text, and saving settings never spend API credits on their own.

打开软件、编辑正文、保存设置都不会自动消耗额度。

---

## Development / 开发

```text
src/novel_agent_workbench/
├── modern_desktop.py       modern desktop host
├── modern_ui/              workbench and studios
├── desktop_app.py          classic Tk fallback
├── application_service.py  backend facade
├── storage.py              local projects
└── providers.py            model adapters
```

Contracts live in [`codex_docs/`](codex_docs/).

Do not commit `dist/`, `.venv/`, `用户数据`, secrets, or manuscript text.

请勿提交 `dist/`、`.venv/`、`用户数据`、密钥或正文。

---

## License / 许可

[AGPL-3.0](LICENSE)
