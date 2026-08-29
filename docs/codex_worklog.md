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
