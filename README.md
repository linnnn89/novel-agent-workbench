# Novel Agent Workbench

## 小说创作工作台

这是一个在 Windows 上写长篇小说的本地桌面工具。

它把作品目录、章节、草稿、人物设定、世界观和长期记忆放在一起。你可以从头到尾自己写，也可以只在需要的时候让模型起草、审稿或改写。模型生成的内容先留在草稿里；只有点下“确认稿件”，它才会成为正式章节。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

### 界面

新版界面分成三栏：左边是作品、章节和草稿版本，中间是正文编辑区，右边显示当前作品和生成上下文的概况。

正文会自动保存。浅色、深色、字体、字号和专注模式都可以调整。顶栏的模型名称可以直接切换当前正文模型；完整接入配置仍在「模型设置」。专注模式会收起左右两侧栏，中间栏右侧的细把手也可以单独收起资料栏。审稿完成后，如果当时没在看审稿页，「审稿」标签上会出现一个小圆点。常用操作留在编辑区附近，窗口变窄时按钮会自动换行，不会被挤出画面。

新版界面的记忆、大纲、人物与世界观、创作设置、接入商和功能分配页会显示保存状态。修改后关闭页面、切换资料或作品、退出程序时，可以选择「保存并继续」「放弃修改」「返回编辑」；保存失败会留在原页。大纲和资料页把正文与保存按钮放在主要区域，章节范围等属性收进可展开的区域。

保存或恢复创作设置、刷新模型目录、从磁盘重载记忆时，当前编辑区和标签页会暂时锁定，避免返回结果覆盖等待期间的新输入。完成或失败后恢复编辑；刷新模型期间仍可使用「停止任务」。

### 现在可以做什么

- 同时管理多部作品，以及每部作品的章节和草稿版本。
- 维护总纲、章节规划、人物和世界观，并决定哪些资料参与生成。
- 生成新章节，或者在现有草稿上重新生成、AI 审稿和按审稿意见精修。
- 在不同草稿之间切换。确认稿件前，旧版本和正式章节都不会被覆盖。
- 从已确认章节整理 Memory Bank，也可以手工修改、生成或压缩记忆内容。
- 在发送前预览本次会带给模型的资料和提示词结构。预览本身不会联网。
- 为正文生成、AI 审稿、AI 精修、记忆生成和记忆压缩分别指定模型。
- 写作、审稿和精修共享按固定顺序排列的「创作资料」块（稳定设定在前，本章大纲/记忆/前文在后）。各自的系统提示词不同，实际是否命中前缀缓存以模型调用记录为准。
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

自动带入的前文按章节编号排序，只选目标章节之前最近的 N 章。例如补写第 2 章时不会带入第 3 章。自定义章节编号需要以数字结尾；无法判断顺序时会提示改编号或关闭自动带入前文。

### 模型怎么接

模型设置里已经预置硅基流动、Chutes 和 OpenRouter，也可以添加 DeepSeek、其他 OpenAI 兼容接口，或本机的 LM Studio、Ollama 兼容地址。正文生成与 AI 精修在「功能分配」里共用 None / Low / High / Max 思考控制，支持 DeepSeek Flash / Pro 动态名称和 V4 起的版本名称，不再限定 0731。直连接口发送 `thinking` 和 `reasoning_effort`，OpenRouter / Chutes 发送 `reasoning`；硅基流动使用 `enable_thinking`，只控制开关。新模型名称或接口不兼容时，可在接入商设置中手工指定思考控制接口，或选择不发送开关。未来接口是否兼容仍需以接入商文档为准。

保存接口和 Key 不会发起请求。以下操作可能联网并产生费用，而且都需要你自己点击：

- 生成、重写或精修草稿；
- AI 审稿；
- 生成或压缩 Memory Bank；
- 从接入商刷新模型列表。

针对 DeepSeek，程序会尽量让变化较少的项目资料保持稳定顺序，把本次指令放在后面，以增加前缀缓存复用的机会。接口返回的缓存命中和未命中数据会被保留，但实际命中率仍取决于模型、服务端缓存周期和每次发送的内容。

