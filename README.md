# Novel Agent Workbench

## 小说创作工作台

这是一个在 Windows 上写长篇小说的本地桌面工具。

它把作品目录、章节、草稿、人物设定、世界观和长期记忆放在一起。你可以从头到尾自己写，也可以只在需要的时候让模型起草、审稿或改写。模型生成的内容先留在草稿里；只有点下“确认稿件”，它才会成为正式章节。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

### 界面

新版界面分成三栏：左边是作品、章节和草稿版本，中间是正文编辑区，右边显示当前作品和生成上下文的概况。

正文会自动保存。浅色、深色、字体、字号和专注模式都可以调整。顶栏的模型名称可以直接切换当前正文模型；完整接入配置仍在「模型设置」。专注模式会收起左右两侧栏，中间栏右侧的细把手也可以单独收起资料栏。审稿完成后，如果当时没在看审稿页，「审稿」标签上会出现一个小圆点。常用操作留在编辑区附近，窗口变窄时按钮会自动换行，不会被挤出画面。

### 现在可以做什么

- 同时管理多部作品，以及每部作品的章节和草稿版本。
- 维护总纲、章节规划、人物和世界观，并决定哪些资料参与生成。
- 生成新章节，或者在现有草稿上重新生成、AI 审稿和按审稿意见精修。
- 在不同草稿之间切换。确认稿件前，旧版本和正式章节都不会被覆盖。
- 从已确认章节整理 Memory Bank，也可以手工修改、生成或压缩记忆内容。
- 在发送前预览本次会带给模型的资料和提示词结构。预览本身不会联网。
- 为正文生成、AI 审稿、AI 精修、记忆生成和记忆压缩分别指定模型。
- 写作、审稿和精修共用同一套「创作资料」前缀（稳定设定在前，本章大纲/记忆/前文在后），便于 DeepSeek 等接口命中前缀缓存。模型调用记录会显示缓存命中情况。
- 给所有作品设置通用提示词和采样参数，也可以为某一部作品单独覆盖。
- 把已确认章节按顺序导出为 TXT。

作品、章节和草稿都有右键菜单。删除的作品或章节会先进入回收站；只有清空回收站后才无法恢复。

### 写一章的大致过程

1. 新建作品，填入大纲、人物和世界观。
2. 新建章节，写下这一章的要求。
3. 先看一眼将要发送的上下文，需要时再生成草稿。
4. 自己修改，或者让模型审稿、重写、精修。
5. 选定版本后确认稿件。确认过的章节可以继续用于记忆整理和下一章生成。

软件不会替你决定哪一版算正文，也不会因为打开作品或保存设置就在后台调用模型。

### 模型怎么接

模型设置里已经预置硅基流动、Chutes 和 OpenRouter，也可以添加 DeepSeek、其他 OpenAI 兼容接口，或本机的 LM Studio、Ollama 兼容地址。正文生成可在「功能分配」里用 None / Low / High / Max 设置 DeepSeek V4 Flash 0731 的思考强度：经 OpenRouter 时发送 reasoning.effort。

保存接口和 Key 不会发起请求。以下操作可能联网并产生费用，而且都需要你自己点击：

- 生成、重写或精修草稿；
- AI 审稿；
- 生成或压缩 Memory Bank；
- 从接入商刷新模型列表。

针对 DeepSeek，程序会尽量让变化较少的项目资料保持稳定顺序，把本次指令放在后面，以增加前缀缓存复用的机会。接口返回的缓存命中和未命中数据会被保留，但实际命中率仍取决于模型、服务端缓存周期和每次发送的内容。

### 数据放在哪里

EXE 版的作品、设置和密钥保存在程序旁边的 `用户数据` 文件夹中。重新打包时，构建脚本只替换程序和运行依赖，不会删除这份目录。右侧「导入导出」可以把一部作品打包为 `.nawpkg`；作品包不含 API Key 和 `backups/`。

源码运行时，作品默认放在仓库的 `workspace_projects`。这些目录以及 `.venv`、`dist`、API Key 和小说正文都不应提交到 GitHub。

### 在 Windows 上构建

构建 EXE 需要 Windows 10/11 和 Python 3.11–3.14。首次构建需要联网安装 PyInstaller、Pillow 和 pywebview。

```cmd
git clone https://github.com/linnnn89/novel-agent-workbench.git
cd novel-agent-workbench
BUILD_NovelAgentWorkbench.bat
```

完成后运行：

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

如果只想从源码启动：

