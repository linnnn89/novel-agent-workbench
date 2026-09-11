# Codex Worklog

## 2026-08-30（北京时间）

- 目标：修复项目级生成设置被全局设置覆盖，以及现代界面关闭时最后编辑可能未落盘的问题。
- 修复：运行时模型配置保留有效项目生成设置；自动保存改为串行队列；原生窗口关闭会等待最终保存成功，保存失败或正在生成时保持窗口打开。
- 回归证据：修复前，项目 `max_tokens=111` 在实际 AI 审稿链中被全局值 `222` 覆盖；旧保存未完成时，新保存会并发发出。两项均以失败测试复现后修复。
- 保持不变：API Key 继续可选以兼容 LM Studio；已确认章节继续允许编辑。
- 验证：5 个 Python 行为测试和 3 个 JavaScript 行为测试通过；Python `compileall`、JavaScript 语法检查、CLI `--help`、`git diff --check` 通过；本地 pywebview 6.2.1 的关闭事件与 Promise 回调接口存在。
- 限制：未执行真实模型调用、真实窗口自动化或 EXE 重建。
- 本次基线还包含：记忆更新/压缩提示词可配置并可恢复默认、规划资料空状态引导、OpenAI-compatible/本地 LM Studio 的可选 Key 提示与校验一致化。
- 发布前检查：内置 `prepublish-check` 返回 0 个 blocker、0 个 warning；候选文件未发现已知 Token 前缀、Bearer 字面量或本机绝对用户路径。
- 拆分原则：每阶段先检索成熟 GitHub 项目，只提取已经存在且职责稳定的边界；保留旧导入路径作为兼容层；正向行为测试和 TDD 反向边界测试全部通过后才进入下一阶段。

### 阶段 0：拆分基线

