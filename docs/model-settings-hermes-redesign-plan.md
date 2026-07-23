# 模型设置 HERMES 式重构计划

日期：2026-07-23（北京时间）  
状态：设计与实施计划，尚未开始编码  
目标产品：`NovelAgentWorkbench` Windows 桌面应用

## 1. 目标

把当前“用途、Provider、模型、API 地址、API Key 全部混在一个表单里”的模型服务窗口，重构为三层清晰的配置体验：

1. 管理 API Provider、端点和各自的密钥。
2. 查看、刷新、搜索并启用每个 Provider 提供的模型。
3. 指定正文生成、AI 审稿、AI 精修、记忆总结和记忆压缩分别使用哪个模型。

设计理念参考用户提供的 HERMES 截图，但不照搬其完整设置中心；本项目只重构与模型相关的区域，并延续当前工作台的浅色、克制、Windows 桌面原生视觉语言。

## 2. 当前架构调查结论

### 2.1 当前用户界面

现有 `configure_model_connection()` 使用一个表单同时处理：

- 功能用途：`writer`、`scorer`、`reviser`。
- Provider 类型。
- 模型 ID。
- API Base URL。
- API Key。
- 请求超时。
- DeepSeek 思考模式。

主要问题：

- 同一个 Provider 的 Key 和 Base URL 会在不同用途之间重复出现。
- Provider、模型和功能分配是三类不同概念，却在同一个保存动作中被绑定。
- 模型 ID 只能手工输入，不能浏览 Provider 的模型目录。
- 用户无法一眼看到“哪些功能继承主模型，哪些功能单独覆盖”。
- 数据结构直接按角色保存完整 Provider 配置，限制了后续扩展更多功能。

### 2.2 当前数据结构

`global_settings.json` 当前为 schema version 1，核心结构是：

```json
{
  "schema_version": 1,
  "model_roles": {
    "writer": {
      "provider": "openrouter",
      "model": "deepseek/deepseek-v4-flash",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key_ref": "project_secret.writer_openrouter_api_key",
      "settings": {
        "timeout_seconds": 300
      }
    },
    "scorer": {},
    "reviser": {}
  }
}
```

`global_secrets.local.json` 是扁平的本地密钥映射。当前密钥名由“功能角色 + Provider”组合生成，因此同一个 Provider 可能出现多个重复 Key。

只读核对当前实际配置后，`writer`、`scorer`、`reviser` 均使用 OpenRouter 的 `deepseek/deepseek-v4-flash`，且均已有密钥引用。迁移时应折叠为一个 OpenRouter Provider 档案、一个模型档案和统一的功能分配，不应要求用户重新输入 Key。

### 2.3 当前运行时

运行时目前围绕 `ModelRoleConfig` 工作：

- `writer`：正文生成，也被记忆银行生成和压缩复用。
- `scorer`：AI 审稿；未配置时回退到 `writer`。
- `reviser`：AI 精修/改写；未配置时回退到 `writer`。

当前仅有“角色”概念，没有“具体功能”概念。因此若要让记忆总结与正文生成使用不同模型，不能只改 UI，必须给请求增加稳定的 `feature_id` 并在运行时解析。

## 3. 推荐的信息架构

新“模型服务”窗口采用一个可调整大小的设置壳，左侧为窄导航，右侧为内容区，底部操作栏始终可见。

左侧仅保留三个页面：

1. `API 提供商`
2. `模型目录`
3. `功能分配`

不复制 HERMES 的“外观、安全、通知、账单”等无关设置项。

```mermaid
flowchart LR
    A["API 提供商<br/>端点与密钥"] --> B["模型目录<br/>远端目录与手工模型"]
    B --> C["功能分配<br/>主模型与功能覆盖"]
    C --> D["运行时解析器"]
    D --> E["现有 Provider Client"]
```

## 4. 页面一：API 提供商

### 4.1 页面目标

回答三个问题：

- 当前支持哪些 Provider？
- 哪些 Provider 已配置并可用于请求？
- 每个 Provider 的端点、Key 和连接状态是什么？

### 4.2 布局

右侧页面再分为两栏：

- 左栏：Provider 列表，宽约 280 px。
- 右栏：选中 Provider 的编辑区，随窗口伸缩。

Provider 列表每行显示：

- 状态圆点：未配置、已配置、检查通过、检查失败。
- Provider 名称。
- 简短状态：`未设置 Key`、`已保存 Key`、`本地端点`。
- 当前启用模型数量。

