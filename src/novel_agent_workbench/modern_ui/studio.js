const studio = {
  mode: "",
  tab: "provider",
  model: null,
  memory: null,
  planning: null,
  selectedProvider: "",
  selectedModel: "",
  selectedPlanning: "",
  creating: false,
  followMemory: true,
};

function requireProject() {
  if (!state.projectId) {
    toast("请先选择或新建一个作品。");
    return false;
  }
  return true;
}

function closeStudio() {
  $("studio").hidden = true;
  studio.mode = "";
  studio.memoryBox = null;
  studio.memoryEditor = null;
  studio.memoryTarget = null;
  studio.memoryEnabled = null;
  studio.memoryLive = null;
  studio.memoryBusy = false;
  studio.memoryLiveText = "";
  if (window.ThinkTrace && ThinkTrace.isIdle()) ThinkTrace.close();
}

function setStudioStatus(text) {
  $("studioStatus").textContent = text || "";
}

function renderTabs(items, active, onPick) {
  const host = $("studioTabs");
  host.innerHTML = "";
  items.forEach(([id, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn ${id === active ? "accent" : "quiet"} compact`;
    button.textContent = label;
    button.addEventListener("click", () => onPick(id));
    host.append(button);
  });
}

function openStudioShell({ kicker, title }) {
  $("studioKicker").textContent = kicker;
  $("studioTitle").textContent = title;
  $("studio").hidden = false;
  setStudioStatus("");
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

async function openModelStudio(tab = "provider") {
  studio.mode = "models";
  studio.tab = tab;
  openStudioShell({ kicker: "软件级配置", title: "模型设置" });
  studio.model = await call("model_state");
  if (!studio.selectedProvider && studio.model.providers[0]) {
    studio.selectedProvider = studio.model.providers[0].profile_id;
  }
  renderModelStudio();
}

function renderModelStudio() {
  renderTabs(
    [
      ["provider", "API 提供商"],
      ["models", "模型目录"],
      ["assign", "功能分配"],
    ],
    studio.tab,
    (tab) => {
      studio.tab = tab;
      renderModelStudio();
    }
  );
  const body = $("studioBody");
  body.innerHTML = "";
  if (studio.tab === "provider") body.append(renderProviderPage());
  if (studio.tab === "models") body.append(renderModelsPage());
  if (studio.tab === "assign") body.append(renderAssignPage());
}

function providerById(id) {
  return (studio.model?.providers || []).find((item) => item.profile_id === id) || null;
}

function renderProviderPage() {
  const wrap = el("div", "studio-grid");
  const list = el("div", "studio-list");
  list.append(el("h3", "", "接入商"));
  const scroll = el("div", "studio-scroll");
  (studio.model.providers || []).forEach((provider) => {
    const button = el("button", `choice${provider.profile_id === studio.selectedProvider ? " active" : ""}`);
    button.type = "button";
    button.innerHTML = `<span class="tree-title">${escapeHtml(provider.display_name)}</span><span class="pill">${provider.has_api_key ? "已保存 Key" : "无 Key"}</span>`;
    button.addEventListener("click", () => {
      studio.selectedProvider = provider.profile_id;
      renderModelStudio();
    });
    scroll.append(button);
  });
  list.append(scroll);
  const add = el("button", "btn quiet", "+ 添加自定义接入商");
  add.type = "button";
  add.addEventListener("click", () => {
    studio.selectedProvider = "";
    renderModelStudio();
  });
  list.append(add);

  const form = el("div", "studio-form");
  const provider = providerById(studio.selectedProvider);
  const name = input(provider?.display_name || "");
  const adapter = input(provider?.adapter || "openai_compatible", {
    select: true,
    options: (studio.model.adapters || []).map((item) => [item.id, item.label]),
  });
  const base = input(provider?.base_url || "", { placeholder: "https://api.example.com/v1" });
  const key = input("", { type: "password", placeholder: provider?.has_api_key ? "已保存（留空则保持不变）" : "尚未保存 Key" });
  const timeout = input(String(provider?.timeout_seconds || 300));
  form.append(
    el("p", "studio-note", "接入商保存后不会自动联网。只有“刷新模型”会请求对应 API。"),
    field("名称", name),
    field("适配器", adapter),
    field("API 地址", base),
    field("API Key", key),
    field("接入等待上限（秒，收到思考后不再计时）", timeout)
  );
  const actions = el("div", "side-actions");
  const save = el("button", "btn primary", "保存当前设置");
  save.type = "button";
  save.addEventListener("click", async () => {
    try {
      const result = await call("save_provider", {
        profile_id: studio.selectedProvider,
        display_name: name.value.trim(),
        adapter: adapter.value,
        base_url: base.value.trim(),
        api_key: key.value,
        timeout_seconds: timeout.value,
      });
      studio.model = result;
      studio.selectedProvider = result.profile_id || studio.selectedProvider;
      setStudioStatus("接入商已保存；未发起网络请求。");
      renderModelStudio();
      if (state.projectId) loadOverview(state.projectId).catch(() => {});
      toast("接入商已保存。");
    } catch (error) {
      toast(error.message);
    }
  });
  const refresh = el("button", "btn quiet", "刷新模型");
  refresh.type = "button";
  refresh.addEventListener("click", () => refreshSelectedModels());
  const clearKey = el("button", "btn quiet", "清除 Key");
  clearKey.type = "button";
  clearKey.addEventListener("click", async () => {
    if (!studio.selectedProvider) return;
    try {
      studio.model = await call("clear_provider_key", studio.selectedProvider);
      setStudioStatus("API Key 已清除。");
      renderModelStudio();
    } catch (error) {
      toast(error.message);
    }
  });
  const remove = el("button", "btn quiet", "删除接入商");
  remove.type = "button";
  remove.disabled = Boolean(provider?.built_in) || !studio.selectedProvider;
  remove.addEventListener("click", async () => {
    if (!studio.selectedProvider || provider?.built_in) return;
    try {
      studio.model = await call("delete_provider", studio.selectedProvider);
      studio.selectedProvider = studio.model.providers?.[0]?.profile_id || "";
      renderModelStudio();
      toast("自定义接入商已删除。");
    } catch (error) {
      toast(error.message);
    }
  });
  actions.append(save, refresh, clearKey, remove);
  form.append(actions);
  wrap.append(list, form);
  return wrap;
}

async function refreshSelectedModels() {
  const profileId = studio.selectedProvider || studio.model.providers?.[0]?.profile_id;
  if (!profileId) return toast("请先选择接入商。");
  setStudioStatus("正在刷新模型目录…");
  try {
    await call("refresh_models", profileId);
  } catch (error) {
    setStudioStatus("刷新失败。");
    toast(error.message);
  }
}

function visibleCatalogModels(query) {
  const needle = String(query || "").trim().toLowerCase();
  return (studio.model.models || []).filter((model) => {
    if (studio.selectedProvider && model.provider_profile_id !== studio.selectedProvider) return false;
    if (!needle) return true;
    const hay = `${model.display_name || ""} ${model.model_id || ""}`.toLowerCase();
    return hay.includes(needle);
  });
}

function selectedModelSet() {
  if (!(studio.selectedModels instanceof Set)) {
    studio.selectedModels = new Set();
    if (studio.selectedModel) studio.selectedModels.add(studio.selectedModel);
  }
  return studio.selectedModels;
}

function renderModelsPage() {
  const wrap = el("div", "studio-form");
  const toolbar = el("div", "side-actions");
  const providerBox = input(studio.selectedProvider, {
    select: true,
    options: (studio.model.providers || []).map((item) => [item.profile_id, item.display_name]),
  });
  providerBox.addEventListener("change", () => {
    studio.selectedProvider = providerBox.value;
    renderModelStudio();
  });
  const search = input("", { placeholder: "搜索模型" });
  const hint = el("p", "studio-note", "");
  const tableHost = el("div", "studio-scroll");
  const selected = selectedModelSet();

  function updateHint(visible) {
    const count = selected.size;
    hint.textContent =
      count > 1
        ? `已选 ${count} 个。Shift 连选，Ctrl 点选；「启用 / 停用」会对选中项一起生效。`
        : "单击选一个，按住 Shift 再点可选一段。模型很多时，适合先圈一段再停用。";
    if (visible) hint.textContent += ` 当前列表 ${visible.length} 条。`;
  }

  const draw = () => {
    const visible = visibleCatalogModels(search.value);
    tableHost.innerHTML = "";
    const table = el("table", "table");
    table.innerHTML = "<thead><tr><th>提供商</th><th>模型</th><th>来源</th><th>状态</th></tr></thead>";
    const tbody = document.createElement("tbody");
    visible.forEach((model, index) => {
      const provider = providerById(model.provider_profile_id);
      const row = document.createElement("tr");
      if (selected.has(model.model_ref)) row.className = "active";
      row.innerHTML = `<td>${escapeHtml(provider?.display_name || model.provider_profile_id)}</td><td>${escapeHtml(model.display_name || model.model_id)}</td><td>${model.source === "manual" ? "手工" : "目录"}</td><td>${model.enabled === false ? "停用" : "启用"}</td>`;
      row.addEventListener("mousedown", (event) => {
        if (event.shiftKey) event.preventDefault();
      });
      row.addEventListener("click", (event) => {
        const refs = visible.map((item) => item.model_ref);
        if (event.shiftKey && studio.modelAnchor) {
          const from = refs.indexOf(studio.modelAnchor);
          const to = index;
          if (from >= 0) {
            const start = Math.min(from, to);
            const end = Math.max(from, to);
            if (!event.ctrlKey && !event.metaKey) selected.clear();
            refs.slice(start, end + 1).forEach((ref) => selected.add(ref));
          }
        } else if (event.ctrlKey || event.metaKey) {
          if (selected.has(model.model_ref)) selected.delete(model.model_ref);
          else selected.add(model.model_ref);
          studio.modelAnchor = model.model_ref;
        } else {
          selected.clear();
          selected.add(model.model_ref);
          studio.modelAnchor = model.model_ref;
        }
        studio.selectedModel = model.model_ref;
        draw();
      });
      tbody.append(row);
    });
    table.append(tbody);
    tableHost.append(table);
    updateHint(visible);
  };
  search.addEventListener("input", draw);
  const refresh = el("button", "btn quiet", "刷新模型");
  refresh.type = "button";
  refresh.addEventListener("click", () => refreshSelectedModels());
  const add = el("button", "btn quiet", "手工添加模型");
  add.type = "button";
  add.addEventListener("click", () => addManualModel());
  const toggle = el("button", "btn quiet", "启用 / 停用");
  toggle.type = "button";
  toggle.addEventListener("click", async () => {
    const refs = [...selectedModelSet()];
    if (!refs.length) return toast("请先选择模型。Shift 连选可一次圈一段。");
    const chosen = (studio.model.models || []).filter((item) => refs.includes(item.model_ref));
    const enable = chosen.length > 0 && chosen.every((item) => item.enabled === false);
    try {
      studio.model = await call("set_models_enabled", refs, enable);
      renderModelStudio();
      toast(enable ? `已启用 ${refs.length} 个模型。` : `已停用 ${refs.length} 个模型。`);
    } catch (error) {
      toast(error.message);
    }
  });
  toolbar.append(field("提供商", providerBox), field("搜索", search));
  wrap.append(toolbar, (() => {
    const row = el("div", "side-actions");
    row.append(refresh, add, toggle);
    return row;
  })(), hint, tableHost);
  draw();
  return wrap;
}

function addManualModel() {
  if (!studio.selectedProvider) return toast("请先选择接入商。");
  const modelId = input("");
  const display = input("");
  openModal({
    title: "手工添加模型",
    desc: "用于目录里还没有、但接口已经支持的模型 ID。",
    body: (() => {
      const wrap = document.createElement("div");
      wrap.append(field("模型 ID", modelId), field("显示名称（可留空）", display));
      return wrap;
    })(),
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "添加",
        style: "primary",
        onClick: async () => {
          try {
            studio.model = await call("add_model", studio.selectedProvider, modelId.value.trim(), display.value.trim());
            closeModal();
            renderModelStudio();
            toast("手工模型已添加。");
          } catch (error) {
            toast(error.message);
          }
        },
      },
    ],
  });
}

function enabledModelOptions() {
  return (studio.model.models || [])
    .filter((item) => item.enabled !== false)
    .map((item) => {
      const provider = providerById(item.provider_profile_id);
      const label = `${provider?.display_name || item.provider_profile_id} · ${item.display_name || item.model_id} [${item.model_id}]`;
      return [item.model_ref, label];
    });
}

function filterModelOptions(options, query) {
  const terms = String(query || "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (!terms.length) return options;
  return options.filter(([, label]) => {
    const hay = String(label || "").toLowerCase();
    return terms.every((term) => hay.includes(term));
  });
}

function searchSelect(options, attrs = {}) {
  const wrap = el("div", "search-select");
  const box = input("", { placeholder: attrs.placeholder || "输入关键词筛选，例如 deep" });
  const list = el("div", "search-select-list");
  list.hidden = true;
  let selected = attrs.value || "";
  let disabled = false;

  function labelFor(value) {
    const hit = options.find(([key]) => key === value);
    return hit ? hit[1] : "";
  }

  function closeList() {
    list.hidden = true;
  }

  function pick(key) {
    selected = key;
    box.value = labelFor(key);
    closeList();
  }

  function placeList() {
    const rect = box.getBoundingClientRect();
    list.style.position = "fixed";
    list.style.left = `${rect.left}px`;
    list.style.width = `${rect.width}px`;
    list.style.top = `${rect.bottom + 4}px`;
    list.style.right = "auto";
  }

  function renderList(query) {
    if (disabled) return;
    const rows = filterModelOptions(options, query);
    list.innerHTML = "";
    if (!rows.length) {
      list.append(el("div", "search-select-empty", "没有匹配的模型"));
    } else {
      rows.slice(0, 80).forEach(([key, label]) => {
        const item = el("button", `search-select-item${key === selected ? " active" : ""}`);
        item.type = "button";
        item.textContent = label;
        item.addEventListener("mousedown", (event) => {
          event.preventDefault();
          pick(key);
        });
        list.append(item);
      });
    }
    placeList();
    list.hidden = false;
  }

  box.addEventListener("focus", () => renderList(box.value === labelFor(selected) ? "" : box.value));
  box.addEventListener("click", () => renderList(box.value === labelFor(selected) ? "" : box.value));
  box.addEventListener("input", () => {
    selected = "";
    renderList(box.value);
  });
  box.addEventListener("blur", () => {
    window.setTimeout(closeList, 120);
  });
  box.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeList();
      return;
    }
    if (event.key === "Enter") {
      const first = list.querySelector(".search-select-item");
      if (first) {
        event.preventDefault();
        first.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      }
    }
  });

  if (selected) box.value = labelFor(selected);
  wrap.append(box, list);
  Object.defineProperty(wrap, "value", {
    get() {
      return selected;
    },
    set(next) {
      pick(next || "");
    },
  });
  Object.defineProperty(wrap, "disabled", {
    get() {
      return disabled;
    },
    set(next) {
      disabled = Boolean(next);
      box.disabled = disabled;
      if (disabled) closeList();
    },
  });
  return wrap;
}

function renderAssignPage() {
  const wrap = el("div", "studio-form");
  const options = enabledModelOptions();
  const primary = searchSelect(options, {
    value: studio.model.primary_model_ref || "",
    placeholder: "输入关键词筛选主模型，例如 deep",
  });
  wrap.append(
    el("p", "studio-note", "在框里输入 deep、flash 这类词就能筛模型，点选一条后保存。“使用主模型”会跟着主模型变；“单独指定”只改这一项。"),
    field("主模型", primary)
  );
  const rows = {};
  (studio.model.features || []).forEach((feature) => {
    const assignment = studio.model.feature_assignments?.[feature.id] || {};
    const mode = input(assignment.mode === "model" ? "model" : "inherit", {
      select: true,
      options: [
        ["inherit", "使用主模型"],
        ["model", "单独指定"],
      ],
    });
    const model = searchSelect(options, {
      value: assignment.model_ref || "",
      placeholder: "单独指定时，输入关键词筛选",
    });
    model.disabled = mode.value !== "model";
    mode.addEventListener("change", () => {
      model.disabled = mode.value !== "model";
    });
    const row = el("div", "assign-row");
    row.append(el("strong", "", feature.label), mode, model);
    wrap.append(row);
    rows[feature.id] = { mode, model };
  });
  const save = el("button", "btn primary", "保存功能分配");
  save.type = "button";
  save.addEventListener("click", async () => {
    const assignments = {};
    Object.entries(rows).forEach(([featureId, row]) => {
      assignments[featureId] = {
        mode: row.mode.value,
        model_ref: row.mode.value === "model" ? row.model.value : "",
      };
    });
    try {
      studio.model = await call("save_assignments", {
        primary_model_ref: primary.value,
        feature_assignments: assignments,
      });
      setStudioStatus("主模型和功能分配已保存。");
      renderModelStudio();
      if (state.projectId) loadOverview(state.projectId).catch(() => {});
      toast("功能分配已保存。");
    } catch (error) {
      toast(error.message);
    }
  });
  wrap.append(save);
  return wrap;
}

async function openMemoryStudio() {
  if (!requireProject()) return;
  studio.mode = "memory";
  studio.memoryEditor = null;
  studio.memoryTarget = null;
  studio.memoryEnabled = null;
  studio.memoryLive = null;
  studio.memoryBusy = false;
  studio.memoryLiveText = "";
  openStudioShell({ kicker: currentProject()?.title || state.projectId, title: "记忆库" });
  $("studioTabs").innerHTML = "";
  studio.memory = await call("memory_state", state.projectId);
  studio.checked = new Set(studio.memory.recommended || []);
  renderMemoryStudio();
}

function renderMemoryStudio() {
  const data = studio.memory;
  const keepText = studio.memoryEditor ? studio.memoryEditor.value : (data.memory?.text || "");
  const keepTarget = studio.memoryTarget ? studio.memoryTarget.value : String(data.target_tokens || 5000);
  const keepEnabled = studio.memoryEnabled ? studio.memoryEnabled.checked : data.memory?.enabled !== false;
  const wrap = el("div", "studio-grid wide-left");
  const list = el("div", "studio-list");
  list.append(el("h3", "", "已确认章节"), el("p", "studio-note", data.progress || ""));
  const picks = el("div", "side-actions");
  const rec = el("button", "btn quiet compact", "勾选建议");
  rec.type = "button";
  rec.addEventListener("click", () => {
    studio.checked = new Set(data.recommended || []);
    renderMemoryStudio();
  });
  const all = el("button", "btn quiet compact", "全选");
  all.type = "button";
  all.addEventListener("click", () => {
    studio.checked = new Set((data.chapters || []).map((item) => item.chapter_id));
    renderMemoryStudio();
  });
  const none = el("button", "btn quiet compact", "清空");
  none.type = "button";
  none.addEventListener("click", () => {
    studio.checked = new Set();
    renderMemoryStudio();
  });
  picks.append(rec, all, none);
  list.append(picks);
  const scroll = el("div", "studio-scroll");
  (data.chapters || []).forEach((chapter) => {
    const row = el("label", `check-row${studio.checked.has(chapter.chapter_id) ? " active" : ""}`);
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = studio.checked.has(chapter.chapter_id);
    box.addEventListener("change", () => {
      if (box.checked) studio.checked.add(chapter.chapter_id);
      else studio.checked.delete(chapter.chapter_id);
      renderMemoryStudio();
    });
    row.append(box, document.createTextNode(`${chapter.label}  ${chapter.title || ""}`));
    scroll.append(row);
  });
  if (!(data.chapters || []).length) scroll.append(el("p", "studio-note", "还没有已确认章节。先确认稿件后再更新记忆。"));
  list.append(scroll);

  const form = el("div", "studio-form");
  const target = input(keepTarget);
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = keepEnabled;
  const enabledRow = el("label", "check-row");
  enabledRow.append(enabled, document.createTextNode("把记忆银行加入生成上下文"));
  const editor = document.createElement("textarea");
  editor.className = "studio-editor";
  editor.value = keepText;
  editor.addEventListener("scroll", () => {
    studio.followMemory = editor.scrollTop + editor.clientHeight >= editor.scrollHeight - 48;
  });
  studio.memoryEditor = editor;
  studio.memoryTarget = target;
  studio.memoryEnabled = enabled;
  const advice = el("div", "studio-note", data.token_advice || "");
  const live = el("pre", "studio-live");
  live.textContent = studio.memoryLiveText || "";
  live.hidden = !studio.memoryLiveText && !studio.memoryBusy;
  studio.memoryLive = live;
  const actions = el("div", "side-actions wrap");
  const inspect = el("div", "side-actions wrap");
  const save = el("button", "btn primary", "保存记忆");
  save.type = "button";
  save.addEventListener("click", () => saveMemoryStudio());
  const generate = el("button", "btn accent", "按勾选章节生成");
  generate.type = "button";
  generate.addEventListener("click", () => runMemoryJob("generate_memory", "正在根据勾选章节生成记忆…"));
  const compress = el("button", "btn quiet", "压缩当前记忆");
  compress.type = "button";
  compress.addEventListener("click", () => runMemoryJob("compress_memory", "正在压缩记忆正文…"));
  const reload = el("button", "btn quiet", "从磁盘重新加载");
  reload.type = "button";
  reload.addEventListener("click", () => reloadMemoryStudio());
  const saved = el("button", "btn quiet", "查看已保存记忆");
  saved.type = "button";
  saved.addEventListener("click", () => showSavedMemory());
  const promptPreview = el("button", "btn quiet", "查看更新提示词");
  promptPreview.type = "button";
  promptPreview.addEventListener("click", () => previewMemory("generate", "prompt"));
  const requestPreview = el("button", "btn quiet", "查看发送结构");
  requestPreview.type = "button";
  requestPreview.addEventListener("click", () => previewMemory("generate", "request"));
  const compressPreview = el("button", "btn quiet", "查看缩写提示词");
  compressPreview.type = "button";
  compressPreview.addEventListener("click", () => previewMemory("compress", "prompt"));
  const contextPreview = el("button", "btn quiet", "查看生成上下文");
  contextPreview.type = "button";
  contextPreview.addEventListener("click", () => showContextPreview(state.projectId));
  actions.append(save, generate, compress);
  inspect.append(reload, saved, promptPreview, requestPreview, compressPreview, contextPreview);
  form.append(
    el("p", "studio-note", "勾选本次要合并进记忆银行的已确认章节。右侧正文来自当前项目已保存记忆；生成失败不会清空它。"),
    field("记忆目标 tokens", target),
    advice,
    enabledRow,
    editor,
    live,
    actions,
    inspect
  );
  wrap.append(list, form);
  const body = $("studioBody");
  body.innerHTML = "";
  body.append(wrap);
}

async function saveMemoryStudio() {
  if (!studio.memoryEditor) return;
  try {
    studio.memory = await call("save_memory_workspace", {
      project_id: state.projectId,
      memory_id: studio.memory.memory?.memory_id || "main_memory_bank",
      text: studio.memoryEditor.value,
      chapter_ids: [...studio.checked],
      target_tokens: studio.memoryTarget.value,
      enabled: studio.memoryEnabled.checked,
    });
    studio.checked = new Set();
    renderMemoryStudio();
    loadOverview(state.projectId).catch(() => {});
    toast("记忆库已保存。");
  } catch (error) {
    toast(error.message);
  }
}

function memoryJobPayload() {
  return {
    project_id: state.projectId,
    chapter_ids: [...studio.checked],
    current_memory: studio.memoryEditor?.value || studio.memory?.memory?.text || "",
    target_tokens: studio.memoryTarget?.value,
  };
}

function formatSavedMemory(data) {
  const items = data?.items || (data?.memory ? [data.memory] : []);
  if (!items.length) return "当前项目还没有已保存的记忆条目。";
  return items
    .map((item, index) => {
      const text = String(item.text || "").trim() || "（暂无正文）";
      return [
        `${index + 1}. ${item.title || item.memory_id || "记忆条目"}`,
        `状态=${item.status || "-"}  字数=${item.text_chars ?? text.length}  更新=${item.updated_at || "-"}`,
        `来源章节=${(item.source_chapter_ids || []).join("、") || "未记录"}`,
        "",
        text,
      ].join("\n");
    })
    .join("\n\n");
}

async function reloadMemoryStudio() {
  if (!requireProject()) return;
  try {
    studio.memoryEditor = null;
    studio.memory = await call("memory_state", state.projectId);
    studio.checked = new Set(studio.memory.recommended || []);
    studio.memoryLiveText = "";
    studio.memoryBusy = false;
    renderMemoryStudio();
    toast("已从磁盘重新加载已保存记忆。");
  } catch (error) {
    toast(error.message);
  }
}

async function showSavedMemory() {
  try {
    const data = await call("memory_state", state.projectId);
    studio.memory = data;
    openDrawer({
      kicker: currentProject()?.title || state.projectId,
      title: "已保存记忆",
      content: formatSavedMemory(data),
      wide: true,
    });
  } catch (error) {
    toast(error.message);
  }
}

async function previewMemory(kind, view) {
  try {
    const name = kind === "compress" ? "preview_memory_compression" : "preview_memory_generation";
    const result = await call(name, memoryJobPayload());
    openDrawer({
      kicker: "记忆库",
      title: view === "request" ? "API 发送结构" : kind === "compress" ? "缩写提示词" : "更新记忆提示词",
      content: view === "request" ? result.request_text : result.prompt_text,
      wide: true,
    });
  } catch (error) {
    toast(error.message);
  }
}

async function runMemoryJob(name, label) {
  if (!studio.memoryEditor) return;
  studio.followMemory = true;
  studio.memoryBackup = studio.memoryEditor.value;
  studio.memoryLiveText = "";
  studio.memoryBusy = true;
  if (studio.memoryLive) {
    studio.memoryLive.hidden = false;
    studio.memoryLive.textContent = "";
  }
  ThinkTrace.start();
  setStudioStatus(label || "请求已发出，正在等待模型接入…");
  try {
    await call(name, memoryJobPayload());
  } catch (error) {
    studio.memoryBusy = false;
    ThinkTrace.finish(false);
    if (studio.memoryEditor && studio.memoryBackup != null) {
      studio.memoryEditor.value = studio.memoryBackup;
    }
    setStudioStatus("");
    toast(error.message);
  }
}

function finishMemoryJob(payload) {
  if (studio.mode !== "memory") return;
  studio.memoryBusy = false;
  ThinkTrace.finish(payload?.ok !== false);
  if (!payload?.ok) {
    if (studio.memoryEditor && studio.memoryBackup != null) {
      studio.memoryEditor.value = studio.memoryBackup;
    }
    setStudioStatus("记忆生成失败。已保留当前记忆正文。");
    toast(payload?.error || "记忆生成失败");
    return;
  }
  const text = payload.data?.text || studio.memoryLiveText || "";
  if (studio.memoryEditor && text) {
    studio.memoryEditor.value = text;
  }
  studio.memoryLiveText = "";
  if (studio.memoryLive) {
    studio.memoryLive.textContent = "";
    studio.memoryLive.hidden = true;
  }
  setStudioStatus("AI 已生成记忆正文，请审阅后保存。");
  toast("记忆正文已生成，尚未保存。");
}

async function openPlanningStudio(kind) {
  if (!requireProject()) return;
  studio.mode = kind;
  studio.creating = false;
  studio.selectedPlanning = "";
  openStudioShell({
    kicker: currentProject()?.title || state.projectId,
    title: kind === "outline" ? "大纲与章节" : "世界观与人物",
  });
  $("studioTabs").innerHTML = "";
  studio.planning = await call("planning_state", state.projectId, kind);
  const first = studio.planning.items?.[0];
  if (first) studio.selectedPlanning = first.planning_id;
  renderPlanningStudio();
}

function planningItem(id) {
  return (studio.planning?.items || []).find((item) => item.planning_id === id) || null;
}

function renderPlanningStudio() {
  const kind = studio.mode;
  const wrap = el("div", "studio-grid");
  const list = el("div", "studio-list");
  list.append(el("h3", "", kind === "outline" ? "阶段资料" : "资料条目"));
  const scroll = el("div", "studio-scroll");
  (studio.planning.items || []).forEach((item) => {
    const active = item.enabled !== false && Boolean(item.active);
    const typeLabel = (studio.planning.types || []).find((entry) => entry.id === item.item_type)?.label || item.item_type;
    const button = el("button", `choice${item.planning_id === studio.selectedPlanning && !studio.creating ? " active" : ""}`);
    button.type = "button";
    button.innerHTML = `<span class="tree-title">${active ? "☑" : "☐"} ${escapeHtml(typeLabel)} ${escapeHtml(item.title || item.planning_id)}</span>`;
    button.addEventListener("click", () => {
      studio.creating = false;
      studio.selectedPlanning = item.planning_id;
      renderPlanningStudio();
    });
    scroll.append(button);
  });
  if (!(studio.planning.items || []).length) scroll.append(el("p", "studio-note", "还没有资料。右侧可以直接新建。"));
  list.append(scroll);

  const actions = el("div", "side-actions");
  (studio.planning.types || []).forEach((type) => {
    const button = el("button", "btn quiet compact", type.id === "outline" || type.id === "world_plan" ? `编辑${type.label}` : `新增${type.label}`);
    button.type = "button";
    button.addEventListener("click", () => startPlanning(type.id));
    actions.append(button);
  });
  list.append(actions);

  const form = el("div", "studio-form");
  const current = studio.creating ? { item_type: studio.createType, adherence_level: "balanced", enabled: true, active: true } : planningItem(studio.selectedPlanning) || {};
  const typeBox = input(current.item_type || studio.planning.types[0].id, {
    select: true,
    options: (studio.planning.types || []).map((item) => [item.id, item.label]),
  });
  typeBox.disabled = !studio.creating;
  const title = input(current.title || "");
  const ident = input(current.planning_id || "");
  ident.readOnly = true;
  const range = input(current.chapter_range || "", { placeholder: "例如 01-05" });
  const adherence = input(current.adherence_level || "balanced", {
    select: true,
    options: (studio.planning.adherence || []).map((item) => [item.id, item.label]),
  });
  const active = document.createElement("input");
  active.type = "checkbox";
  active.checked = current.enabled !== false && current.active !== false;
  const activeRow = el("label", "check-row");
  activeRow.append(active, document.createTextNode("加入生成上下文"));
  const editor = document.createElement("textarea");
  editor.className = "studio-editor";
  editor.value = current.text || "";
  studio.planForm = { typeBox, title, ident, range, adherence, active, editor };
  const save = el("button", "btn primary", "保存当前");
  save.type = "button";
  save.addEventListener("click", () => savePlanningStudio());
  const remove = el("button", "btn quiet", "删除");
  remove.type = "button";
  remove.disabled = studio.creating || !studio.selectedPlanning;
  remove.addEventListener("click", () => deletePlanningStudio());
  const row = el("div", "side-actions");
  row.append(save, remove);
  form.append(
    el("p", "studio-note", kind === "outline" ? "这里只管理总纲和章节计划。保存资料本身不会调用模型。" : "人物、世界观和约束可以逐条编辑。保存不会调用模型。"),
    field("资料类型", typeBox),
    field("标题", title),
    field("内部编号", ident),
    field("章节范围", range),
    field("参考强度", adherence),
    activeRow,
    editor,
    row
  );
  wrap.append(list, form);
  const body = $("studioBody");
  body.innerHTML = "";
  body.append(wrap);
}

async function startPlanning(itemType) {
  const existing = (studio.planning.items || []).find((item) => item.item_type === itemType);
  if ((itemType === "outline" || itemType === "world_plan") && existing) {
    studio.creating = false;
    studio.selectedPlanning = existing.planning_id;
    renderPlanningStudio();
    return;
  }
  const created = await call("new_planning_id", itemType);
  studio.creating = true;
  studio.createType = itemType;
  studio.selectedPlanning = created.planning_id;
  renderPlanningStudio();
  if (studio.planForm) studio.planForm.ident.value = created.planning_id;
}

async function savePlanningStudio() {
  const form = studio.planForm;
  if (!form) return;
  try {
    const result = await call("save_planning", {
      project_id: state.projectId,
      planning_id: form.ident.value.trim(),
      creating: studio.creating,
      item_type: form.typeBox.value,
      title: form.title.value.trim(),
      text: form.editor.value,
      active: form.active.checked,
      adherence_level: form.adherence.value,
      chapter_range: form.range.value.trim(),
    });
    studio.planning = result;
    studio.creating = false;
    studio.selectedPlanning = result.saved_id || form.ident.value.trim();
    renderPlanningStudio();
    loadOverview(state.projectId).catch(() => {});
    toast("资料已保存。");
  } catch (error) {
    toast(error.message);
  }
}

async function deletePlanningStudio() {
  if (studio.creating || !studio.selectedPlanning) return;
  try {
    studio.planning = await call("delete_planning", state.projectId, studio.selectedPlanning, studio.mode);
    studio.selectedPlanning = studio.planning.items?.[0]?.planning_id || "";
    renderPlanningStudio();
    loadOverview(state.projectId).catch(() => {});
    toast("资料已删除。");
  } catch (error) {
    toast(error.message);
  }
}

function handleStudioPush(event, payload) {
  if (event === "models_done") {
    if (!payload?.ok) {
      setStudioStatus("刷新失败。");
      toast(payload?.error || "刷新模型失败");
      return;
    }
    studio.model = payload.data || studio.model;
    setStudioStatus(`模型目录已刷新：${payload.data?.refresh?.model_count || 0} 个模型。`);
    if (studio.mode === "models") renderModelStudio();
    if (state.projectId) loadOverview(state.projectId).catch(() => {});
  }
  if (event === "memory_chunk") {
    studio.memoryLiveText = (studio.memoryLiveText || "") + (payload?.text || "");
    if (studio.memoryLive) {
      studio.memoryLive.hidden = false;
      studio.memoryLive.textContent = studio.memoryLiveText;
      if (studio.followMemory) {
        studio.memoryLive.scrollTo({ top: studio.memoryLive.scrollHeight, behavior: "smooth" });
      }
    }
  }
  if (event === "memory_done") finishMemoryJob(payload);
}

async function saveActiveStudio() {
  if (studio.mode === "memory") return saveMemoryStudio();
  if (studio.mode === "outline" || studio.mode === "world") return savePlanningStudio();
  if (studio.mode === "gen") return saveGenSettings();
}

async function openGenSettings(scope) {
  if (scope === "project" && !requireProject()) return;
  studio.mode = "gen";
  studio.genScope = scope;
  studio.genTab = studio.genTab || "prompt";
  openStudioShell({
    kicker: scope === "project" ? currentProject()?.title || state.projectId : "全局默认",
    title: scope === "project" ? "项目专属创作设置" : "全局创作设置",
  });
  studio.gen = await call("generation_settings_state", scope, state.projectId || "");
  renderGenSettings();
}

function renderGenSettings() {
  const settings = studio.gen.settings || studio.gen;
  const prompting = settings.prompting || {};
  const sampling = settings.sampling || {};
  const context = settings.context || {};
  const review = settings.review || {};
  renderTabs(
    [
      ["prompt", "提示词"],
      ["sample", "采样与上下文"],
      ["review", "审稿"],
    ],
    studio.genTab,
    (tab) => {
      collectGenForm();
      studio.genTab = tab;
      renderGenSettings();
    }
  );
  const body = $("studioBody");
  body.innerHTML = "";
  const form = el("div", "studio-form");
  if (studio.genTab === "prompt") {
    const system = input(prompting.system_prompt || "", { area: true });
    const user = input(prompting.default_user_prompt || "", { area: true });
    system.className = "studio-editor";
    user.className = "studio-editor";
    system.style.minHeight = "160px";
    user.style.minHeight = "120px";
    form.append(
      el("p", "studio-note", studio.genScope === "project" ? "保存到当前作品，优先于全局默认。" : "全局默认。某本小说要单独设置时，在作品上右键打开“项目专属设置”。"),
      field("系统提示词", system),
      field("默认写作要求", user)
    );
    studio.genFields = { system, user };
  } else if (studio.genTab === "sample") {
    const keys = [
      ["temperature", "Temperature", sampling.temperature],
      ["top_p", "Top P", sampling.top_p],
      ["top_k", "Top K", sampling.top_k],
      ["min_p", "Min P", sampling.min_p],
      ["max_tokens", "Max Tokens", sampling.max_tokens],
      ["presence_penalty", "Presence Penalty", sampling.presence_penalty],
      ["frequency_penalty", "Frequency Penalty", sampling.frequency_penalty],
      ["repetition_penalty", "Repetition Penalty", sampling.repetition_penalty],
      ["max_context_tokens", "上下文 Token 上限", context.max_context_tokens],
      ["recent_confirmed_chapter_count", "自动带入前文章数", context.recent_confirmed_chapter_count],
    ];
    studio.genFields = {};
    keys.forEach(([id, label, value]) => {
      const box = input(value == null ? "" : String(value));
      form.append(field(label, box));
      studio.genFields[id] = box;
    });
    const stream = document.createElement("input");
    stream.type = "checkbox";
    stream.checked = Boolean(sampling.stream);
    const recent = document.createElement("input");
    recent.type = "checkbox";
    recent.checked = context.include_recent_chapters !== false;
    const row1 = el("label", "check-row");
    row1.append(stream, document.createTextNode("请求流式输出"));
    const row2 = el("label", "check-row");
    row2.append(recent, document.createTextNode("生成时带入前文片段"));
    form.append(row1, row2, el("p", "studio-note", "这些只影响写作采样。API 地址和 Key 在模型设置里。"));
    studio.genFields.stream = stream;
    studio.genFields.include_recent_chapters = recent;
  } else {
    const enabled = document.createElement("input");
    enabled.type = "checkbox";
    enabled.checked = Boolean(review.scorer_enabled);
    const row = el("label", "check-row");
    row.append(enabled, document.createTextNode("启用评分模型辅助审稿"));
    const system = input(review.system_prompt || "", { area: true });
    const task = input(review.task_prompt || "", { area: true });
    system.className = "studio-editor";
    task.className = "studio-editor";
    form.append(
      row,
      el("p", "studio-note", "关闭时确认稿不需要评分模型。开启后，AI 审稿会调用模型设置里的审稿角色。"),
      field("审稿系统提示词", system),
      field("AI审稿提示词（可用 {chapter_heading}、{chapter_id}、{title}）", task)
    );
    studio.genFields = { enabled, system, task };
  }
  const actions = el("div", "side-actions");
  const save = el("button", "btn primary", studio.genScope === "project" ? "保存项目设置" : "保存全局设置");
  save.type = "button";
  save.addEventListener("click", () => saveGenSettings());
  const reset = el("button", "btn quiet", studio.genScope === "project" ? "清除项目覆盖" : "恢复出厂默认");
  reset.type = "button";
  reset.addEventListener("click", () => resetGenSettings());
  actions.append(save, reset);
  form.append(actions);
  body.append(form);
}

function collectGenForm() {
  if (!studio.gen || !studio.genFields) return;
  if (!studio.gen.settings) studio.gen.settings = studio.gen;
  const settings = studio.gen.settings;
  settings.prompting = settings.prompting || {};
  settings.sampling = settings.sampling || {};
  settings.context = settings.context || {};
  settings.review = settings.review || {};
  const fields = studio.genFields;
  if (fields.system && studio.genTab === "prompt") {
    settings.prompting.system_prompt = fields.system.value;
    settings.prompting.default_user_prompt = fields.user.value;
  }
  if (fields.temperature) {
    [
      "temperature",
      "top_p",
      "top_k",
      "min_p",
      "max_tokens",
      "presence_penalty",
      "frequency_penalty",
      "repetition_penalty",
    ].forEach((key) => {
      settings.sampling[key] = fields[key].value;
    });
    settings.context.max_context_tokens = fields.max_context_tokens.value;
    settings.context.recent_confirmed_chapter_count = fields.recent_confirmed_chapter_count.value;
    settings.sampling.stream = fields.stream.checked;
    settings.context.include_recent_chapters = fields.include_recent_chapters.checked;
  }
  if (fields.enabled && studio.genTab === "review") {
    settings.review.scorer_enabled = fields.enabled.checked;
    settings.review.system_prompt = fields.system.value;
    settings.review.task_prompt = fields.task.value;
  }
}

async function saveGenSettings() {
  collectGenForm();
  await call("save_generation_settings", {
    scope: studio.genScope,
    project_id: state.projectId || "",
    settings: studio.gen.settings || studio.gen,
  });
  setStudioStatus("创作设置已保存。");
  toast("创作设置已保存。");
}

async function resetGenSettings() {
  const updated = await call("reset_generation_settings", studio.genScope, state.projectId || "");
  studio.gen = { ...(studio.gen || {}), settings: updated };
  renderGenSettings();
  toast(studio.genScope === "project" ? "已改用全局默认。" : "已恢复出厂默认。");
}

async function openRecordsStudio(kind = "connection") {
  const pages = [
    ["connection", "连接检查", true],
    ["confirmed", "已确认章节", true],
    ["chapters", "章节列表", true],
    ["reviews", "审稿与改写", true],
    ["checklist", "出稿清单", true],
    ["export", "导出设置", true],
    ["calls", "模型调用记录", true],
    ["guide", "使用说明", false],
    ["run_log", "运行记录", false],
    ["diagnostics", "开发者诊断", false],
  ];
  const page = pages.find((item) => item[0] === kind) || pages[0];
  if (page[2] && !requireProject()) return;
  studio.mode = "records";
  studio.recordsKind = page[0];
  openStudioShell({
    kicker: page[2] ? currentProject()?.title || state.projectId : "帮助",
    title: "记录与诊断",
  });
  $("studioTabs").innerHTML = "";
  studio.records = await call("records_state", studio.recordsKind, state.projectId || "");
  renderRecordsStudio();
}

function renderRecordsStudio() {
  const data = studio.records || {};
  const pages = data.pages || [];
  const wrap = el("div", "studio-grid");
  const list = el("div", "studio-list");
  list.append(el("h3", "", "记录"));
  const scroll = el("div", "studio-scroll");
  pages.forEach((page) => {
    const button = el("button", `choice${page.id === studio.recordsKind ? " active" : ""}`);
    button.type = "button";
    button.textContent = page.label;
    button.addEventListener("click", () => openRecordsStudio(page.id).catch((error) => toast(error.message)));
    scroll.append(button);
  });
  list.append(scroll);

  const form = el("div", "studio-form");
  form.append(el("h3", "", data.title || "记录"), el("p", "studio-note", "这里只展示本地记录。开发者诊断会扫描项目库，不会调用模型。"));
  const body = el("pre", "studio-records");
  body.textContent = data.details || "暂无记录。";
  form.append(body);
  const actions = el("div", "side-actions wrap");
  const refresh = el("button", "btn quiet", "刷新");
  refresh.type = "button";
  refresh.addEventListener("click", () => openRecordsStudio(studio.recordsKind).catch((error) => toast(error.message)));
  actions.append(refresh);
  if (studio.recordsKind === "confirmed" || studio.recordsKind === "export") {
    const exportBtn = el("button", "btn primary", "导出 TXT");
    exportBtn.type = "button";
    exportBtn.addEventListener("click", async () => {
      try {
        await call("export_txt", state.projectId);
        toast("TXT 已导出。");
      } catch (error) {
        if (!error.cancelled) toast(error.message);
      }
    });
    actions.append(exportBtn);
  }
  form.append(actions);
  wrap.append(list, form);
  const host = $("studioBody");
  host.innerHTML = "";
  host.append(wrap);
}