- GitHub 参考：CPython IDLE 的 [`idlelib/README.txt`](https://github.com/python/cpython/blob/main/Lib/idlelib/README.txt) 按编辑器、配置、对话框等具体职责拆模块，但 [`editor.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/editor.py) 仍保留窗口编排；Thonny 的[内置插件示例](https://github.com/thonny/thonny/blob/master/thonny/plugins/cells.py)把独立行为放入小模块；pywebview 的[窗口实现](https://github.com/r0x0r/pywebview/blob/master/webview/window.py)把事件和 JS API 作为显式边界。只采用“小职责模块 + 薄入口”，不引入插件框架、依赖注入容器或新依赖。
- 当前规模：`desktop_app.py` 6,423 行；`WorkbenchDesktopApp` 4,914 行、121 个方法。
- 冷导入中位数（5 次独立进程）：`application_service` 398.19 ms / 9.45 MiB / 不加载 Tk；`desktop_app` 422.88 ms / 11.30 MiB / 加载 Tk；`modern_desktop` 427.12 ms / 11.46 MiB / 加载 Tk。
- 特征测试：新增 5 个公开行为测试，覆盖草稿排序/标签、确认与计划章节可见性、记忆进度、数值解析的非法输入、空失败章节的重试编号；正向与反向边界均通过。
- 阶段结论：第一步只解除现代 UI 对经典 Tk 入口的纯展示函数依赖；预期收益是降低耦合与导入内存，不承诺显著降低运行期峰值内存。大型窗口方法暂不移动。

### 阶段 1：共享展示函数叶模块

- GitHub 复核：CPython IDLE 的 [`run.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/run.py) 在测试场景刻意避免 Tk 初始化副作用；[`idlelib/README.txt`](https://github.com/python/cpython/blob/main/Lib/idlelib/README.txt) 同时警告循环导入并允许有理由的延迟导入；pywebview 的[窗口 API](https://github.com/r0x0r/pywebview/blob/master/docs/api/README.md)保持显式 JS API/事件边界。本阶段据此采用单向依赖 `desktop_app/modern_desktop -> ui_presenters`。
- TDD 红灯：新增独立进程测试，证明修改前导入 `modern_desktop` 会把 `tkinter` 加入 `sys.modules`。
- 实现：新增无 Tk 的 `ui_presenters.py`，迁移 47 个共享函数及两组展示常量；现代入口直接导入新模块；经典入口保留原有函数名并重导出同一函数对象。只添加模块职责、兼容桥和独立进程原因等必要注释。
- 等价性核对：46/47 个迁移函数与合并前版本 AST 完全一致；唯一因列表写法收敛而产生 AST 差异的 `format_review_details`，用空结果、普通评分、截断且含结构化/文本问题 3 组输入逐字比较通过。
- 正向/反向验证：12 个 Python 测试和 3 个 JavaScript 测试通过；覆盖 29 个原公开名称的经典入口兼容性、非法数值输入、确认章节可见性和 Tk 导入边界。
- 冷导入中位数（5 次独立进程）：`modern_desktop` 从 427.12 ms / 11.46 MiB / 加载 Tk，变为 391.05 ms / 9.59 MiB / 不加载 Tk；峰值下降约 1.87 MiB（约 16%）。经典 Tk 入口仍为 420.43 ms / 11.32 MiB，符合预期。
- 文件结果：`desktop_app.py` 从 6,423 行降至 5,662 行；主窗口类仍是 4,914 行、121 个方法，说明本阶段没有伪装成类拆分。

### 阶段 2：经典 UI 主题模块

- GitHub 复核：Thonny 的 [`clean_ui_themes.py`](https://github.com/thonny/thonny/blob/master/thonny/plugins/clean_ui_themes.py) 与[主题说明](https://github.com/thonny/thonny/wiki/Theming)把 ttk 主题定义独立于 Workbench；CPython IDLE 的 [`config.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/config.py)集中管理主题颜色，编辑窗口只消费配置。这里仅采用“主题令牌 + 单一应用函数”，不引入动态主题注册或插件系统。
- TDD 红灯：先新增主题应用和反向依赖测试，生产模块尚不存在时两项均按预期失败。
- 实现：新增 `classic_ui_theme.py`，迁移全部颜色/字体令牌和 ttk/Tk option 配置；经典窗口的 `_configure_style()` 保持为 3 行兼容钩子。主题模块只依赖 Tk，不反向导入 `desktop_app` 或业务服务；必要注释说明了原生 Tk 控件不继承 ttk 样式的原因。
- 等价性核对：动态还原合并前 `_configure_style()`，在两个独立隐藏 Tk 解释器中比较 17 类样式的 `configure/map`、根背景和菜单 option database，全部一致；Tk 8.6.15。
- 正向/反向验证：14 个 Python 测试和 3 个 JavaScript 测试通过；真实隐藏 Tk 根窗口验证主题色、主按钮、确认按钮和 Treeview 行高；独立进程验证主题导入不加载经典桌面入口。
- 文件结果：`desktop_app.py` 5,343 行；主窗口类从 4,914 行降至 4,620 行；原 297 行主题方法缩为 3 行，方法数仍为 121，业务行为未改。

### 阶段 3：记忆库窗口纯状态边界

- GitHub 复核：CPython IDLE 的 [`configdialog.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/configdialog.py) 将配置页拆为 `FontPage`、`HighPage`、`KeysPage` 等具体职责类，而 [`editor.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/editor.py) 继续负责窗口与事件编排。本阶段只采用“先分离稳定状态变换”的原则，不照搬多页面层级或控制器框架。
- 风险审计：`show_memory_bank_window()` 拆分前约 796 行，包含 35 个直接局部函数；其中生成与压缩命令分别约 150 行和 148 行，并共同依赖线程回调、窗口生命周期及多个控件闭包。缺少真实事件自动化时直接迁移这些命令，回归风险高于当前收益，因此本阶段不动网络和线程编排。
- TDD 红灯：先新增状态模块测试；生产模块尚不存在时，3 项测试均以 `ModuleNotFoundError` 按预期失败。
- 实现：新增无 Tk 的 `memory_bank_ui_state.py`，提取章节行标签、按持久化章节顺序筛选勾选项、紧凑选择摘要和编辑器规范快照；原窗口内函数保留为薄委托，控件读取、保存和事件副作用仍由窗口编排。注释仅解释“持久化顺序”和“脏状态规范快照”等不直观约束。
- 正向/反向验证：18 个 Python 测试和 3 个 JavaScript 测试通过；覆盖正常排序与快照、未知章节丢弃、非法 token 回退、超过 5 章的摘要截断，以及独立导入不得加载 `tkinter`。Python `compileall`、JavaScript 语法检查和 `git diff --check` 通过。
- 文件结果：`desktop_app.py` 从 5,343 行降至 5,330 行；主窗口类从 4,620 行降至 4,601 行；记忆库窗口从约 796 行降至 777 行。方法数仍为 121，说明没有以增加同类方法掩盖复杂度。
- 阶段门禁结论：纯状态边界已稳定，可独立测试；线程命令拆分延后到具备窗口事件测试时再评估，避免为了文件变小而引入额外抽象。

### 阶段 4：记忆库窗口职责模块

- 回退准备：确认本地 `main` 与 `origin/main` 同为 `cc3b057`，建立本地回退分支 `backup/pre-memory-window-split-2026-08-30` 后才创建工作分支。回退点不包含本阶段任何修改。
- 爆炸半径：全仓只有经典入口 `show_memory_bank()` 调用目标窗口；现代界面、应用服务和存储层均无反向引用。目标代码对宿主只使用应用服务、子窗口、文本样式、日志、健康检查、Tk 调度和文本预览能力；主要结构风险是新模块反向导入 `desktop_app` 形成循环。
- GitHub 复核：CPython IDLE 将大型配置窗口放入独立 [`configdialog.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/configdialog.py)，[`editor.py`](https://github.com/python/cpython/blob/main/Lib/idlelib/editor.py) 保留调用入口；pywebview 的 [`window.py`](https://github.com/r0x0r/pywebview/blob/master/webview/window.py) 将同一窗口的事件和窗口状态集中在窗口对象。本阶段采用“整体迁移一个内聚窗口、调用者保留薄入口”，不把 35 个共享闭包拆成浅层模块。
- TDD 红灯：先建立真实隐藏 Tk 行为测试，要求新模块能打开现有记忆并从保存按钮写回应用服务；生产模块不存在时，以 `ModuleNotFoundError` 按预期失败。
- 实现：新增 `memory_bank_window.py`，运行时保持单向 `desktop_app -> memory_bank_window`；应用标题由调用者显式传入，避免反向导入。原 `show_memory_bank_window()` 缩为 3 行兼容入口，旧的 `wrapped_row_positions` 与 `format_memory_compression_prompt` 导入名继续重导出。注释解释循环导入门禁、标题传递、提示词归属和暂不拆散窗口闭包的理由。
- 无损核对：从回退分支直接读取拆分前源码；迁移前后的 777 行窗口主体（忽略新增接口说明和标题别名）、26 行布局算法、34 行压缩提示词 AST 均完全一致。
- 正向/反向验证：新增 4 项测试，覆盖现有正文读取与编辑保存、取消未保存关闭时窗口和文本保留、经典兼容入口、独立进程导入不得加载 `desktop_app` 以及旧辅助函数身份兼容。全套 22 个 Python 测试、3 个 JavaScript 测试、Python `compileall`、JavaScript 语法、CLI `--help` 和 `git diff --check` 通过。
- 文件结果：`desktop_app.py` 从 5,330 行降至 4,491 行；主窗口类从 4,601 行降至 3,827 行；方法数仍为 121。新模块 884 行，明确表示复杂度被按窗口职责隔离，而不是伪称已消失；主文件当前最大方法变为 404 行的生成设置窗口。
- 限制：真实隐藏 Tk 已覆盖打开、编辑、保存和取消关闭；未触发真实模型 API、流式线程完成回调或 EXE 打包。

## 2026-09-02（北京时间）

### 修复现代窗口关闭卡死

- 根因：Windows EdgeChromium 的 `closing` 事件运行在 UI 线程；旧实现直接在该事件内同步调用 `evaluate_js()`，等待 JavaScript 完成时阻塞同一 UI 线程，形成确定性死锁。pywebview 上游 issue #1699 记录了相同问题及线程化规避方案。
- 修复：关闭事件立即取消本次原生关闭，并由后台 `NovelCloseSave` 线程执行最终保存；保存成功后再销毁窗口。增加 8 秒看门狗、关闭尝试编号以及过期回调隔离，保存失败或超时时恢复编辑状态并允许重试。
- TDD 与验证：修改前线程身份回归测试按预期失败；修改后真实隐藏 EdgeChromium 窗口可在关闭请求后退出。Python 测试 38/38、JavaScript 测试 4/4、`compileall`、JavaScript 语法检查、`git diff --check` 和发布前检查均通过；未调用真实模型/API。
- 打包说明：为避免覆盖仍被无响应旧进程占用的正式 `dist`，曾尝试在独立时间戳目录构建探针；首次因资源相对路径解析失败，第二次按用户指示中止。源码修复和真实 EdgeChromium 集成测试已完成，但正式 EXE 未重建。
- 保持不变：作品数据格式、模型调用流程、供应商配置和其他功能行为未修改。

## 2026-09-10（北京时间）

### 正文生成思考开关修复与 EXE 重建

- 用户要求：正文生成默认关闭思考，修复 OpenRouter 关闭不生效，改为明确开关并重新构建 EXE。
- 修改：缺失或非法思考档位默认 none；界面显示思考模式开关，开启后选择低/高/最高，保存仍使用原 reasoning_effort 字段。已保存的合法档位保留。
- 请求：DeepSeek V4 Flash 0731 正文生成通过 OpenRouter 等兼容接口关闭时发送 reasoning.enabled=false，不再发送 effort=none；开启发送 enabled=true 与 effort。DeepSeek 官方接口继续使用 thinking.type。
- 验证：scripts/test_reasoning_switch.py 三项测试通过，覆盖默认/保存配置、两个接口四档最终 HTTP 请求体和非目标模型；JavaScript 六种初始状态及开启/选强度/关闭逻辑通过，语法与 diff 检查通过。
- 构建：复用既有环境，build_windows_exe.ps1 -SkipInstall 成功；核对 EXE 嵌入默认值与关闭代码、打包 studio.js 与源码一致。输出 dist/NovelAgentWorkbench/NovelAgentWorkbench.exe，保留用户数据和原有 ZIP。
- 反证检查：关闭强度控件时 hidden 有现有 CSS 强制隐藏支持，且控件禁用；旧项目显式保存 high 时仍开启，不静默覆盖用户配置。
- 限制：未进行付费模型调用、真实窗口视觉验收或默认个人数据库启动测试；原 ZIP 未更新，应直接运行本次 EXE。


### AI 精修完整链路重新评估及推理遗漏修复

- 范围：现代界面 refineDraft → WorkbenchBridge.refine_draft → refine_draft_from_ai_review → 上下文/审稿组装 → generate_with_provider → HTTP/SSE → save_provider_draft_version → draft_done。未调用外部模型或上传作品内容。
- 已确认根因并修复：ai_refinement 未进入正文推理设置分支。现在正文生成和 AI 精修共用现有开关，UI 明示适用范围；其余功能不变。回归测试先在精修 none/high 两种情况失败，修复后四项测试全部通过，包含八种功能/开关组合的调用分派至 HTTP 请求体。
- P1 待修：app.js refineDraft 忽略 saveDraft 返回的 ok=false；模拟磁盘保存失败后仍打开精修对话框已复现。可能用磁盘旧稿请求，beginStream 又清空当前编辑器。
- P1 待修：providers.py SSE 解析忽略无 choices 的 error 事件，EOF 未要求完成标记；隔离 BytesIO 探针证实部分正文后错误事件/直接 EOF 都返回 partial 与空 finish_reason。Provider 仅检查正文非空，精修随后可保存为普通新稿。
- P2 待修：update_draft_content 原位修改正文但保持 draft_id；find_ai_review_for_draft 和精修入口仅验证 ID/type，没有正文版本或摘要一致性验证。审稿后编辑仍会复用旧审稿，且 ai_review 界面入口发现已有审稿直接返回。
- P2 待修：finish_reason=length 有保存在产物，但精修完成回调没有截断提示，按普通新稿提示成功；隔离 SSE 探针已确认 length 结果正常返回。审稿截断虽有提示，也未阻止用于精修。
- P2 待修：精修先对上下文做预算估计，再追加完整源稿和审稿意见，未对最终 provider_prompt 重新核算输入与输出容量。此为源码确认的边界缺口，未实测超限请求。
- 已有保护：审稿须属于同一 draft_id 且为 AI 类型；原文经推理清洗；精修保存新版本及源稿/审稿关联，状态 draft，不自动确认；界面后端单任务互斥。上述保护不代表审稿时效、全文完整性或实际修改质量已验证。
- USER_DECISION_REQUIRED：旧审稿失效应阻断重审还是允许明确确认后复用；截断结果应作为不完整候选保留并提示还是拒绝生成。建议前者采用重审，后者保留并禁止冒充完整稿；未实施这些策略变更。
- 构建：SkipInstall 编译成功，候选 build/pyinstaller_dist/NovelAgentWorkbench 中 EXE 的精修分支与 UI 已核对。覆盖 dist 正式 EXE 时 Access denied，疑似运行占用，已停止替换并请求用户退出；没有杀进程或绕过。正式 EXE 此时仍是上一版。
- 限制：这是当前代理源码审查及隔离探针，不是独立模型审核；未进行真实付费调用和完整 GUI 操作验收。


### 精修链路其余问题修复（用户授权全部处理）

- 现代与经典界面：保存编辑失败即停止审稿/精修；现代精修在保存后重新核对审稿有效性，避免磁盘旧稿与编辑区错配。
- 审稿有效性：新 AI 审稿记录原始正文 SHA-256。复用和精修入口均核对同一草稿及正文摘要；正文改变、旧记录缺少摘要、审稿被截断或仅返回思考内容时要求重新审稿。历史审稿文件不修改、不删除。补充精修源正文摘要作为版本证据。
- SSE：上游 error 事件、finish_reason=error、无完成标记的 EOF 均抛出错误；保留 stop/length 和仅 DONE 终止的兼容性。收到正文或推理后连接失败不自动重试，防止两次内容混合；未开始输出时仍保留既有有限重试。
- 输出：精修截断结果保存新版本，并持久化 output_incomplete；两种界面均提示不完整候选，现代界面及经典编辑区重新打开时继续显示警示。空白/仅思考输出不创建精修稿。失败不覆盖源稿、不新增普通成功候选。
- 容量：先为系统要求、完整原稿与审稿预留输入预算，再组装背景上下文；发送前复核最终完整输入。模型目录有 context_length 时同时核对输入估算与输出预算。原稿与审稿不静默截断。沿用 ceil(chars/4) 并加消息开销估算，非真实 tokenizer；未知模型容量记录 null，不声称已验证。
- 验证：test_refinement_integrity.py 12 项、test_reasoning_switch.py 4 项通过；test_refinement_ui.cjs 覆盖保存失败、审稿过期、有效分派及完整/截断提示通过。隔离真实项目文件验证新审稿、正文修改后重审、精修产物、错误不落稿与原稿不变。compileall、JS 语法和 diff 检查通过。流式中断/旧审稿测试在修复前按预期失败。
- 反证自审：补测已经收到流式文本后网络错误，不得自动重试；仅思考文本清洗为空不得落稿；旧审稿缺失摘要不能因 draft_id 相同而复用。未进行独立模型评审或付费 API/真实 GUI 端到端验收。
- 构建：复用既有 PyInstaller spec/环境，无依赖安装。完整候选位于 build/ai_refinement_repair_dist/NovelAgentWorkbench；嵌入模块及 app.js、studio.js 与修复内容核对通过。EXE SHA-256: 4e7dc276f264433afa04ac0a3026ac9554247634fdfbf4b495c73f5fcf51baf8。
- 正式目录替换尚待用户选择：先前删除旧程序目录的替换命令被自动审批 blocked by policy 拒绝，未重试。已提出先备份程序文件后覆盖，或用户手动替换两种方式；用户数据和旧 ZIP 均未改动。


### GitHub 源码同步

- 用户授权上传至对应 GitHub 仓库；已核对 origin 为 linnnn89/novel-agent-workbench，分支 main，fetch 后本地与远端无分歧。
- 本次提交范围：精修/推理修复、三份回归测试脚本及本日工作记录。既有安卓迁移记录留在本地；构建文件、个人项目数据和密钥不纳入提交。验证沿用本次修复已通过的 16 项 Python 测试、前端交互及打包核验；正式 EXE 替换仍未完成。


## 2026-09-11（北京时间）个人 Windows 单机优化

- 授权与定位：用户授权实施本轮审查建议，继续采用个人自用、非商业、Python + pywebview + 本地 JSON 的结构，主要适配 DeepSeek Flash。明确要求：确认章节变更仅弹窗建议手工核对记忆，不由 AI 精细改写；允许宽松预算及小型 tokenizer；思考控制兼容后续 DeepSeek 版本。起始源码 HEAD 为 `84bebf3`，调查时工作区干净。
- 保存：现代界面在切换作品/章节/版本、重新打开当前稿件、重写、审稿、确认、导出及导入前检查保存结果；保存失败保留编辑区及失败标记。串行写入、共用进行中的保存和导航序号防止慢响应覆盖新选择；右键动作在打开失败后停止。经典 Tk 的对应保存入口也增加失败拦截，并保留正文末尾换行。
- 减少写盘：前端去除重复请求；后端正文、索引和关联确认稿均一致时跳过无变化保存。反证场景是正文已写入而索引写入失败：重试必须补齐确认稿和索引，不能因正文相同就误报成功。20 次无变化保存的文件集合与字节内容完全不变；历史备份和真实用户资料未清理。
- 记忆提醒：确认章节正文有变化，或替换确认稿版本且内容变化，已保存记忆包含该章来源（或旧记录没有来源）时返回提醒。现代弹窗每个作品/章节每次启动最多一次，并避让其他对话框；经典编辑入口也提醒。记忆正文、启用状态和历史记录保持原样，原有主动生成/压缩功能仍由用户选择。
- Token 预算：默认输入预算 32768 → 131072；明确保存过的旧预算不迁移，现代创作设置提供一键填入宽松值并保存。引入固定版本 `deepseek-tokenizer==0.3.0`，仅安装到项目 `.venv`；下载约 1.9 MB、词表 6367146 bytes、无额外运行依赖。wheel SHA-256 `b6617d0b92aabaebe71a7be23244b5c602a5b0c1bd2dcdc6fa0dfdaf735f9e88`；词表 Git blob SHA-1 `628e3364caad11bdf9e67cea06eae7878122811d` 与官方 DeepSeek V4 Flash 0731 词表一致。10 万字符中文合成样本编码约 0.14 秒（单次小样本，仅作选型依据）。惰性加载并串行保护内部缓存；缺失 tokenizer 或其他模型使用中文保守估算。动态名称/未来模型和消息封装仍有估算误差，以服务商用量为准。
- 上下文：记忆权重只参与选择意义，不再折扣实际发送长度；空背景预算确实选择零项。正文、审稿、精修先预留完整任务所需文本；所有模型生成入口统一检查完整输入及输出空间，目录提供 context_length 时同时限制模型容量。原稿和审稿不静默截断。未指定 max_tokens 的生成使用已有创作设置默认值，连接测试仍保持自己的小额度。
- DeepSeek：按模型家族识别 Flash/Pro 动态名称、V4/V4.1/V5 等版本形式，排除无关模型、R1/distill/vision。协议与模型名称分离：官方 thinking + reasoning_effort；OpenRouter/Chutes reasoning；SiliconFlow enable_thinking（仅开关）。接入设置增加自动/指定协议/不发送控制；模型级配置可优先覆盖。新名称可手工指定已有协议，不承诺未知未来协议自动兼容。保留旧函数名供既有脚本兼容。
- 输出与停止：普通生成、重写和精修统一拒绝空白/仅思考正文，长度截断则保留新候选并标记 output_incomplete。取消控制绑定每个现代界面任务；取消可中断等待响应头和读取输出，收到思考后不再取消超时，纯心跳也不能无限续期。Windows 上 shutdown 不能可靠唤醒阻塞的 readline，改为分离并关闭本任务拥有的 socket 句柄；响应已进入本地保存阶段则完成保存并提示稍候。任务编号拦截迟到回调。正文任务失败/取消恢复原稿，已经显示的片段可复制；本地停止不保证上游立即停止计算或计费。停止按钮位于现代正文区及工作室，经典界面保留有限网络超时。
- 刷新与用量：正文和思考按约 50 ms 或 2048 字符批量推送，正常完成时刷新尾部，取消后丢弃未发送缓冲。1000 个单字回调在固定时钟测试中合并为 1 次正文推送，顺序与尾部保持一致。调用日志保留 OpenRouter 缓存详情、思考 token、数值费用，缺失值不伪造为零；增加功能、耗时、估算 token 和系统提示词摘要。保留各功能提示词职责，缓存优化先获得可比较记录，未进行付费命中率实验。
- 验证：`.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s scripts -p 'test_*.py'` 共 42 项通过（原有 16 + 新增 26）；`node scripts/test_local_ui.cjs` 19 项通过，`node scripts/test_refinement_ui.cjs` 原有场景通过；JS 语法、Python 3.10 语法兼容解析及 `git diff --check` 通过。测试均使用临时作品、合成文本及本机回环 HTTP 服务，无付费 API 或真实小说数据。含真实 WorkbenchBridge 停止任务后零新草稿的集成检查。
- 失败与修复记录：第一次新增回归发现 Windows 响应头等待停止不及时，修正 socket 释放后通过；另一个用例误用规范化前的 provider ID，改为使用实际返回 ID。原有容量测试使用重复 x 并假定 chars/4，改为足够长的中文原稿以保留其真实边界意图。首次隔离打包因 add-data 相对 spec 目录解析失败，换成项目绝对路径后通过。
- 打包：使用现有 PyInstaller 6.20.0 / Python 3.14.5 构建完整候选，位于 `build/local_optimizations_20260911/dist/NovelAgentWorkbench/`，整体约 44.08 MiB；构建脚本加入 tokenizer 收集。最终 EXE SHA-256 `84fde9121d4c2a8b77d7b7767cd78a73504d676078a59053c493a5aebf5f380a`。逐一比较已打包的 52 个项目 Python 模块（归一化代码文件名）与现源码编译结果，以及全部 UI 资源，均一致；词表官方摘要匹配，打包目录内 tokenizer 可独立导入并编码中文，未包含项目注册表或密钥文件。Android 可选模块收集警告与本次 Windows 目标无关；collections.abc 告警已核对其 collections/_collections_abc 引导文件包含在包中。
- 未验证与交付边界：Browser 技能连接在初始化时被环境拒绝，原始信息为 `privileged native pipe bridge is not available; browser-client is not trusted`；未改用其他控制通道绕过，因此真实浏览器页面/WebView 交互验收未完成。候选 EXE 已构建和检查嵌入内容，未声称已启动并完成 GUI 验收；TLS/DNS 中止以及真实服务商行为也未做在线验收。后续可在本机候选程序人工检查，或恢复 Browser 连接后自动验收。原 `dist` 正式程序、真实用户数据和 GitHub 均未替换/推送。本次没有待定的重要方案或新增授权请求。

- 最终补充反证：等待保存期间连续点击重写，只启动一个任务并保留正确原稿；打开稿件不直接信任前端无变化缓存，首次保存仍交由后端核对磁盘一致性。新增界面测试最终为 21 项，均通过；Python 42 项结果保持有效（此补充仅改前端）。候选再次打包并复核 52 个 Python 模块和全部 UI 资源与现源码一致。最终 EXE SHA-256 `84fde9121d4c2a8b77d7b7767cd78a73504d676078a59053c493a5aebf5f380a`，最终 app.js SHA-256 `dbce688f95cf8fefcf52ffe5438373bbde128d3b69543d9ad2f8b99b6e5c1088`。原正式程序仍未替换。

## 2026-09-11 10:52（北京时间）重建正式 EXE 并交付 PR

- 用户明确要求重新构建 EXE、上传 PR 并合并，接受后续自行反馈修复问题。
- 重新执行隔离 PyInstaller 构建成功；正式 `dist/NovelAgentWorkbench` 的 EXE 与 `_internal` 已替换，旧程序保存在 `old/program-backup-20260911-105156/`。逐文件 SHA-256 核对 1223 个程序文件与构建候选一致；用户数据目录及用户数据.zip 的替换前后指纹一致。EXE SHA-256：`84fde9121d4c2a8b77d7b7767cd78a73504d676078a59053c493a5aebf5f380a`。
- 当前源码重新验证：Python 42 项通过，界面逻辑 21 项通过，原有精修界面回归通过，git diff --check 通过。
- 远端 main 与起始 HEAD 一致；仓库没有 CI 工作流、分支保护或规则集。将以独立分支创建 PR，核对最新 PR head 和检查状态后合并，不将无 CI 描述为 CI 通过。
- 已知限制延续：真实 WebView/EXE 窗口交互、真实服务商请求及 TLS/DNS 中止未验收。二进制和用户数据不纳入源码 PR；本地 EXE 已更新。
