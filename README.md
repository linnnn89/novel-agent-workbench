# 小说创作工作台 / Novel Agent Workbench

面向网文和长篇小说作者的 **Windows 本地 AI 写作台**。  
A local-first Windows desktop workbench for long-form fiction.

草稿只是候选，必须你亲自点「确认稿件」才会成为正文。数据默认留在本机，模型也只有你点了才会联网。

Drafts stay candidates until you confirm them. Projects stay on your machine. The model is called only when you click.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

## 它能帮你做什么

- **一本一本管作品**：大纲、人物、世界观、章节、草稿、确认稿都在同一棵树里。
- **写完一章再确认**：生成、重写、精修都先落成新版本，不会悄悄覆盖已确认正文。
- **AI 审稿后再改**：先看意见，再按审稿精修；也可以自己改，软件会自动保存。
- **带着前文继续写**：记忆库、资料和前文章节会在生成前按预算组装。
- **自己选模型**：硅基流动、DeepSeek、Chutes、OpenRouter、OpenAI 兼容接口，或本地 LM Studio / Ollama。
- **现代桌面界面**：三栏工作台，圆角磨砂面板，可改字体、字号和浅色/深色。

它不是自动写完整本书的 Agent。人决定哪一版成为正文。

## 日常写法

```text
建作品 → 写大纲 / 人物 / 世界观
      → 生成或手写章节草稿
      → AI 审稿或按意见精修
      → 对比版本，确认这一章
      → 导出 TXT
```

右键作品或章节还能删除、看生成上下文、打开项目专属设置。确认到一定章数后，可以生成记忆库摘要。

## 在 Windows 上使用

需要 Windows 10/11，以及 Python 3.10+。

```cmd
git clone https://github.com/linnnn89/novel-agent-workbench.git
cd novel-agent-workbench
BUILD_NovelAgentWorkbench.bat
```

打好后打开：

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

作品、设置和 API Key 在同目录的 `用户数据` 里。以后再打包只会换 EXE，不会清掉这些数据。

第一次用：先开「模型设置」填接口和 Key，再「生成新章节」。保存设置本身不会联网。

## 从源码运行

```cmd
SETUP_ENV.bat
START_ModernUI.cmd
```

默认是现代界面。没有 `pywebview` 时会回到经典 Tk 窗口。

## 模型调用边界

支持 OpenAI 兼容云端、硅基流动、DeepSeek、Chutes、OpenRouter、本地兼容端口，以及不联网的离线测试。

只有这些动作会在你点击后访问模型：生成草稿、AI 审稿、精修、刷新模型目录、生成或压缩记忆。打开软件、改设置、改正文都不会自动扣额度。

## 给开发者

```text
src/novel_agent_workbench/
├── modern_desktop.py      现代界面宿主
├── modern_ui/             工作台和设置页
├── desktop_app.py         经典界面（回退）
├── application_service.py 业务门面
├── storage.py             本地项目与可恢复写入
└── providers.py           模型适配与调用策略
```

更细的契约在 [`codex_docs/`](codex_docs/)。当前交接见 [`docs/handoff.md`](docs/handoff.md)。

请不要把 `dist/`、`.venv/`、`用户数据`、密钥和正文提交进 Git。

## 许可

[AGPL-3.0](LICENSE)