首批内置 Provider：

- 离线测试。
- OpenRouter。
- DeepSeek。
- Chutes。
- OpenAI 兼容云端 API。
- 本地 OpenAI 兼容端点。
- 自定义 OpenAI 兼容端点。

数据层应允许以后创建多个自定义端点；首版 UI 对内置 Provider 默认只显示一个档案。

### 4.3 Provider 编辑区

字段：

- Provider 名称：内置项只读，自定义项可编辑。
- API Base URL。
- API Key 状态。
- API Key 新值输入框。
- 请求超时。
- Provider 专属选项，例如 DeepSeek 思考模式默认值。

密钥交互：

- 已保存时显示 `已保存 · 末 4 位` 或仅显示 `已保存`。
- 不提供“显示完整已保存 Key”。
- 提供 `替换 Key` 和 `移除 Key`。
- 移除前列出受影响的模型和功能并二次确认。
- 保存 Provider 只写本地配置，不联网。

操作：

- `保存 Provider`
- `检查连接`：明确提示会联网。
- `刷新模型`：明确提示会联网。
- `恢复默认端点`
- `删除自定义端点`

### 4.4 状态规则

- `未配置`：缺少必要的 Base URL 或 Key。
- `已配置`：本地字段完整，但尚未做连接检查。
- `检查通过`：最近一次用户主动连接检查通过。
- `检查失败`：最近一次用户主动连接检查失败；不自动清除现有模型与分配。

## 5. 页面二：模型目录

### 5.1 页面目标

提供类似 HERMES 的按 Provider 分组模型选择体验，同时避免把当前模型清单硬编码进软件。

顶部工具栏：

- 搜索模型。
- Provider 筛选。
- `只看已启用`。
- `刷新当前 Provider`。
- 最近刷新时间。

主体按 Provider 分组，每个分组显示：

- Provider 名称和连接状态。
- 可用模型数量。
- 可折叠模型列表。
- 该 Provider 的 `手工添加模型`。

模型行显示：

- 模型显示名。
- 请求使用的真实模型 ID。
- 上下文长度（Provider 返回时才显示）。
- 文本、图像、推理等能力标签（Provider 返回时才显示）。
- `已启用`/`未启用`。
- 被哪些功能使用。

不在首版加入“High”“Low”等主观能力等级，也不自动宣称某模型更适合写作；这些判断缺少稳定、可验证的依据。

### 5.2 模型目录来源

推荐采用 `远端目录 + 本地缓存 + 手工模型` 混合模式：

- OpenRouter：用户主动刷新时请求官方 `/api/v1/models`。
- DeepSeek：用户主动刷新时请求官方 `/models`。
- OpenAI 兼容云端、本地端点和 Chutes：优先尝试标准 `/models`；失败时保留缓存并允许手工输入模型 ID。
- 离线测试：使用本地静态模型。

官方资料依据：

- OpenRouter 模型目录：<https://openrouter.ai/docs/api/api-reference/models/get-models>
- DeepSeek 模型目录：<https://api-docs.deepseek.com/api/list-models>
- Chutes OpenAI 兼容说明：<https://chutes.ai/docs>

DeepSeek 官方文档显示旧模型别名会变化或弃用，这进一步说明不应把模型清单永久硬编码在 UI 中：

- <https://api-docs.deepseek.com/guides/function_calling/>
- <https://api-docs.deepseek.com/updates/>

### 5.3 刷新行为

- 应用启动时不自动联网。
- 进入模型目录时不自动联网。
- 只有用户点击“刷新模型”才联网。
- 使用后台线程，窗口不冻结。
- 显示进度、取消和失败原因。
- 刷新失败不清空上次成功缓存。
- 远端返回的模型目录是“不可信外部数据”，必须限制字段长度和条目数量。
- 缓存中不得写入 Authorization Header、API Key 或完整错误响应。

### 5.4 缓存

新建派生缓存文件：

```text
model_catalog_cache.json
```

建议结构：

```json
{
  "schema_version": 1,
  "providers": {
    "openrouter": {
      "refreshed_at": "2026-07-23T00:00:00Z",
      "status": "ok",
      "models": [
        {
          "id": "deepseek/deepseek-v4-flash",
          "name": "DeepSeek V4 Flash",
          "context_length": 0,
          "capabilities": ["text"],
          "source": "remote"
        }
      ]
    }
  }
}
```

