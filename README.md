# 小说创作工作台

Novel Agent Workbench

写长篇的时候，我不太想把整本书交给网上的编辑器，也不想让模型自己决定哪一段算数。所以做成了这个 Windows 软件：书在你电脑里，AI 只在你点按钮的时候出手。

I made this for writing novels on Windows. The book stays on your machine. The model only runs when you press a button.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

## 这个软件干什么

一本书的大纲、人物、世界观、章节和各版草稿，都放在同一个窗口里。左边选章节，中间改稿，右边看设定。

生成出来的是草稿，不是定稿。你点「确认稿件」之前，正文不会被换掉。改一改、重写一版、按审稿意见精修，都是另存新版本，旧的还在。

可以先让模型审一稿，再按它的意见改。也可以自己写，软件会自动存。

生成下一章时，会把记忆库、设定和前面几章按篇幅拼进去，免得写着写着人设丢了。

模型你自己接。硅基流动、DeepSeek、Chutes、OpenRouter、常见的 OpenAI 兼容接口，或者本机 LM Studio / Ollama，都可以。

It's a three-pane desktop app: project tree, manuscript, notes. New generations land as drafts. Confirmed chapters don't get overwritten unless you say so. You can review with a model, rewrite, or just type. Plug in whatever OpenAI-compatible API you already use, including a local one.

## 大概怎么写

建一个作品，把大纲和人物先丢进去，然后生成或手写一章。不满意就重写或精修。定了就确认。整本差不多了，导出 TXT。

作品或章节上可以右键。删东西、看这次生成会带上哪些资料、改这一本的专属设置，都在那儿。

Typical path: new project → notes and characters → draft a chapter → review or rewrite → confirm → export as TXT.

## 怎么跑起来

Windows 10 或 11，装好 Python 3.10 以上。

```cmd
git clone https://github.com/linnnn89/novel-agent-workbench.git
cd novel-agent-workbench
BUILD_NovelAgentWorkbench.bat
```

打完去这个文件：

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

你的书和 Key 在旁边的 `用户数据` 里。以后再打包，只会换程序，不会动这份数据。

第一次打开：先到「模型设置」填接口和 Key，再建作品，点「生成新章节」。光保存设置是不会联网的。

If you want to run the source instead of the EXE:

```cmd
SETUP_ENV.bat
START_ModernUI.cmd
```

没装 `pywebview` 的话，会退回一套老的 Tk 界面。能用，就是不好看。

## 什么时候会花钱

打开软件、改稿、存设置，都不会打模型。

会打模型的只有这些，而且都要你亲手点：生成草稿、AI 审稿、按审稿精修、刷新模型列表、生成或压缩记忆库。

Opening the app and editing text is free. You get billed only when you click generate, review, refine, refresh the model list, or rebuild the memory bank.

## 开发

```text
src/novel_agent_workbench/
├── modern_desktop.py
├── modern_ui/
├── desktop_app.py          older Tk UI
├── application_service.py
├── storage.py
└── providers.py
```

更细的约定在 [`codex_docs/`](codex_docs/)。

`dist/`、`.venv/`、`用户数据`、密钥和小说正文都不要提交。

## 许可

[AGPL-3.0](LICENSE)
