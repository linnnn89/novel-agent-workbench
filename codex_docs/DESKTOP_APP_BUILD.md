# Desktop App Build

Date: 2026-05-30, Asia/Shanghai.

## Entry Point

Desktop source:

```text
src/novel_agent_workbench/desktop_app.py
```

PyInstaller launcher:

```text
packaging/desktop_launcher.py
```

Built executable:

```text
dist/NovelAgentWorkbench/NovelAgentWorkbench.exe
```

Convenience launcher:

```text
START_NovelAgentWorkbench.cmd
```

Do not launch the EXE under `build/NovelAgentWorkbench/`; that folder is PyInstaller intermediate output and can fail with Python DLL loading errors.

## Build Command

Recommended one-click build from a fresh clone:

```cmd
BUILD_NovelAgentWorkbench.bat
```

The BAT resolves all paths relative to the repository root, runs setup/build steps in the foreground console, and prints the final runnable EXE path before asking whether to launch it.

Direct PowerShell build command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows_exe.ps1
```

The scripts create/use project-local `.venv`, require Python 3.10 or newer, install `pyinstaller` and `pillow`, reuse the committed icon by default, and build the Windows EXE. Pass `-RegenerateIcon` to the PowerShell script only when intentionally updating icon assets.

## Icon

Source icon generator:

```text
scripts/generate_windows_icon.py
```

Generated assets:

```text
src/novel_agent_workbench/assets/novel_agent_workbench_icon_1024.png
src/novel_agent_workbench/assets/novel_agent_workbench.ico
```

The `.ico` contains:

```text
16, 20, 24, 32, 40, 48, 64, 128, 256 px
```

Design: blank manuscript paper with a pen, no text content.

## Safety Boundary

The desktop launcher does not call real Providers on startup or while saving settings. The user-triggered actions `测试连接` and `生成草稿` may call the configured OpenAI-compatible model service. Missing API address, model ID, or required API Key still fail before a request is sent.

This is a product boundary, not a ban on model features. Codex development sessions and automated QA must not call real LLM/API providers unless the user authorizes that specific run, but the shipped desktop software may expose clear user-triggered send/generate/test actions that call the configured provider.

## Top-Level UI Categories

The launcher uses task-first top categories. Project selection stays in the left sidebar; the top buttons represent work areas a writer would recognize:

```text
工作台
创作
资料库
模型
创作设置
定稿
帮助
```

Current submenu design:

```text
工作台: 当前项目概览 / 完整性检查 / 打开作品文件夹 / 打开项目库
创作: 章节列表 / 生成草稿 / 审稿与改写 / 已确认章节
资料库: 大纲与章节 / 世界观与人物 / 记忆库 / 参考作品与风格
模型: 模型服务 / 连接检查 / 调用记录
创作设置: 提示词与上下文 / 采样参数 / 项目库位置 / 刷新
定稿: 已确认章节 / 出稿清单 / 导出设置
帮助: 使用说明 / 开发者诊断 / 运行记录 / 关于软件
```

All top menu entries are clickable. Items backed by mature workflows open the real action dialog or metadata list. The left sidebar exposes a primary `生成草稿` action so authors do not have to open the top menu for the main writing flow. The model area now owns service connection concerns: API address, API Key, model ID, role, and connection checks. Prompt text, context size, recent-chapter count, and sampling parameters live under creation settings. The developer prepublish check is no longer presented as a normal writing action; it is available as Help -> Developer Diagnostics. The library area now supports user-triggered planning/setting entries, metadata-only reference-style import, chapter-structure import, and style-baseline creation from confirmed chapters. Planning entries expose one user-facing switch, `用于生成上下文`; internally this sets both the stored enabled flag and the active context flag so users do not have to distinguish implementation states.

The generation settings surface now owns the prompt/context design:

```text
System message:
  user-editable default system prompt, with Restore Defaults

User message:
  【用户本次要求】
  【用户提供的总纲】
  【用户提供的目前章节大纲】
  【上下文记忆】
  【世界书和人物设定】
  【写作约束】
  【往前 N 章的上文】
```

Empty sections are omitted. `N`, context token budget, temperature, top_p, top_k, min_p, max_tokens, penalties, and stream preference are saved on the same settings page. Provider calls still obey the real-generation gate; previewing the format is local and does not call a model.

## Model Connection Design

The desktop UI describes model access as a user-facing connection profile instead of provider implementation names. The current profile fields are:

```text
用途: 正文生成 / 评分校对 / 改写润色
接入方式: 离线测试 / OpenAI 兼容云端 API / Chutes API / DeepSeek API / 本地 OpenAI 兼容端口
API 地址: API Base URL, for example a cloud /v1 endpoint or a local LM Studio/Ollama-compatible endpoint
模型 ID: provider-specific model name
API Key: written only to local project secrets, never into config or logs
```

The UI no longer asks users for a secret/reference name. The app derives an internal safe name from the selected role and provider. Saving these settings does not open a network connection. Cloud providers and local ports remain behind explicit connectivity-test and real-generation authorization gates.

## Verification

```text
EXE launch smoke: process started and closed
Ran 144 tests
OK
```

2026-05-30 open-source build audit:

```text
Python floor relaxed from 3.13 to 3.10.
Build entrypoint is BUILD_NovelAgentWorkbench.bat.
Build scripts use repository-relative paths.
Final EXE path is dist\NovelAgentWorkbench\NovelAgentWorkbench.exe.
dist\NovelAgentWorkbench\用户数据 remains preserved during rebuild.
```