这是可删除、可重建的派生数据，不与核心设置混写。

## 6. 页面三：功能分配

### 6.1 页面目标

让用户直接回答“每个功能用哪个模型”，而不是理解 `writer/scorer/reviser` 等内部角色。

顶部为“主模型”：

- 主模型默认承担正文生成。
- 其他功能默认选择“使用主模型”。
- 主模型失效时，保存前给出阻断提示。

首版功能列表：

| 功能 ID | 用户可见名称 | 当前后端角色 | 默认行为 |
|---|---|---|---|
| `draft_generation` | 正文生成 | `writer` | 主模型 |
| `ai_review` | AI 审稿 | `scorer` | 使用主模型 |
| `ai_refinement` | AI 精修/改写 | `reviser` | 使用主模型 |
| `memory_generation` | 记忆银行总结 | `writer` | 使用主模型 |
| `memory_compression` | 记忆银行压缩 | `writer` | 使用主模型 |

每行显示：

- 功能名称。
- 简短说明。
- 当前模式：`使用主模型` 或 `单独指定`。
- 当前模型：按 Provider 分组的下拉菜单。
- Provider 配置状态。
- `改用主模型` 快捷操作。

模型下拉参考 HERMES：

- 顶部搜索框。
- 按 Provider 分组。
- 已启用模型优先。
- 当前模型有勾选标记。
- 不显示未配置 Provider 的模型，或显示为禁用并解释原因。
- 底部提供 `刷新模型` 和 `编辑模型目录`。

### 6.2 保存前校验

必须阻断保存：

- 主模型不存在。
- 分配引用不存在的模型。
- 模型所属 Provider 已删除。
- 云端 Provider 缺少必要 Key。
- Base URL 为空或格式非法。

只警告、不阻断：

- 目录缓存过期。
- 模型来自手工输入，尚未通过连接检查。
- 某功能继承主模型。
- Provider 最近一次连接检查失败，但用户仍选择保留配置。

## 7. 推荐的新数据模型

将 `global_settings.json` 升级为 schema version 2。

```json
{
  "schema_version": 2,
  "provider_profiles": {
    "openrouter": {
      "profile_id": "openrouter",
      "adapter_id": "openrouter",
      "display_name": "OpenRouter",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key_ref": "project_secret.provider_openrouter_api_key",
      "timeout_seconds": 300,
      "enabled": true,
      "settings": {}
    }
  },
  "model_profiles": {
    "openrouter::deepseek/deepseek-v4-flash": {
      "model_ref": "openrouter::deepseek/deepseek-v4-flash",
      "provider_profile_id": "openrouter",
      "model_id": "deepseek/deepseek-v4-flash",
      "display_name": "DeepSeek V4 Flash",
      "enabled": true,
      "source": "remote"
    }
  },
  "primary_model_ref": "openrouter::deepseek/deepseek-v4-flash",
  "feature_assignments": {
    "draft_generation": {
      "mode": "primary",
      "model_ref": ""
    },
    "ai_review": {
      "mode": "primary",
      "model_ref": ""
    },
    "ai_refinement": {
      "mode": "primary",
      "model_ref": ""
    },
    "memory_generation": {
      "mode": "primary",
      "model_ref": ""
    },
    "memory_compression": {
      "mode": "primary",
      "model_ref": ""
    }
  }
}
```

### 7.1 设计原则

- Provider 档案拥有 Base URL、Key 引用和 Provider 级设置。
- 模型档案只拥有模型身份和显示元数据，不重复保存 Key。
- 功能分配只引用 `model_ref`。
- API Key 仍只存在于 `global_secrets.local.json`。
- `model_ref` 使用稳定内部 ID，不使用可变显示名称。
- 内置 Provider 和自定义端点使用相同抽象。

## 8. 运行时解析设计

### 8.1 保留现有语义角色

保留 `writer/scorer/reviser`，因为：

- 现有 Provider 日志使用这些角色。
- Prompt 与输出处理仍依赖角色语义。
- 大量旧代码和产物元数据已经记录这些值。

### 8.2 新增功能 ID

给 `ProviderRequest` 增加可选字段：

```python
feature_id: str = ""
```

请求调用点传入：

- 草稿生成：`draft_generation`
- AI 审稿：`ai_review`
- AI 精修：`ai_refinement`
- 记忆总结：`memory_generation`
- 记忆压缩：`memory_compression`