```cmd
SETUP_ENV.bat
START_ModernUI.cmd
```

源码本身支持 Python 3.10 以上。缺少 pywebview 或找不到新版界面文件时，程序会回退到经典 Tk 界面。

### 当前版本

新版界面已经覆盖从建作品、整理资料、写草稿、审稿和精修，到确认章节和导出 TXT 的日常路径。

审稿与改写总表、模型连接检查、调用记录、运行记录、出稿清单和导出设置等辅助页面，目前仍以经典 Tk 界面中的版本为主。后续迁移不会改变现有作品格式。

经典 Tk 文件目前不只是备用界面。新版桌面程序仍从 `desktop_app.py` 复用路径定位、章节排序、Memory Bank 状态、提示词预览和审稿信息格式化等公共函数；打包时也会把它一并带入。因此它仍是现阶段的运行依赖，不能直接从源码中删除。以后如果完成公共函数拆分并取消回退入口，才可以安全移除。

### 开发入口

```text
src/novel_agent_workbench/modern_desktop.py   WebView 宿主和桌面接口
src/novel_agent_workbench/modern_ui/          新版界面的 HTML、CSS 和 JavaScript
src/novel_agent_workbench/desktop_app.py      经典 Tk 界面及新版仍复用的公共函数（当前运行依赖）
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/storage.py
src/novel_agent_workbench/providers.py
```

接口约定和项目说明在 [`codex_docs/`](codex_docs/) 中。

---

## English

Novel Agent Workbench is a Windows desktop app for writing long-form fiction while keeping the project on your own machine.

It keeps outlines, characters, world-building notes, chapters, draft versions, and long-term story memory in one place. You can write on your own or ask a model to draft, review, or revise a chapter. Generated text remains a draft until you choose to confirm it.

### The desktop app

The new interface has three columns: projects and chapters on the left, the manuscript editor in the middle, and a compact project/context summary on the right. It includes autosave, light and dark themes, font controls, and a focus mode. Important actions wrap when the window becomes narrow instead of disappearing off-screen.

You can:

- manage multiple novels, chapters, and draft versions;
- maintain outlines, chapter plans, characters, world-building notes, and a Memory Bank;
- generate, rewrite, review, and refine drafts without overwriting confirmed chapters;
- preview the context and prompt structure before sending anything;
- assign separate models to drafting, review, refinement, memory generation, and memory compression;
- keep global writing settings or override them for one project;
- export confirmed chapters as a TXT file.

Deleted projects and chapters go to a local trash area first. They are removed permanently only when you empty the trash.

### Models, network calls, and local data

Built-in provider profiles include SiliconFlow, Chutes, and OpenRouter. You can also add DeepSeek, another OpenAI-compatible API, or a local LM Studio/Ollama-compatible endpoint.

Opening a project, editing text, and saving settings do not call a model. Network requests happen only after you choose an action such as generation, AI review, refinement, model-list refresh, or Memory Bank generation/compression.

For DeepSeek requests, low-change project context is kept in a stable order and the current instruction is placed later in the prompt when possible. Cache hit/miss figures returned by the service are preserved, but no fixed cache hit rate is promised.

In the packaged app, projects, settings, and secrets live in the `用户数据` folder beside the executable. Rebuilding replaces the program files, not this data folder. Use 导入导出 to pack one novel as `.nawpkg`; the package omits API keys and `backups/`.

### Build on Windows

Building the EXE requires Windows 10/11 and Python 3.11–3.14.

```cmd
git clone https://github.com/linnnn89/novel-agent-workbench.git
cd novel-agent-workbench
BUILD_NovelAgentWorkbench.bat
```

The finished app is written to:

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

To run from source instead:

```cmd
SETUP_ENV.bat
START_ModernUI.cmd
```

The source package supports Python 3.10 or newer. If pywebview is unavailable, the app falls back to the older Tk interface.

### Project status

The modern interface covers the main path from project setup and drafting through review, confirmation, and TXT export. A few secondary views—such as aggregate review history, connection diagnostics, provider call logs, and export settings—still live primarily in the classic Tk interface.

The classic Tk file is not only a backup UI. The modern desktop host still imports shared path, chapter-ordering, Memory Bank, prompt-preview, and review-formatting helpers from `desktop_app.py`, and the packaged app includes it as a dependency. It cannot be deleted safely until those helpers are separated and the fallback entry point is removed.

Technical notes and interface contracts are kept in [`codex_docs/`](codex_docs/).

## License

[GNU Affero General Public License v3.0](LICENSE)