上下文默认预算为 131072 tokens。已有作品的明确设置保留，可在「创作设置 → 采样与上下文」使用宽松预算按钮，再点击保存。程序使用固定版本 `deepseek-tokenizer==0.3.0` 在本地计算文本长度；下载包约 1.9 MB，词表约 6.4 MB，无额外运行依赖，不会下载模型权重。它使用 DeepSeek V4 词表，动态名称、未来模型及消息格式仍有估算误差；其他模型或缺少 tokenizer 时使用中文保守估算。最终以 API 用量为准。

已启用的资料、记忆银行和按设置选入的前文章节会完整组装，不会为了满足 input 预算而自动删减。发送前检查会把系统提示词、本次要求、审稿或精修所需正文一起计入输入，并为输出预留空间。超出软件预算时先停止发送，在专门提示区列出估算用量，并提供提高本作品预算、减少带入的前文章数、手工精简记忆三个入口。提高预算需点击保存；减少前文章数不会删除本地章节；记忆只有手工编辑并保存正文才会缩短，调整目标 tokens 不会自动改写它。保存并关闭编辑页后，可通过稿纸上方的「查看发送预算提示」重新检查并发送原请求，无需重输写作要求。模型硬性容量不能通过提高软件预算突破；模型目录未提供容量时，只能检查软件预算，实际仍以服务商限制为准。

记忆银行生成或压缩时，页面顶部显示等待计时和接口返回的思考文本，可折叠查看，也可点击「停止任务」结束等待。等待期间正文、章节勾选和参数暂时锁定；生成结果保存时按实际发送的章节记录来源，压缩不会把新勾选章节记为已处理。部分模型不返回思考文本；正文仍在记忆编辑区流式显示。手动上滚阅读、折叠或关闭思考栏后，计时和后续输出不会打断该操作；滚回底部后恢复跟随新内容。

审稿失败或停止后，右侧保留明确状态和已返回的片段，供阅读或复制。达到输出上限的审稿意见会标注“不完整”，重新打开对应正文时仍可查看；只有与当前正文匹配的完整审稿才能用于精修。

编辑已确认章节，或用内容不同的新版本替换确认稿时，如果记忆银行涉及该章，会弹窗提醒手工核对。提醒不会改写、禁用或重新生成记忆。同一作品、同一章节每次启动最多提醒一次，避免自动保存反复打断写作；只有措辞润色时可以忽略。

新版界面支持停止正文、审稿、记忆和模型目录任务。已返回结果进入本地保存阶段后，会先完成保存；网络阶段停止则保留原稿，已显示的正文片段供手工复制。停止本地请求不保证上游立即停止计算或计费。空正文不会创建草稿；达到输出上限的有效正文会保存为不完整候选，重新打开仍有提示。保存失败会阻止切换、重写、确认和导出等后续动作。没有正文变化的保存会跳过，避免生成无意义备份。

调用记录保留服务商实际返回的缓存、思考 token 和费用字段，缺失字段不补成零。记录另含输入估算、耗时和系统提示词摘要，方便比较同一功能的缓存效果。写作、审稿、精修各自的提示词职责保持不变；共享资料顺序并不保证跨功能命中缓存。

### 数据放在哪里

EXE 版的作品、设置和密钥保存在程序旁边的 `用户数据` 文件夹中。重新打包时，构建脚本只替换程序和运行依赖，不会删除这份目录。右侧「导入导出」可以把一部作品打包为 `.nawpkg`；作品包不含 API Key 和 `backups/`。

「项目库位置」会先将当前正文保存到原项目库，再切换目录并清空旧编辑状态。保存请求绑定原目录，避免两个库里同名的作品互相覆盖。成功切换的位置会记在默认数据目录旁的 `desktop_settings.local.json` 中，下次启动继续使用；该目录不可用时使用默认项目库。

左侧「历史备份」列出最近 200 个完整作品检查点，包括时间、触发原因和作品名称。选中后会校验全部文件，再允许恢复为带「恢复副本」名称的新作品，包含备份时的草稿、确认章节、记忆和作品设置，当前作品不会被覆盖。独立密钥文件和旧配置中的 API Key 不会复制。恢复以实际保留的完整检查点为准；清空回收站后，已删除作品中的备份也会被清理。

源码运行时，作品默认放在仓库的 `workspace_projects`。这些目录以及 `.venv`、`dist`、API Key 和小说正文都不应提交到 GitHub。

### 在 Windows 上构建