### 8.3 解析顺序

`resolve_effective_model_config(feature_id, role)`：

1. 查找功能分配。
2. 若为 `explicit`，使用指定 `model_ref`。
3. 若为 `primary`，使用 `primary_model_ref`。
4. 将模型档案与 Provider 档案组合为临时 `ModelRoleConfig`。
5. 保留传入的语义角色用于日志和输出处理。
6. 若新 schema 尚未迁移，回退到旧 `model_roles`。

这样可以在不重写现有 HTTP Client 的前提下，让同一个 `writer` 语义角色在不同功能中使用不同模型。

## 9. 旧配置迁移

### 9.1 安全边界

- 首次迁移前，创建带时间戳的 `global_settings.json` 备份。
- 不复制 `global_secrets.local.json`，避免制造额外明文密钥副本。
- 首版迁移不删除旧密钥条目。
- 使用原子写入。
- 迁移失败时保持原文件不变并继续使用旧 schema。

### 9.2 迁移算法

1. 读取旧 `writer/scorer/reviser`。
2. 按 `provider + base_url + api_key_ref` 分组建立 Provider 档案。
3. 每个唯一 `provider + model` 建立模型档案。
4. `writer` 模型成为主模型。
5. `scorer` 与 `writer` 相同则设为“使用主模型”，不同则显式分配。
6. `reviser` 与 `writer` 相同则设为“使用主模型”，不同则显式分配。
7. 记忆总结和记忆压缩默认继承旧 `writer`。
8. 保留 `legacy_model_roles` 只读快照一个版本，供回滚和兼容检查。

### 9.3 不同 Key 的处理

如果同一 Provider 在不同角色中引用不同 Key，不得静默合并：

- 自动创建多个 Provider 档案。
- 名称示例：`OpenRouter（正文生成）`、`OpenRouter（AI 审稿）`。
- 原功能继续指向各自档案，行为不变。
- UI 后续允许用户主动合并。

当前实际配置的三个角色均指向同一 OpenRouter 配置，预计会自动迁移为一个 Provider 档案，不触发该分支。

## 10. 后端模块划分

建议新增：

### `model_settings.py`

- schema v2 默认值。
- ProviderProfile、ModelProfile、FeatureAssignment 数据结构。
- 校验与序列化。
- schema v1 → v2 迁移。
- 功能分配解析。
- 兼容旧 `model_roles`。

### `model_catalog.py`

- Provider 模型目录策略。
- `/models` 请求。
- 响应归一化。
- 缓存读写。
- 手工模型。
- 条目上限、字段长度和异常清洗。

### `model_settings_ui.py`

- 模型服务设置壳。
- 左侧导航。
- Provider 页面。
- 模型目录页面。
- 功能分配页面。
- 固定底栏、脏状态和关闭确认。

建议把新 UI 从已超过 6000 行的 `desktop_app.py` 中拆出，避免继续扩大单文件。

需要修改：

### `application_service.py`

新增稳定 facade：

- `list_provider_profiles()`
- `read_provider_profile(profile_id)`
- `upsert_provider_profile(...)`
- `remove_provider_profile(profile_id)`
- `set_provider_secret(profile_id, value)`
- `remove_provider_secret(profile_id)`
- `list_model_profiles()`
- `set_model_enabled(model_ref, enabled)`
- `add_manual_model(...)`
- `refresh_provider_models(profile_id)`
- `read_feature_assignments()`
- `update_feature_assignments(...)`
- `resolve_feature_model(feature_id)`

### `providers.py`

- `ProviderRequest.feature_id`。
- 接受解析后的有效模型配置。
- 保留角色语义。
- Provider 日志增加 `feature_id`。
- 模型目录刷新与真实生成共享安全的认证 Header 构造，但不得共享日志正文。

### `config.py`

- `GLOBAL_SETTINGS_SCHEMA_VERSION = 2`。
- 新 schema 默认值。
- 旧 schema 兼容入口。

### `desktop_app.py`

- 顶部“模型服务”入口改为打开新设置壳。
- 主界面模型摘要读取新功能分配。
- “连接检查”读取 Provider/功能状态。
- 删除旧单表单 UI 和仅为旧表单服务的辅助函数。

## 11. UI 状态管理

窗口打开时创建一个内存草稿：

```text
saved_state
working_state
dirty = working_state != saved_state
```

规则：

