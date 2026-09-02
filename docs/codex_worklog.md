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