构建 EXE 需要 Windows 10/11 和 Python 3.11–3.14。首次构建需要联网安装 PyInstaller、Pillow、pywebview 和上述小型 tokenizer。

```cmd
git clone https://github.com/linnnn89/novel-agent-workbench.git
cd novel-agent-workbench
BUILD_NovelAgentWorkbench.bat
```

完成后运行：

```text
dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

构建会先在 Windows 桌面会话中运行 `scripts/verify_feedback_ui.py` 的 3 组关键窗口回归，覆盖记忆保存保护、思考栏交互和审稿结束状态，使用临时项目与模拟输出，不调用模型；失败时立即停止，保留现有程序。通过后在独立目录构建并核对文件，再替换正式程序。旧 EXE 和运行依赖保存在 `old/program-backup-*`，替换失败会尝试还原并核对旧程序；运行中的程序需先关闭。「关于」显示构建时间、代码提交和当前项目库位置。旧程序备份会占用磁盘空间，确认新版可用后可手工整理。已有构建依赖时可用 `powershell -File scripts/build_windows_exe.ps1 -SkipInstall` 跳过安装。

如果只想从源码启动：

```cmd
SETUP_ENV.bat
START_ModernUI.cmd
```

源码本身支持 Python 3.10 以上。缺少 pywebview 或找不到新版界面文件时，程序会回退到经典 Tk 界面。

### 当前版本

新版界面已经覆盖从建作品、整理资料、写草稿、审稿和精修，到确认章节和导出 TXT 的日常路径。

审稿与改写总表、模型连接检查、调用记录、运行记录、出稿清单和导出设置等辅助页面，目前仍以经典 Tk 界面中的版本为主。后续迁移不会改变现有作品格式。

新版桌面程序从 `ui_presenters.py` 复用路径定位、章节排序、Memory Bank 状态、提示词预览和审稿信息格式化。经典 Tk 界面仍作为备用入口保留；其保存保护、记忆提醒和底层输出检查也已更新，停止按钮目前位于新版界面。

### 开发入口

```text
src/novel_agent_workbench/modern_desktop.py   WebView 宿主和桌面接口
src/novel_agent_workbench/modern_ui/          新版界面的 HTML、CSS 和 JavaScript
src/novel_agent_workbench/desktop_app.py      经典 Tk 备用界面
src/novel_agent_workbench/ui_presenters.py    两种界面共用的显示格式
src/novel_agent_workbench/token_budget.py     本地 token 估算及完整输入预算
src/novel_agent_workbench/task_control.py     本地任务停止和网络中断
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/storage.py
src/novel_agent_workbench/providers.py
```

接口约定和项目说明在 [`codex_docs/`](codex_docs/) 中。

在 Windows 桌面会话中运行 `.venv\Scripts\python.exe scripts\verify_desktop_iterations.py`，可用独立临时项目库验证保存提示、切库、备份恢复和原生退出；不会调用模型。结果保存在 `work/desktop-iteration-check/ui_results.json`。

`.venv\Scripts\python.exe scripts\verify_studio_safety.py` 用 3 个真实窗口回归用例检查设置保存、模型刷新和记忆重载期间的编辑保护，使用受控本地延迟模拟慢操作，不调用模型。结果保存在 `work/studio-safety-check/green.json`；修复前可加 `--red` 单独记录失败基线。

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

Shared display helpers live in `ui_presenters.py`; the classic Tk interface remains a fallback. The modern UI supports cancellation, while both interfaces use the same save integrity checks, incomplete-output markers, and manual Memory Bank reminders. New defaults allow 131072 input tokens, using a small local DeepSeek V4 tokenizer with conservative fallbacks. Existing explicit budgets are retained. Thinking controls recognize DeepSeek model families and can be overridden per provider; future API compatibility still needs verification.

Enabled context is always assembled in full. If the complete input exceeds the configured budget, the request stops before dispatch; the modern UI offers a dedicated panel to raise the project budget, reduce the selected prior chapters, or manually edit Memory Bank. Changes must be saved before retrying the original request. Increasing the software budget cannot override a known model context limit, including reserved output tokens.

Technical notes and interface contracts are kept in [`codex_docs/`](codex_docs/).

## License

[GNU Affero General Public License v3.0](LICENSE)