- Provider 字段、模型启用状态和功能分配先写入 `working_state`。
- `保存全部设置` 才写核心设置。
- `取消` 丢弃草稿。
- 有未保存修改时关闭窗口必须确认。
- `Ctrl+S` 保存。
- 底栏固定显示 `取消` 与 `保存全部设置`。
- 远端模型刷新写派生缓存，但不自动改变功能分配。
- 删除 Provider、移除 Key 等破坏性操作单独确认。

## 12. 网络与安全

- 保存配置不联网。
- 刷新模型和检查连接必须由用户主动点击。
- 真实请求前显示 Provider、目标主机和动作。
- 所有网络动作使用后台线程。
- 默认超时沿用 300 秒；目录刷新可使用更短的独立超时，例如 30 秒。
- API Key 不进入日志、异常文本、缓存、模型档案或公开状态。
- 已保存 Key 不回填到普通文本框。
- Provider 错误响应只保留状态码和安全摘要。
- 模型刷新失败不覆盖最后一次成功缓存。
- 不在自动化测试中调用真实 Provider。

## 13. 测试计划

### 13.1 数据与迁移

新增 `tests/test_model_settings_schema.py`：

- schema v2 默认值。
- v1 三角色同 Provider 同 Key 的折叠迁移。
- 同 Provider 不同 Key 不被错误合并。
- 迁移失败不破坏旧设置。
- 旧密钥仍可解析。
- 原始 Key 不进入设置和日志。

### 13.2 模型目录

新增 `tests/test_model_catalog.py`：

- OpenRouter 响应归一化。
- DeepSeek 响应归一化。
- 标准 OpenAI `/models` 响应归一化。
- 无效 JSON、超时、HTTP 错误。
- 失败时保留旧缓存。
- 手工模型与远端模型去重。
- 条目数和字段长度限制。
- 测试使用 mock/本地假响应，不联网。

### 13.3 功能解析

新增 `tests/test_model_feature_resolution.py`：

- 正文生成使用主模型。
- AI 审稿继承主模型。
- AI 审稿显式覆盖。
- AI 精修显式覆盖。
- 记忆总结与压缩可分别覆盖。
- Provider 删除后解析失败并给出明确错误。
- 新 schema 不存在时兼容旧 `model_roles`。
- Provider 日志同时记录逻辑角色和功能 ID。

### 13.4 UI 合约

新增 `tests/test_model_settings_ui_contract.py`：

- 三个导航页面存在。
- 保存底栏始终存在。
- 所有页面随窗口伸缩。
- Key 默认不显示明文。
- 功能下拉按 Provider 分组。
- 未配置 Provider 不可被误选。
- 未保存修改关闭时触发确认。
- 保存操作不调用网络。
- 刷新模型明确调用网络动作。

### 13.5 完整回归

- 当前全部单元测试。
- 草稿生成。
- AI 审稿。
- AI 精修。
- 记忆银行生成与压缩。
- Provider 状态和连接检查。
- EXE 打包。
- 用户数据目录保留。

## 14. 人工验收清单

在 Windows 100%、125%、150% DPI 下检查：

1. 三个设置页面均无裁切。
2. 窗口放大、缩小后导航、列表、详情和固定底栏布局正确。
3. Provider Key 可以新增、替换和移除。
4. 保存 Provider 不联网。
5. 刷新模型前有明确网络动作。
6. 模型按 Provider 分组，可搜索。
7. 主模型切换后，继承主模型的功能同步更新。
8. 单独覆盖的功能不随主模型变化。
9. 保存、关闭、重开后设置一致。
10. 旧配置首次打开后无 Key 丢失、无模型分配变化。
11. 模型调用记录展示正确 Provider、模型、角色和功能。
12. 真实 Key 不出现在日志、缓存或截图可见区域。

## 15. 实施顺序与阶段闸门

### 阶段 0：冻结规格

- 确认本计划末尾的 `USER_DECISION_REQUIRED`。
- 不开始 UI 编码，直到功能粒度和项目覆盖范围确定。

验收：数据层目标、页面结构和首版边界明确。

### 阶段 1：schema v2 与迁移

- 新建 `model_settings.py`。
- 写默认结构、校验、迁移和备份。
- 先写测试，再连接现有应用服务。

验收：旧配置能无损迁移并可回滚。

### 阶段 2：Provider 档案与密钥

- Provider CRUD。
- 一 Provider 一密钥引用。
- 替换、移除和受影响项检查。
- 不联网保存。

验收：密钥不泄露，旧 Key 无需重新输入。

### 阶段 3：模型目录

- 新建 `model_catalog.py`。
- OpenRouter、DeepSeek、标准 `/models` 策略。
- 手工模型和缓存。
- 失败回退。

验收：无真实网络测试也能覆盖解析与失败逻辑。

### 阶段 4：功能分配解析器

- 新增 `feature_id`。
- 主模型与功能覆盖。
- 保留旧角色语义和日志。

验收：五个功能能独立解析到正确模型。

### 阶段 5：新模型设置 UI

- 新建 `model_settings_ui.py`。
- Provider、模型目录、功能分配三个页面。
- 固定底栏、脏状态、键盘保存。
- 所有窗体可调整大小。

验收：低 DPI 和高 DPI 均无裁切，设置路径完整。

### 阶段 6：接入现有入口与摘要

- 替换旧“模型服务”表单。
- 更新主界面模型摘要。
- 更新连接检查。
- 删除不再使用的旧 UI 辅助函数。

验收：用户不再接触内部 `writer/scorer/reviser` 名称。

### 阶段 7：回归与反证审查

- 全部自动化测试。
- 专门检查“看似保存成功但实际功能仍走旧模型”。
- 专门检查“删除 Key 后仍显示已配置”。
- 专门检查“刷新失败清空模型列表”。
- 专门检查“迁移时多个不同 Key 被错误合并”。

验收：所有阻断场景均有可理解的错误提示。

### 阶段 8：EXE 构建与交付

- 使用现有 Python 和 PyInstaller，`-SkipInstall`。
- 只替换 EXE 与 `_internal`。
- 保留 `用户数据/workspace_projects`。
- 记录 EXE 时间、大小、SHA-256。
- 未经单独授权不调用真实模型 API。

验收：新 EXE 启动、设置可保存、旧数据可读取。

## 16. 明确排除

首版不做：

- Provider 账户余额或账单。
- 模型价格比较与自动推荐。
- 自动联网刷新。
- 自动选择“最强模型”。
- 模型 benchmark 排名。
- 多 Key 自动轮换。
- Provider 故障自动跨平台切换。
- 完整复刻 HERMES 的设置中心。
- 无证据的 High/Low 能力标签。

## 17. USER_DECISION_REQUIRED

### 决策 1：首版功能粒度

推荐：

- 正文生成。
- AI 审稿。
- AI 精修/改写。
- 记忆银行总结。
- 记忆银行压缩。

影响：如果只保留现有三个角色，记忆银行仍无法独立选模型。

### 决策 2：项目专属模型覆盖

推荐首版：

- 新 UI 只管理软件级全局模型。
- 保留旧项目专属配置的兼容读取，但暂不新增项目覆盖 UI。
- 后续另做“本项目覆盖全局模型”。

影响：同时实现全局与项目两层会显著增加迁移、状态提示和测试复杂度。

### 决策 3：Provider 档案数量

推荐：

- 数据层支持同一 adapter 多个档案。
- 首版内置 Provider 各显示一个档案。
- “自定义 OpenAI 兼容端点”允许多个。

影响：既能保持首版简单，也不会锁死未来多账户、多端点需求。

### 决策 4：模型刷新方式

推荐：

- 仅用户主动刷新。
- 远端目录、本地缓存、手工输入并存。
- 保存配置不联网。

影响：符合当前软件的网络安全边界，也能避免模型清单过时。

### 决策 5：主模型规则

推荐：

- 正文生成模型即主模型。
- 其他四个功能默认继承主模型。
- 用户可逐项覆盖。

影响：首次设置最简单，同时保留专业用户的精细控制。

## 18. 下一轮编程任务的最小提示词

下一轮可以直接使用：

> 按 `docs/model-settings-hermes-redesign-plan.md` 实施模型设置重构。先完成阶段 1 到阶段 4：schema v2、无损迁移、Provider 档案、模型目录缓存和功能分配解析器；暂不做 UI。所有旧配置与 Key 必须保留，真实 Provider 不联网。完成后跑新增测试和现有完整测试，更新 `docs/codex_worklog.md`，不要重建 EXE，等我验收后再进入 UI 阶段。

建议不要在一次低推理编程会话中同时做全部八个阶段；先完成数据层与解析器，再做 UI，可以显著降低“界面看起来正确但调用仍走旧模型”的风险。
