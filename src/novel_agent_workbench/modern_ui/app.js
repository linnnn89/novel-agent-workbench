const FONTS = {
  literary: { label: "衬线文学体", value: "var(--font-literary)" },
  sans: { label: "现代黑体", value: "var(--font-sans)" },
  kai: { label: "楷体手感", value: "var(--font-kai)" },
  mono: { label: "等宽草稿", value: "var(--font-mono)" },
};

const ICONS = {
  refresh: '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
  close: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  chevronRight: '<polyline points="9 18 15 12 9 6"/>',
  chevronDown: '<polyline points="6 9 12 15 18 9"/>',
};

function iconSvg(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

const CHAPTER_GROUP_SIZE = 10;

const state = {
  ready: false,
  workspace: [],
  prefs: { theme: "system", fontFamily: "literary", fontSize: 16, focusMode: false, hideInspector: false, editorWidth: "comfort" },
  inspectorTab: "chapter",
  hasReview: false,
  reviewBadge: false,
  reviewText: "",
  reviewNotice: "",
  model: null,
  lastSavedAt: 0,
  projectId: "",
  chapterId: "",
  closeAttempt: 0,
  closeEditorWasReadOnly: false,
  closing: false,
  draftId: "",
  draftIds: [],
  draftIndex: -1,
  generating: false,
  importing: false,
  follow: true,
  saveQueue: Promise.resolve(),
  saveTimer: 0,
  saveError: "",
  dirty: false,
  savedSnapshot: null,
  navigationId: 0,
  activeJobId: 0,
  lastJobId: 0,
  memoryReminders: [],
  memoryReminderShown: new Set(),
  inputBudgetNotice: null,
  inputBudgetRetry: null,
  projectsRoot: "",
  changingRoot: false,
  streamSource: null,
  streamProjectId: "",
  streamChapterId: "",
  treeOpen: { projects: Object.create(null), groups: Object.create(null) },
  treeSearchOpen: { projects: Object.create(null), groups: Object.create(null) },
};

const $ = (id) => document.getElementById(id);

function api() {
  return window.pywebview?.api;
}

async function call(name, ...args) {
  const bridge = api();
  if (!bridge || typeof bridge[name] !== "function") {
    throw new Error("界面桥接尚未就绪。");
  }
  const result = await bridge[name](...args);
  if (result && result.ok === false) {
    const error = new Error(result.error || "操作失败");
    error.cancelled = Boolean(result.cancelled);
    throw error;
  }
  return result?.data;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  requestAnimationFrame(() => el.classList.add("show"));
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => {
      el.hidden = true;
    }, 220);
  }, 2800);
}

function applyPrefs() {
  const root = document.documentElement;
  const theme = state.prefs.theme === "system"
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : state.prefs.theme;
  root.dataset.theme = theme;
  root.style.setProperty("--editor-font", (FONTS[state.prefs.fontFamily] || FONTS.literary).value);
  root.style.setProperty("--editor-size", `${Number(state.prefs.fontSize) || 18}px`);
  $("app").dataset.editorWidth = state.prefs.editorWidth === "fill" ? "fill" : "comfort";
  $("app").classList.toggle("focus-mode", Boolean(state.prefs.focusMode));
  $("app").classList.toggle("hide-inspector", Boolean(state.prefs.hideInspector));
  $("focusBtn").textContent = state.prefs.focusMode ? "退出专注" : "专注";
  const hideInspector = Boolean(state.prefs.hideInspector);
  const inspectorToggle = $("inspectorToggle");
  if (inspectorToggle) {
    inspectorToggle.setAttribute("aria-expanded", hideInspector ? "false" : "true");
    inspectorToggle.title = hideInspector ? "展开右侧面板" : "收起右侧面板";
  }
  const widthBtn = $("widthBtn");
  if (widthBtn) widthBtn.textContent = state.prefs.editorWidth === "fill" ? "铺满" : "舒适宽";
}

function countChars(text) {
  return Array.from(String(text || "").replace(/\s+/g, "")).length;
}

function formatCount(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function selectedEditorChars() {
  const editor = $("editor");
  if (!editor) return 0;
  const start = editor.selectionStart || 0;
  const end = editor.selectionEnd || 0;
  if (end <= start) return 0;
  return countChars(editor.value.slice(start, end));
}

function updateCountPill() {
  const chars = countChars($("editor").value);
  const selected = selectedEditorChars();
  const minutes = chars ? Math.max(1, Math.round(chars / 400)) : 0;
  let text = `本章 ${formatCount(chars)}`;
  if (minutes) text += ` · 约 ${minutes} 分钟`;
  if (selected) text += ` · 选中 ${formatCount(selected)}`;
  $("countPill").textContent = text;
}

function refreshSavePill() {
  if (state.generating) return;
  if (state.saveError) { $("savePill").textContent = "保存失败 · 请重试"; return; }
  if (state.dirty) { $("savePill").textContent = "尚有编辑未保存"; return; }
  if (!state.lastSavedAt) {
    $("savePill").textContent = "本地保存就绪";
    return;
  }
  const sec = Math.max(0, Math.round((Date.now() - state.lastSavedAt) / 1000));
  if (sec < 8) $("savePill").textContent = "已自动保存";
  else if (sec < 60) $("savePill").textContent = `${sec}秒前已保存`;
  else $("savePill").textContent = `${Math.max(1, Math.round(sec / 60))}分钟前已保存`;
}

function updateDock() {
  const busy = state.generating;
  ["cancelJobBtn", "cancelStudioJobBtn"].forEach(id => {
    const cancel = $(id);
    if (cancel) { cancel.hidden = !busy; cancel.disabled = false; cancel.textContent = "停止任务"; }
  });
  ["rewriteBtn", "reviewBtn", "confirmBtn", "newChapterBtn"].forEach((id) => {
    const button = $(id);
    if (button) button.disabled = busy;
  });
  const refine = $("refineBtn");
  if (refine) {
    refine.disabled = busy || !state.hasReview;
    refine.title = state.hasReview ? "" : "需要先完成 AI 审稿";
  }
}

function setBusy(busy, label, options = {}) {
  const lockEditor = options.lockEditor !== false;
  const veil = options.veil !== false;
  state.generating = busy;
  $("streamVeil").hidden = !(busy && veil);
  if (label) $("streamLabel").textContent = label;
  $("editor").readOnly = Boolean(busy && lockEditor);
  $("editor").removeAttribute("disabled");
  updateDock();
}

function writingModelRef(model) {
  const assignment = model?.feature_assignments?.draft_generation || {};
  if (assignment.mode === "model" && assignment.model_ref) return assignment.model_ref;
  return model?.primary_model_ref || "";
}

function findModelProfile(model, ref) {
  return (model?.models || []).find((item) => item.model_ref === ref) || null;
}

function shortModelName(model, ref) {
  const item = findModelProfile(model, ref);
  return item ? item.display_name || item.model_id || "" : "";
}

function enabledWritingModels(model) {
  const providers = model?.providers || [];
  return (model?.models || [])
    .filter((item) => item.enabled !== false)
    .map((item) => {
      const provider = providers.find((row) => row.profile_id === item.provider_profile_id);
      return {
        ...item,
        providerName: provider?.display_name || item.provider_profile_id || "",
      };
    });
}

function renderModelPill() {
  const pill = $("modelPill");
  if (!pill) return;
  const name = shortModelName(state.model, writingModelRef(state.model));
  let label = pill.querySelector(".model-pill-name");
  if (!label) {
    label = document.createElement("span");
    label.className = "model-pill-name";
    pill.replaceChildren(label);
  }
  label.textContent = name || "模型待配置";
  pill.classList.toggle("empty", !name);
  pill.title = name ? "切换正文生成模型" : "尚未配置正文模型，点击打开模型设置";
}

function syncModelState(data) {
  if (data) state.model = data;
  renderModelPill();
}

async function refreshModelPill() {
  try {
    state.model = await call("model_state");
  } catch (_error) {
    state.model = state.model || null;
  }
  renderModelPill();
}

function hideModelMenu() {
  const menu = $("modelMenu");
  if (!menu) return;
  menu.hidden = true;
  menu.innerHTML = "";
  const pill = $("modelPill");
  if (pill) pill.setAttribute("aria-expanded", "false");
}

function placeAnchorMenu(menu, anchor) {
  const rect = anchor.getBoundingClientRect();
  menu.hidden = false;
  const pad = 8;
  let left = rect.left;
  let top = rect.bottom + 6;
  left = Math.min(left, window.innerWidth - menu.offsetWidth - pad);
  left = Math.max(pad, left);
  if (top + menu.offsetHeight > window.innerHeight - pad) {
    top = Math.max(pad, rect.top - menu.offsetHeight - 6);
  }
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
}

async function toggleModelMenu() {
  const menu = $("modelMenu");
  const pill = $("modelPill");
  if (!menu || !pill) return;
  if (!menu.hidden) {
    hideModelMenu();
    return;
  }
  await refreshModelPill();
  menu.innerHTML = "";
  const current = writingModelRef(state.model);
  const models = enabledWritingModels(state.model);
  if (!models.length) {
    const empty = document.createElement("button");
    empty.type = "button";
    empty.textContent = "还没有可用模型，打开模型设置";
    empty.addEventListener("click", () => {
      hideModelMenu();
      openModelStudio().catch((error) => toast(error.message));
    });
    menu.append(empty);
  } else {
    models.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "menuitem");
      if (item.model_ref === current) button.className = "active";
      button.innerHTML = `<span class="tree-title">${escapeHtml(item.display_name || item.model_id)}</span><span class="pill">${escapeHtml(item.providerName)}</span>`;
      button.addEventListener("click", async () => {
        hideModelMenu();
        if (item.model_ref === current) return;
        try {
          await switchWritingModel(item.model_ref);
        } catch (error) {
          toast(error.message);
        }
      });
      menu.append(button);
    });
    menu.append(document.createElement("hr"));
    const more = document.createElement("button");
    more.type = "button";
    more.textContent = "打开模型设置";
    more.addEventListener("click", () => {
      hideModelMenu();
      openModelStudio().catch((error) => toast(error.message));
    });
    menu.append(more);
  }
  pill.setAttribute("aria-expanded", "true");
  placeAnchorMenu(menu, pill);
}

async function switchWritingModel(modelRef) {
  const model = state.model || (await call("model_state"));
  const assignments = { ...(model.feature_assignments || {}) };
  const draft = assignments.draft_generation || { mode: "inherit", model_ref: "" };
  if (draft.mode === "model") {
    assignments.draft_generation = { ...draft, mode: "model", model_ref: modelRef };
  }
  const currentPrimary = model.primary_model_ref || "";
  const primaryValid = (model.models || []).some(
    (item) => item.model_ref === currentPrimary && item.enabled !== false
  );
  const primary = draft.mode === "model" && primaryValid ? currentPrimary : modelRef;
  const data = await call("save_assignments", {
    primary_model_ref: primary,
    feature_assignments: assignments,
  });
  syncModelState(data);
  if (typeof studio !== "undefined" && studio.model) {
    studio.model = data;
    if (studio.mode === "models" && studio.tab === "assign") renderModelStudio();
  }
  toast("正文模型已切换。");
}

function setReviewBadge(on) {
  state.reviewBadge = Boolean(on);
  const badge = $("reviewBadge");
  if (badge) badge.hidden = !state.reviewBadge;
}

function closeModal() {
  const cancelled = state.modalCancel;
  state.modalCancel = null;
  $("modal").hidden = true;
  $("modalBody").innerHTML = "";
  $("modalFoot").innerHTML = "";
  cancelled?.();
}

function openModal({ title, desc, body, actions }) {
  if (state.modalCancel) closeModal();
  $("modalTitle").textContent = title;
  $("modalDesc").textContent = desc || "";
  $("modalBody").innerHTML = "";
  $("modalBody").append(body);
  $("modalFoot").innerHTML = "";
  actions.forEach((action) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn ${action.style || "quiet"}`;
    button.textContent = action.label;
    button.addEventListener("click", action.onClick);
    $("modalFoot").append(button);
  });
  $("modal").hidden = false;
}

function closeDrawer() {
  $("drawer").hidden = true;
}

function showInputBudgetNotice(report, projectId = state.projectId, retry = null) {
  if (!report || report.can_send || projectId !== state.projectId) return;
  state.inputBudgetNotice = { report, projectId, retry, sourceDraftId: state.draftId };
  const hardLimit = Boolean(report.model_limit_exceeded);
  $("inputBudgetTitle").textContent = hardLimit ? "完整材料超过模型容量" : "完整材料超过软件预算";
  $("inputBudgetMessage").textContent = hardLimit
    ? "提高软件 input 预算不能突破模型容量。请减少带入的前文、手工精简记忆，或在创作设置中降低预留输出。"
    : `完整材料超出软件 input 预算约 ${formatCount(report.over_budget_tokens)} tokens。请选择提高预算，或自行调整材料。`;
  const rows = [
    ["完整输入（估算）", `${formatCount(report.estimated_input_tokens)} tokens`],
    ["软件 input 预算", `${formatCount(report.configured_input_limit)} tokens`],
    ["预留输出", `${formatCount(report.output_token_budget)} tokens`],
    ["模型容量", report.model_context_limit ? `${formatCount(report.model_context_limit)} tokens` : "未知，以服务商限制为准"],
  ];
  const stats = $("inputBudgetStats");
  stats.replaceChildren();
  for (const [label, value] of rows) {
    const dt = document.createElement("dt"); dt.textContent = label;
    const dd = document.createElement("dd"); dd.textContent = value;
    stats.append(dt, dd);
  }
  $("raiseInputBudgetBtn").disabled = hardLimit;
  $("inputBudgetEntry").hidden = false;
  $("retryInputBudgetBtn").hidden = !retry;
  $("inputBudgetPanel").hidden = false;
}

async function retryInputBudget() {
  const notice = state.inputBudgetNotice;
  const retry = notice?.retry;
  if (!retry || notice.projectId !== state.projectId || blockIfGenerating()) return;
  if (notice.sourceDraftId !== state.draftId) return toast("当前稿件已切换，请从当前稿件重新发起任务。");
  if (studio.mode) return toast("请先保存并关闭当前编辑页，再重新检查发送。");
  if (!(await flushSave()).ok || blockIfGenerating()) return;
  $("inputBudgetPanel").hidden = true;
  if (retry.method === "ai_review") return reviewDraft();
  state.inputBudgetRetry = retry;
  beginStream(retry.projectId, retry.chapterId, retry.title);
  try {
    await call(retry.method, ...retry.args);
  } catch (error) {
    await finishDraft({ ok: false, error: error.message });
  }
}

async function adjustInputBudget(kind) {
  const notice = state.inputBudgetNotice;
  if (!notice || notice.projectId !== state.projectId || blockIfGenerating()) return;
  const targetOpen = kind === "memory" ? studio.mode === "memory" : studio.mode === "gen" && studio.genScope === "project";
  if (studio.mode && !targetOpen) return toast("请先保存并关闭当前编辑页，再调整另一项材料。");
  if (kind === "memory") {
    if (studio.mode !== "memory") await openMemoryStudio();
    studio.memoryEditor?.focus();
  } else {
    if (kind === "raise" && notice.report.model_limit_exceeded) return;
    if (targetOpen) collectGenForm();
    studio.genTab = "sample";
    if (targetOpen) renderGenSettings();
    else await openGenSettings("project");
    const key = kind === "raise" ? "max_context_tokens" : "recent_confirmed_chapter_count";
    const box = studio.genFields[key];
    if (kind === "raise") box.value = String(notice.report.suggested_input_limit);
    box.focus();
    box.scrollIntoView({ block: "center" });
    setStudioStatus("仅调整本作品。点击保存后，再重新发起任务。");
  }
  $("inputBudgetPanel").hidden = true;
}

function openDrawer({ kicker, title, content, wide }) {
  $("drawerKicker").textContent = kicker || "";
  $("drawerTitle").textContent = title || "";
  $("drawerBody").innerHTML = "";
  $("drawer").classList.toggle("wide", Boolean(wide));
  if (typeof content === "string") {
    $("drawerBody").textContent = content;
  } else {
    $("drawerBody").append(content);
  }
  $("drawer").hidden = false;
}

function field(label, control) {
  const wrap = document.createElement("label");
  wrap.className = "field";
  const span = document.createElement("span");
  span.textContent = label;
  wrap.append(span, control);
  return wrap;
}

function input(value, attrs = {}) {
  const el = document.createElement(attrs.area ? "textarea" : attrs.select ? "select" : "input");
  if (!attrs.area && !attrs.select) el.type = attrs.type || "text";
  if (attrs.select) {
    (attrs.options || []).forEach(([key, label]) => {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = label;
      if (key === value) option.selected = true;
      el.append(option);
    });
  } else {
    el.value = value || "";
  }
  if (attrs.placeholder) el.placeholder = attrs.placeholder;
  return el;
}

function currentProject() {
  return state.workspace.find((item) => item.project_id === state.projectId);
}

function chapterNumberFromId(chapterId) {
  const match = String(chapterId || "").match(/(\d+)$/);
  return match ? Number.parseInt(match[1], 10) : null;
}

function chapterGroupStart(number) {
  if (!Number.isFinite(number) || number <= 0) return 0;
  return Math.floor((number - 1) / CHAPTER_GROUP_SIZE) * CHAPTER_GROUP_SIZE + 1;
}

function chapterGroupKey(projectId, start) {
  return `${projectId}:${start}`;
}

function searchQuery() {
  return $("searchInput").value.trim().toLowerCase();
}

function isSearching() {
  return Boolean(searchQuery());
}

function isProjectExpanded(projectId, ctx) {
  if (ctx.searching) {
    const flag = state.treeSearchOpen.projects[projectId];
    if (flag === true) return true;
    if (flag === false) return false;
    return Boolean(ctx.hasChapterHits || ctx.projectTitleMatch);
  }
  return Boolean(state.treeOpen.projects[projectId]);
}

function isGroupExpanded(projectId, start, ctx) {
  const key = chapterGroupKey(projectId, start);
  if (ctx.searching) {
    const flag = state.treeSearchOpen.groups[key];
    if (flag === true) return true;
    if (flag === false) return false;
    return Boolean(ctx.groupHasHits);
  }
  return Boolean(state.treeOpen.groups[key]);
}

function toggleProjectOpen(projectId, ctx) {
  if (ctx.searching) {
    state.treeSearchOpen.projects[projectId] = !isProjectExpanded(projectId, ctx);
    return;
  }
  state.treeOpen.projects[projectId] = !state.treeOpen.projects[projectId];
}

function toggleGroupOpen(projectId, start, ctx) {
  const key = chapterGroupKey(projectId, start);
  if (ctx.searching) {
    state.treeSearchOpen.groups[key] = !isGroupExpanded(projectId, start, ctx);
    return;
  }
  state.treeOpen.groups[key] = !state.treeOpen.groups[key];
}

function revealInTree(projectId, chapterId) {
  if (!projectId) return;
  state.treeOpen.projects[projectId] = true;
  const number = chapterNumberFromId(chapterId);
  const start = number == null ? 0 : chapterGroupStart(number);
  if (chapterId) state.treeOpen.groups[chapterGroupKey(projectId, start)] = true;
}

function groupChapters(chapters) {
  const groups = new Map();
  chapters.forEach((chapter) => {
    const number = chapterNumberFromId(chapter.chapter_id);
    const start = number == null ? 0 : chapterGroupStart(number);
    let group = groups.get(start);
    if (!group) {
      group = {
        start,
        end: start === 0 ? 0 : start + CHAPTER_GROUP_SIZE - 1,
        chapters: [],
      };
      groups.set(start, group);
    }
    group.chapters.push(chapter);
  });
  return [...groups.values()].sort((left, right) => left.start - right.start);
}

function groupLabel(group) {
  if (group.start === 0) return "其他";
  return `${group.start}-${group.end}`;
}

function renderChapterRow(project, chapter) {
  const row = document.createElement("div");
  row.className = `tree-chapter${chapter.chapter_id === state.chapterId ? " active" : ""}`;
  const chapterBtn = document.createElement("button");
  chapterBtn.type = "button";
  chapterBtn.innerHTML = `<span class="dot ${chapter.status}"></span><span class="tree-title">${escapeHtml(chapter.title || chapter.chapter_id)}</span>`;
  chapterBtn.addEventListener("click", () => openChapter(project.project_id, chapter));
  chapterBtn.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
    showTreeMenu(event, { kind: "chapter", project, chapter });
  });
  row.append(chapterBtn);
  if (chapter.chapter_id === state.chapterId) {
    (chapter.drafts || []).forEach((draft) => {
      const draftBtn = document.createElement("button");
      draftBtn.type = "button";
      draftBtn.className = `tree-draft${draft.draft_id === state.draftId ? " active" : ""}`;
      draftBtn.innerHTML = `<span class="tree-title">${escapeHtml(draft.version_label || draft.draft_id)}</span>`;
      draftBtn.addEventListener("click", () => loadDraft(project.project_id, draft.draft_id));
      draftBtn.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        showTreeMenu(event, { kind: "draft", project, chapter, draft });
      });
      row.append(draftBtn);
    });
  }
  return row;
}

function renderTree() {
  const query = searchQuery();
  const searching = Boolean(query);
  const root = $("tree");
  const scrollTop = root.scrollTop;
  root.innerHTML = "";
  state.workspace.forEach((project) => {
    const projectHay = `${project.title} ${project.project_id}`.toLowerCase();
    const projectTitleMatch = searching && projectHay.includes(query);
    const chapterHits = searching
      ? (project.chapters || []).filter((chapter) => {
          const hay = `${chapter.title || ""} ${chapter.chapter_id}`.toLowerCase();
          return hay.includes(query);
        })
      : [];
    if (searching && !chapterHits.length && !projectTitleMatch) {
      return;
    }
    const sourceChapters = searching
      ? (chapterHits.length ? chapterHits : (project.chapters || []))
      : (project.chapters || []);
    const ctx = {
      searching,
      projectTitleMatch,
      hasChapterHits: chapterHits.length > 0,
    };
    const open = isProjectExpanded(project.project_id, ctx);
    const box = document.createElement("div");
    box.className = `tree-project${project.project_id === state.projectId ? " active" : ""}${open ? " open" : ""}`;
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-expanded", open ? "true" : "false");
    button.innerHTML = `<span class="chevron">${iconSvg(open ? "chevronDown" : "chevronRight")}</span><span class="tree-title">${escapeHtml(project.title)}</span><span class="tree-count">${(project.chapters || []).length}</span>`;
    button.addEventListener("click", () => {
      toggleProjectOpen(project.project_id, ctx);
      renderTree();
    });
    button.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showTreeMenu(event, { kind: "project", project });
    });
    box.append(button);
    if (open) {
      const list = document.createElement("div");
      list.className = "chapters";
      groupChapters(sourceChapters).forEach((group) => {
        const groupCtx = { ...ctx, groupHasHits: searching && chapterHits.some((chapter) => {
          const number = chapterNumberFromId(chapter.chapter_id);
          const start = number == null ? 0 : chapterGroupStart(number);
          return start === group.start;
        }) };
        const groupOpen = isGroupExpanded(project.project_id, group.start, groupCtx);
        const groupBox = document.createElement("div");
        groupBox.className = `tree-group${groupOpen ? " open" : ""}`;
        const groupBtn = document.createElement("button");
        groupBtn.type = "button";
        groupBtn.setAttribute("aria-expanded", groupOpen ? "true" : "false");
        groupBtn.innerHTML = `<span class="chevron">${iconSvg(groupOpen ? "chevronDown" : "chevronRight")}</span><span class="tree-title">${escapeHtml(groupLabel(group))}</span><span class="tree-count">${group.chapters.length}</span>`;
        groupBtn.addEventListener("click", (event) => {
          event.stopPropagation();
          toggleGroupOpen(project.project_id, group.start, groupCtx);
          renderTree();
        });
        groupBox.append(groupBtn);
        if (groupOpen) {
          group.chapters.forEach((chapter) => groupBox.append(renderChapterRow(project, chapter)));
        }
        list.append(groupBox);
      });
      box.append(list);
    }
    root.append(box);
  });
  root.scrollTop = scrollTop;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refreshWorkspace(keepSelection = true) {
  const workspace = await call("refresh_workspace");
  state.workspace = workspace || [];
  if (keepSelection && state.projectId && !currentProject() && state.workspace[0]) {
    state.projectId = state.workspace[0].project_id;
  }
  if (!state.projectId && state.workspace[0]) {
    state.projectId = state.workspace[0].project_id;
  }
  renderTree();
  if (state.projectId) await loadOverview(state.projectId);
}

async function flushSave() {
  if (state.flushPromise) return state.flushPromise;
  clearTimeout(state.saveTimer);
  state.saveTimer = 0;
  const editor = $("editor");
  const wasReadOnly = editor.readOnly;
  const pending = saveDraft();
  editor.readOnly = true;
  state.flushPromise = (async () => {
    try { return await pending; }
    finally {
      state.flushPromise = null;
      if (!state.closing && !state.generating && !state.importing) editor.readOnly = wasReadOnly;
    }
  })();
  return state.flushPromise;
}

function blockIfGenerating() {
  if (state.changingRoot) { toast("正在切换项目库，请稍候。"); return true; }
  if (!state.generating) return false;
  toast("请等待当前生成完成。");
  return true;
}

async function selectProject(projectId) {
  if (!projectId) return false;
  if (projectId !== state.projectId) {
    if (blockIfGenerating()) return false;
    if (studio.mode && !(await guardStudioLeave())) return false;
    if (!(await flushSave()).ok) return false;
    state.navigationId += 1;
    state.draftId = "";
    state.chapterId = "";
    state.draftIds = [];
    state.draftIndex = -1;
    state.hasReview = false;
    state.reviewText = "";
    state.reviewNotice = "";
    state.reviewBox = null;
    state.dirty = false;
    state.savedSnapshot = null;
    state.inputBudgetNotice = null;
    state.inputBudgetRetry = null;
    $("inputBudgetPanel").hidden = true;
    $("inputBudgetEntry").hidden = true;
    $("editor").value = "";
    $("editor").readOnly = false;
    $("draftTitle").textContent = "选择章节开始写作";
    $("draftHint").textContent = "";
    $("versionLabel").textContent = "—";
    updateCountPill();
    updateDock();
    if (studio.mode) await closeStudio({ discard: true });
    ["outline", "world"].forEach((kind) => {
      const pane = $(`pane-${kind}`);
      if (pane) {
        pane.dataset.selected = "";
        pane.dataset.projectId = "";
      }
    });
  }
  if (window.ThinkTrace && ThinkTrace.isIdle()) ThinkTrace.dispose();
  state.projectId = projectId;
  $("projectChip").textContent = currentProject()?.title || "未选择作品";
  renderTree();
  await loadOverview(projectId);
  return true;
}

async function loadOverview(projectId) {
  const overview = await call("project_overview", projectId);
  if (projectId !== state.projectId) return;
  $("projectChip").textContent = currentProject()?.title || projectId;
  refreshModelPill().catch(() => {});
  $("summaryText").textContent = `章节 ${overview.chapter_count} · 草稿 ${overview.draft_count}\n已确认 ${overview.committed_chapter_count} · 审稿 ${overview.review_count}`;
  $("contextText").textContent = `大纲与资料 ${overview.planning_item_count} 项\n记忆库 ${overview.memory_bank_item_count} 项\n已启用材料完整保留，超出预算会提示调整。`;
  if (state.inspectorTab !== "chapter") renderInspector().catch(() => {});
}

async function openChapter(projectId, chapter) {
  if (blockIfGenerating()) return false;
  if (state.draftId && (projectId !== state.projectId || chapter.chapter_id !== state.chapterId)) {
    if (!(await flushSave()).ok) return false;
  }
  revealInTree(projectId, chapter.chapter_id);
  if ((await selectProject(projectId)) === false) return false;
  const latest = [...(chapter.drafts || [])].pop();
  renderTree();
  if (latest?.draft_id) {
    return loadDraft(projectId, latest.draft_id);
  } else {
    state.chapterId = chapter.chapter_id;
    state.draftId = "";
    state.draftIds = [];
    state.draftIndex = -1;
    $("draftTitle").textContent = chapter.title || chapter.chapter_id;
    $("draftHint").textContent = "这一章还没有可读草稿";
    $("editor").value = "";
    updateCountPill();
    $("versionLabel").textContent = "—";
    state.hasReview = false;
    state.reviewText = "";
    state.reviewNotice = "";
    state.reviewBox = null;
    setReviewBadge(false);
    updateDock();
    if (state.inspectorTab === "review") renderInspector();
    return true;
  }
}

async function loadDraft(projectId, draftId, { silent = false, force = false } = {}) {
  if (!force && blockIfGenerating()) return false;
  if (!force && state.draftId) {
    if (!(await flushSave()).ok) return false;
  }
  const navigationId = ++state.navigationId;
  $("editor").readOnly = true;
  let draft;
  try { draft = await call("open_draft", projectId, draftId); }
  finally {
    if (navigationId === state.navigationId) $("editor").readOnly = state.closing || state.generating;
  }
  if (navigationId !== state.navigationId) return false;
  state.projectId = draft.project_id;
  state.chapterId = draft.chapter_id;
  state.draftId = draft.draft_id;
  revealInTree(draft.project_id, draft.chapter_id);
  state.draftIds = draft.draft_ids || [];
  state.draftIndex = draft.index ?? -1;
  $("draftTitle").textContent = `${draft.chapter_id} · ${draft.title}`;
  $("draftHint").textContent = `${draft.version_label} · ${draft.status_label} · 编辑会自动保存`;
  if (draft.output_incomplete) {
    $("draftHint").textContent += " · 输出已截断：这是不完整候选，请核对并补全";
  }
  $("versionLabel").textContent = draft.version_label;
  $("editor").value = draft.content || "";
  // The first save after opening also reconciles a previously interrupted disk
  // write. Only a successful save response may populate the no-op cache.
  state.savedSnapshot = null;
  state.dirty = false;
  state.saveError = "";
  state.hasReview = Boolean(draft.has_review);
  state.reviewText = draft.review?.details || draft.review?.comment || "";
  state.reviewNotice = draft.review?.truncated ? "审稿意见被截断，可能不完整。可阅读或复制；请重新审稿后再精修。" : "";
  state.reviewBox = null;
  setReviewBadge(false);
  state.lastSavedAt = Date.now();
  updateCountPill();
  refreshSavePill();
  updateDock();
  $("prevBtn").disabled = state.draftIndex <= 0;
  $("nextBtn").disabled = state.draftIndex < 0 || state.draftIndex >= state.draftIds.length - 1;
  renderTree();
  if (state.inspectorTab === "review") renderInspector();
  if (!silent) $("editor").focus();
  return true;
}

function scheduleSave() {
  updateCountPill();
  if (!state.draftId || $("editor").readOnly || state.importing) return;
  state.dirty = true;
  $("savePill").textContent = "保存中…";
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(saveDraft, 700);
}

async function saveDraft() {
  // importing 与 readOnly 都必须挡住：saveDraft 原先只认 readOnly，覆盖导入后旧缓冲会写回磁盘。
  if (!state.projectId || !state.draftId || $("editor").readOnly || state.importing) return { ok: true };
  const projectId = state.projectId;
  const draftId = state.draftId;
  const text = $("editor").value;
  const projectsRoot = state.projectsRoot;
  // Serialize writes so a slower earlier request cannot overwrite newer editor text.
  const queuedSave = state.saveQueue
    .catch(() => {})
    .then(() => {
      const previous = state.savedSnapshot;
      if (previous?.projectsRoot === projectsRoot && previous.projectId === projectId && previous.draftId === draftId && previous.text === text) return { changed: false };
      return call("save_draft", projectId, draftId, text, projectsRoot);
    });
  state.saveQueue = queuedSave.catch(() => {});
  try {
    const result = await queuedSave;
    state.savedSnapshot = { projectsRoot, projectId, draftId, text };
    if (result?.memory_reminder) queueMemoryReminder(projectId, result.memory_reminder);
    if (projectId === state.projectId && draftId === state.draftId && text === $("editor").value) {
      state.saveError = "";
      state.dirty = false;
      state.lastSavedAt = Date.now();
      refreshSavePill();
    }
    return { ok: true };
  } catch (error) {
    state.saveError = error.message || "保存失败";
    $("savePill").textContent = "保存失败";
    toast(error.message);
    return { ok: false, error: error.message || "保存失败" };
  }
}

function queueMemoryReminder(projectId, reminder) {
  const key = `${projectId}:${reminder.chapter_id}`;
  if (state.memoryReminderShown.has(key)) return;
  state.memoryReminderShown.add(key);
  state.memoryReminders.push({ projectId, ...reminder });
  if (state.memoryReminders.length === 1) setTimeout(showMemoryReminder, 500);
}

function showMemoryReminder() {
  if (!state.memoryReminders.length || state.closing) return;
  if (state.generating || !$("modal").hidden) { setTimeout(showMemoryReminder, 500); return; }
  const reminder = state.memoryReminders.shift();
  openModal({ title: "请核对记忆银行", desc: `${reminder.projectId} · ${reminder.chapter_id}`,
    body: elNote(reminder.message), actions: [{ label: "知道了，我会按需手工检查", onClick: () => {
      closeModal();
      if (state.memoryReminders.length) setTimeout(showMemoryReminder, 500);
    } }] });
}

function requireDraft() {
  if (!state.projectId || !state.draftId) {
    toast("请先打开一个草稿。");
    return false;
  }
  return true;
}

function promptText({ title, desc, value = "", onSubmit }) {
  const area = input(value, { area: true, placeholder: "可留空" });
  openModal({
    title,
    desc,
    body: field("本次要求", area),
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "继续",
        style: "primary",
        onClick: async () => {
          closeModal();
          await onSubmit(area.value);
        },
      },
    ],
  });
  setTimeout(() => area.focus(), 30);
}

async function createProject() {
  const title = input("", { placeholder: "例如：雾港来信" });
  const ident = input("", { placeholder: "可留空，自动生成英文 ID" });
  openModal({
    title: "新建作品",
    desc: "作品保存在本地项目库。ID 只能使用英文、数字、下划线和连字符。",
    body: (() => {
      const wrap = document.createElement("div");
      wrap.append(field("作品标题", title), field("作品 ID（可选）", ident));
      return wrap;
    })(),
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "创建",
        style: "primary",
        onClick: async () => {
          try {
            const created = await call("create_project", title.value.trim(), ident.value.trim());
            state.workspace = created.workspace || [];
            await selectProject(created.project.project_id);
            renderTree();
            closeModal();
            toast("作品已创建。");
          } catch (error) {
            toast(error.message);
          }
        },
      },
    ],
  });
}

async function generateChapter() {
  if (blockIfGenerating()) return;
  if (!state.projectId) {
    toast("请先选择或新建一个作品。");
    return;
  }
  const suggestion = await call("suggest_chapter", state.projectId);
  const chapter = input(suggestion.chapter_id);
  const title = input("");
  const prompt = input(suggestion.default_prompt, { area: true });
  openModal({
    title: "生成新章节",
    desc: "先确认章节与写作目标。只有点击生成后才会调用模型。",
    body: (() => {
      const wrap = document.createElement("div");
      wrap.append(field("章节 ID", chapter), field("章节标题", title), field("本次要求", prompt));
      return wrap;
    })(),
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "检查发送材料",
        onClick: async () => {
          try {
            const projectId = state.projectId;
            const chapterId = chapter.value.trim();
            const chapterTitle = title.value.trim() || chapterId;
            const userPrompt = prompt.value;
            const preview = await call("preview_prompt", projectId, chapterId, userPrompt);
            if (preview.input_budget && !preview.input_budget.can_send) {
              closeModal();
              closeDrawer();
              showInputBudgetNotice(preview.input_budget, projectId, {
                method: "generate_draft", args: [projectId, chapterId, chapterTitle, userPrompt],
                projectId, chapterId, title: chapterTitle,
              });
            } else {
              openDrawer({ kicker: "不会联网", title: "将发送给模型的结构", content: preview.details });
            }
          } catch (error) {
            toast(error.message);
          }
        },
      },
      {
        label: "生成草稿",
        style: "primary",
        onClick: async () => {
          const projectId = state.projectId;
          const chapterId = chapter.value.trim();
          const chapterTitle = title.value.trim() || chapterId;
          const userPrompt = prompt.value;
          try {
            if (!(await flushSave()).ok) return;
            if (blockIfGenerating()) return;
            closeModal();
            state.inputBudgetRetry = { method: "generate_draft", args: [projectId, chapterId, chapterTitle, userPrompt],
              projectId, chapterId, title: chapterTitle };
            beginStream(projectId, chapterId, chapterTitle);
            await call("generate_draft", projectId, chapterId, chapterTitle, userPrompt);
          } catch (error) {
            await finishDraft({ ok: false, error: error.message });
          }
        },
      },
    ],
  });
}

function beginStream(projectId, chapterId, title) {
  state.navigationId += 1;
  state.streamSource = { projectId: state.projectId, chapterId: state.chapterId, draftId: state.draftId,
    draftIds: [...state.draftIds], draftIndex: state.draftIndex, content: $("editor").value,
    title: $("draftTitle").textContent, hint: $("draftHint").textContent,
    version: $("versionLabel").textContent, hasReview: state.hasReview, reviewText: state.reviewText, reviewNotice: state.reviewNotice };
  state.follow = true;
  state.streamProjectId = projectId;
  state.streamChapterId = chapterId;
  state.projectId = projectId;
  state.chapterId = chapterId;
  state.draftId = "";
  $("draftTitle").textContent = `${chapterId} · ${title}`;
  $("draftHint").textContent = "请求已发出，正在等待模型接入…";
  $("editor").value = "";
  updateCountPill();
  $("savePill").textContent = "正在生成…";
  ThinkTrace.start();
  setBusy(true, "请求已发出，正在等待模型接入…");
}

function appendEditor(text, chapterId = "") {
  if (!state.generating) return;
  if (state.streamChapterId && chapterId && chapterId !== state.streamChapterId) return;
  if (state.streamProjectId && state.projectId !== state.streamProjectId) return;
  const editor = $("editor");
  editor.value += text;
  updateCountPill();
  if (state.follow) {
    editor.scrollTo({ top: editor.scrollHeight, behavior: "auto" });
  }
}

async function finishDraft(payload) {
  const projectId = state.streamProjectId || state.projectId;
  ThinkTrace.finish(payload?.ok !== false);
  if (!payload?.ok) {
    const partial = $("editor").value;
    const source = state.streamSource;
    if (source) {
      Object.assign(state, { projectId: source.projectId, chapterId: source.chapterId, draftId: source.draftId,
        draftIds: source.draftIds, draftIndex: source.draftIndex, hasReview: source.hasReview, reviewText: source.reviewText, reviewNotice: source.reviewNotice });
      $("editor").value = source.content;
      $("draftTitle").textContent = source.title;
      $("draftHint").textContent = source.hint;
      $("versionLabel").textContent = source.version;
      if (partial) openDrawer({ kicker: "未保存的输出片段，可手工复制", title: "本次生成未完成", content: partial });
    }
    state.streamSource = null;
    setBusy(false);
    updateCountPill();
    renderTree();
    $("savePill").textContent = payload.cancelled ? "本次任务已停止" : "本次生成失败，原稿已保留";
    toast(payload?.error || "生成失败");
    state.streamProjectId = "";
    state.streamChapterId = "";
    return;
  }
  const draftId = payload.data?.draft_id;
  try {
    await refreshWorkspace();
    if (draftId) {
      await loadDraft(projectId, draftId, { silent: true, force: true });
      toast(payload.data?.output_incomplete
        ? "输出达到上限，已保存为不完整候选。请核对结尾、补全或提高 Max Tokens 后重试。"
        : "新草稿已写入，尚未成为确认稿。");
    }
  } catch (error) { toast(`结果已保存，但刷新失败：${error.message}。请重新打开章节。`); }
  finally { setBusy(false); state.streamSource = null; }
  state.streamProjectId = "";
  state.streamChapterId = "";
}

async function rewriteDraft() {
  if (!requireDraft()) return;
  if (blockIfGenerating() || !(await flushSave()).ok) return;
  promptText({
    title: "重新生成",
    desc: "会生成一个全新版本，不会覆盖当前草稿，也不会参考上一版正文。",
    onSubmit: async (instruction) => {
      if (blockIfGenerating() || !(await flushSave()).ok || blockIfGenerating()) return;
      const projectId = state.projectId;
      const draftId = state.draftId;
      const chapterId = state.chapterId;
      const project = currentProject();
      const chapter = project?.chapters?.find((item) => item.chapter_id === chapterId);
      state.inputBudgetRetry = { method: "rewrite_draft", args: [projectId, draftId, instruction],
        projectId, chapterId, title: chapter?.title || chapterId };
      beginStream(projectId, chapterId, chapter?.title || chapterId);
      try {
        await call("rewrite_draft", projectId, draftId, instruction);
      } catch (error) {
        await finishDraft({ ok: false, error: error.message });
      }
    },
  });
}

async function refineDraft() {
  if (!requireDraft()) return;
  if (!state.hasReview) {
    toast("需要先完成 AI 审稿，才能根据审稿精修。");
    setInspectorTab("review");
    return;
  }
  const saved = await flushSave();
  if (!saved.ok) return;
  // Saving may have changed the text after its review was produced.
  const current = await call("open_draft", state.projectId, state.draftId);
  state.hasReview = current.has_review;
  if (!current.has_review) {
    toast("正文已变化或审稿不完整，请先重新进行 AI 审稿。");
    setInspectorTab("review");
    return;
  }
  promptText({
    title: "根据审稿精修",
    desc: "必须以当前 AI 审稿意见为主约束。没有审稿时不能精修。",
    onSubmit: async (instruction) => {
      if (blockIfGenerating() || !(await flushSave()).ok || blockIfGenerating()) return;
      const projectId = state.projectId;
      const draftId = state.draftId;
      const chapterId = state.chapterId;
      state.inputBudgetRetry = { method: "refine_draft", args: [projectId, draftId, instruction],
        projectId, chapterId, title: `精修 ${chapterId}` };
      beginStream(projectId, chapterId, `精修 ${chapterId}`);
      try {
        await call("refine_draft", projectId, draftId, instruction);
      } catch (error) {
        await finishDraft({ ok: false, error: error.message });
      }
    },
  });
}

async function reviewDraft() {
  if (!requireDraft()) return;
  if (blockIfGenerating()) return;
  const saved = await flushSave();
  if (!saved.ok || blockIfGenerating()) return;
  const box = document.createElement("div");
  box.className = "review-stream";
  box.textContent = "";
  state.reviewBox = box;
  state.reviewNotice = "";
  setInspectorTab("review");
  const pane = $("pane-review");
  pane.innerHTML = "";
  pane.append(elNote("正在阅读这一稿…"), box);
  ThinkTrace.start();
  state.inputBudgetRetry = { method: "ai_review", projectId: state.projectId };
  setBusy(true, "请求已发出，正在等待模型接入…", { lockEditor: false, veil: false });
  try {
    const result = await call("ai_review", state.projectId, state.draftId);
    if (result?.existing) {
      state.inputBudgetRetry = null;
      finishReview({ ok: true, data: result.review });
      return;
    }
  } catch (error) {
    finishReview({ ok: false, error: error.message, cancelled: error.cancelled });
  }
}

function finishReview(payload) {
  setBusy(false);
  ThinkTrace.finish(payload?.ok !== false);
  const review = payload.data || {};
  if (!payload?.ok) {
    state.hasReview = false;
    state.reviewText = state.reviewBox?.textContent || "";
    state.reviewNotice = payload?.cancelled
      ? "审稿已停止。已返回的片段可阅读或复制；请重新审稿后再精修。"
      : `审稿失败：${payload?.error || "未收到完整结果"}。可重新点击「AI 审稿」。`;
  } else {
    state.hasReview = !review.truncated && !state.dirty;
    state.reviewText = review.details || review.comment || "暂无说明";
    state.reviewNotice = review.truncated
      ? "审稿意见被截断，可能不完整。可阅读或复制；请重新审稿后再精修。"
      : state.dirty ? "正文已修改，这份意见供参考；请重新审稿后再精修。" : "";
  }
  state.reviewBox = null;
  updateDock();
  if (state.inspectorTab === "review") {
    setReviewBadge(false);
    renderReviewPane();
  } else {
    setReviewBadge(true);
    if (payload?.ok && !review.truncated) toast("审稿意见已就绪");
  }
  if (!payload?.ok) { toast(payload?.error || state.reviewNotice); return; }
  if (review.truncated) toast(review.truncated_notice || "审稿意见被截断，可能不完整。");
  loadOverview(state.projectId).catch(() => {});
}

async function confirmDraft() {
  if (!requireDraft()) return;
  if (blockIfGenerating() || !(await flushSave()).ok) return;
  const note = document.createElement("p");
  note.textContent = "确认后，这一版会成为该章节的确认稿。未确认的草稿仍会保留。";
  openModal({
    title: "确认稿件",
    desc: "这是一个显式提交动作，不会在后台自动发生。",
    body: note,
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "确认这一版",
        style: "success",
        onClick: async () => {
          try {
            if (!(await flushSave()).ok) return;
            const projectId = state.projectId;
            const draftId = state.draftId;
            const result = await call("confirm_draft", projectId, draftId);
            if (result?.memory_reminder) queueMemoryReminder(projectId, result.memory_reminder);
            closeModal();
            await refreshWorkspace();
            await loadDraft(projectId, draftId, { silent: true });
            toast("已提交为确认稿。");
            await maybeOfferAutoMemory(projectId);
          } catch (error) {
            toast(error.message);
          }
        },
      },
    ],
  });
}

async function openLibrary() {
  await openPlanningStudio("outline");
}

function elNote(text) {
  const p = document.createElement("p");
  p.className = "studio-note";
  p.textContent = text;
  return p;
}

function setInspectorTab(tab) {
  state.inspectorTab = tab;
  if (tab === "review") setReviewBadge(false);
  document.querySelectorAll(".inspector-tabs .tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  ["chapter", "outline", "world", "memory", "review"].forEach((name) => {
    const pane = $(`pane-${name}`);
    if (pane) pane.hidden = name !== tab;
  });
  if (tab !== "chapter") renderInspector();
}

async function renderInspector() {
  const tab = state.inspectorTab;
  if (tab === "review") {
    renderReviewPane();
    return;
  }
  if (!state.projectId) {
    const pane = $(`pane-${tab}`);
    if (pane && tab !== "chapter") {
      pane.innerHTML = "";
      pane.append(elNote("请先选择作品。"));
    }
    return;
  }
  if (tab === "outline" || tab === "world") {
    await renderPlanningPane(tab);
    return;
  }
  if (tab === "memory") await renderMemoryPane();
}

function renderReviewPane() {
  const pane = $("pane-review");
  if (!pane) return;
  if (state.reviewBox && state.generating) {
    if (!pane.contains(state.reviewBox)) {
      pane.innerHTML = "";
      pane.append(elNote("正在阅读这一稿…"), state.reviewBox);
    }
    return;
  }
  pane.innerHTML = "";
  if (!state.draftId) {
    pane.append(elNote("打开草稿后，这里显示该稿的 AI 审稿意见。"));
    return;
  }
  if (state.reviewNotice) pane.append(elNote(state.reviewNotice));
  if (!state.reviewText) {
    if (!state.reviewNotice) pane.append(elNote("这一稿还没有审稿。点底部「AI 审稿」后，意见会出现在这里，不会挡住正文。"));
    return;
  }
  const body = document.createElement("div");
  body.className = "review-stream";
  body.textContent = state.reviewText || "暂无说明";
  if (!state.reviewNotice) pane.append(elNote("审稿意见与正文并排，可边看边改。"));
  pane.append(body);
}

async function renderPlanningPane(kind) {
  const pane = $(`pane-${kind}`);
  if (!pane) return;
  let data;
  try {
    data = await call("planning_state", state.projectId, kind);
  } catch (error) {
    pane.innerHTML = "";
    pane.append(elNote(error.message));
    return;
  }
  if (state.inspectorTab !== kind) return;
  const items = data.items || [];
  if (pane.dataset.projectId !== state.projectId) {
    pane.dataset.selected = "";
    pane.dataset.projectId = state.projectId;
  }
  const selectedId = items.find((item) => item.planning_id === pane.dataset.selected)?.planning_id || items[0]?.planning_id || "";
  pane.dataset.selected = selectedId;
  pane.innerHTML = "";
  pane.append(elNote(kind === "outline" ? "对照大纲写正文。需要新建或删条目时，打开完整编辑。" : "对照人物、世界观和写作约束写正文。"));
  if (!items.length) {
    const copy = planningIdleCopy(kind);
    const banner = document.createElement("div");
    banner.className = "studio-idle-banner";
    banner.append(elNote(copy.banner));
    const create = document.createElement("button");
    create.type = "button";
    create.className = "btn primary";
    create.textContent = copy.button;
    create.addEventListener("click", () => openPlanningStudio(kind, { create: true }).catch((error) => toast(error.message)));
    banner.append(create);
    pane.append(banner);
    return;
  }
  const list = document.createElement("div");
  list.className = "stack";
  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `choice${item.planning_id === selectedId ? " active" : ""}`;
    button.textContent = item.title || item.planning_id;
    button.addEventListener("click", () => {
      pane.dataset.selected = item.planning_id;
      renderPlanningPane(kind).catch((error) => toast(error.message));
    });
    list.append(button);
  });
  pane.append(list);
  const current = items.find((item) => item.planning_id === selectedId);
  if (current) {
    const editor = document.createElement("textarea");
    editor.className = "studio-editor";
    editor.value = current.text || "";
    const save = document.createElement("button");
    save.type = "button";
    save.className = "btn primary";
    save.textContent = "保存";
    save.addEventListener("click", async () => {
      try {
        await call("save_planning", {
          project_id: state.projectId,
          planning_id: current.planning_id,
          creating: false,
          item_type: current.item_type,
          title: current.title || "",
          text: editor.value,
          active: current.enabled !== false && current.active !== false,
          adherence_level: current.adherence_level || "balanced",
          chapter_range: current.chapter_range || "",
        });
        toast("资料已保存。");
        loadOverview(state.projectId).catch(() => {});
      } catch (error) {
        toast(error.message);
      }
    });
    pane.append(editor, save);
  }
  const more = document.createElement("button");
  more.type = "button";
  more.className = "btn ghost block";
  more.textContent = "完整编辑";
  more.addEventListener("click", () => openPlanningStudio(kind).catch((error) => toast(error.message)));
  pane.append(more);
}

async function renderMemoryPane() {
  const pane = $("pane-memory");
  if (!pane) return;
  let data;
  try {
    data = await call("memory_state", state.projectId);
  } catch (error) {
    pane.innerHTML = "";
    pane.append(elNote(error.message));
    return;
  }
  if (state.inspectorTab !== "memory") return;
  pane.innerHTML = "";
  pane.append(elNote(data.token_advice || "记忆库正文会参与后续生成。保存不会联网。"));
  const editor = document.createElement("textarea");
  editor.className = "studio-editor";
  editor.value = data.memory?.text || "";
  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn primary";
  save.textContent = "保存记忆";
  save.addEventListener("click", async () => {
    try {
      await call("save_memory_workspace", {
        project_id: state.projectId,
        memory_id: data.memory?.memory_id || "main_memory_bank",
        text: editor.value,
        chapter_ids: data.memory?.source_chapter_ids || [],
        target_tokens: data.target_tokens || 5000,
        enabled: data.memory?.enabled !== false,
      });
      toast("记忆已保存。");
      loadOverview(state.projectId).catch(() => {});
    } catch (error) {
      toast(error.message);
    }
  });
  const more = document.createElement("button");
  more.type = "button";
  more.className = "btn ghost block";
  more.textContent = "完整编辑与生成";
  more.addEventListener("click", () => openMemoryStudio().catch((error) => toast(error.message)));
  pane.append(editor, save, more);
}

function openSettings() {
  const theme = input(state.prefs.theme, { select: true, options: [["system", "跟随系统"], ["light", "浅色"], ["dark", "深色"]] });
  const font = input(state.prefs.fontFamily, {
    select: true,
    options: Object.entries(FONTS).map(([key, item]) => [key, item.label]),
  });
  const size = input(String(state.prefs.fontSize), { type: "range" });
  size.min = "14";
  size.max = "26";
  size.value = String(state.prefs.fontSize);
  const sizeLabel = document.createElement("span");
  sizeLabel.textContent = `${state.prefs.fontSize} px`;
  size.addEventListener("input", () => {
    sizeLabel.textContent = `${size.value} px`;
    state.prefs.fontSize = Number(size.value);
    applyPrefs();
  });
  const sizeRow = document.createElement("div");
  sizeRow.className = "pref-row";
  sizeRow.append(size, sizeLabel);
  const width = input(state.prefs.editorWidth === "fill" ? "fill" : "comfort", {
    select: true,
    options: [["comfort", "舒适宽（约 40 字）"], ["fill", "铺满中间栏"]],
  });
  width.addEventListener("change", () => {
    state.prefs.editorWidth = width.value;
    applyPrefs();
  });
  const body = document.createElement("div");
  body.append(field("外观", theme), field("正文字体", font), field("正文字号", sizeRow), field("稿纸宽度", width));
  theme.addEventListener("change", () => {
    state.prefs.theme = theme.value;
    applyPrefs();
  });
  font.addEventListener("change", () => {
    state.prefs.fontFamily = font.value;
    applyPrefs();
  });
  openModal({
    title: "外观与阅读",
    desc: "字号、字体和主题只影响你自己的阅读方式，不会改动作品文件。",
    body,
    actions: [
      {
        label: "完成",
        style: "primary",
        onClick: async () => {
          state.prefs.theme = theme.value;
          state.prefs.fontFamily = font.value;
          state.prefs.fontSize = Number(size.value);
          state.prefs.editorWidth = width.value;
          applyPrefs();
          await call("save_prefs", state.prefs);
          closeModal();
        },
      },
    ],
  });
}

async function toggleFocus() {
  state.prefs.focusMode = !state.prefs.focusMode;
  if (state.prefs.focusMode) state.prefs.hideInspector = true;
  else state.prefs.hideInspector = false;
  applyPrefs();
  await call("save_prefs", {
    focusMode: state.prefs.focusMode,
    hideInspector: state.prefs.hideInspector,
  });
}

async function toggleInspector() {
  state.prefs.hideInspector = !state.prefs.hideInspector;
  applyPrefs();
  await call("save_prefs", { hideInspector: state.prefs.hideInspector });
}

function hideTreeMenu() {
  const menu = $("ctxMenu");
  if (!menu) return;
  menu.hidden = true;
  menu.innerHTML = "";
}

function showTreeMenu(event, target) {
  const menu = $("ctxMenu");
  menu.innerHTML = "";
  menuItemsFor(target).forEach((item) => {
    if (item === "-") {
      menu.append(document.createElement("hr"));
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    if (item.danger) button.className = "danger";
    button.addEventListener("click", async () => {
      hideTreeMenu();
      try {
        await item.onClick();
      } catch (error) {
        toast(error.message);
      }
    });
    menu.append(button);
  });
  menu.hidden = false;
  const pad = 8;
  const left = Math.min(event.clientX, window.innerWidth - menu.offsetWidth - pad);
  const top = Math.min(event.clientY, window.innerHeight - menu.offsetHeight - pad);
  menu.style.left = `${Math.max(pad, left)}px`;
  menu.style.top = `${Math.max(pad, top)}px`;
}

function menuItemsFor(target) {
  const projectId = target.project.project_id;
  const chapter = target.chapter;
  const draft = target.draft;
  const shared = [
    { label: "记忆库", onClick: () => openMemoryStudio() },
    { label: "大纲与章节", onClick: () => openPlanningStudio("outline") },
    { label: "世界观与人物", onClick: () => openPlanningStudio("world") },
    { label: "查看生成时会带的上下文", onClick: () => showContextPreview(projectId) },
  ];
  if (target.kind === "chapter") {
    const items = [
      { label: "打开章节", onClick: () => openChapter(projectId, chapter) },
      { label: "重命名章节", onClick: () => renameChapter(projectId, chapter) },
      { label: "AI审稿当前稿", onClick: () => runOnChapterDraft(projectId, chapter, reviewDraft) },
      { label: "本地初审当前稿", onClick: () => runOnChapterDraft(projectId, chapter, localReviewCurrent) },
      { label: "要求重写（重新随机）当前稿", onClick: () => runOnChapterDraft(projectId, chapter, rewriteDraft) },
      { label: "根据审稿精修当前稿", onClick: () => runOnChapterDraft(projectId, chapter, refineDraft) },
      "-",
    ];
    if (chapter.status === "confirmed") {
      items.push({
        label: "删除已确认章节",
        danger: true,
        onClick: () => deleteConfirmedChapter(projectId, chapter),
      });
    }
    items.push({
      label: "删除本章草稿",
      danger: true,
      onClick: () => deleteChapterDrafts(projectId, chapter),
    });
    items.push("-", ...shared);
    return items;
  }
  if (target.kind === "draft") {
    return [
      { label: "打开草稿", onClick: () => loadDraft(projectId, draft.draft_id) },
      { label: "AI审稿", onClick: () => runOnDraft(projectId, draft.draft_id, reviewDraft) },
      { label: "本地初审", onClick: () => runOnDraft(projectId, draft.draft_id, localReviewCurrent) },
      { label: "确认稿件", onClick: () => runOnDraft(projectId, draft.draft_id, confirmDraft) },
      { label: "要求重写（重新随机）", onClick: () => runOnDraft(projectId, draft.draft_id, rewriteDraft) },
      { label: "根据审稿精修", onClick: () => runOnDraft(projectId, draft.draft_id, refineDraft) },
      "-",
      ...shared,
    ];
  }
  return [
    {
      label: "打开作品",
      onClick: async () => {
        state.treeOpen.projects[projectId] = true;
        await selectProject(projectId);
      },
    },
    { label: "重命名作品", onClick: () => renameProject(target.project) },
    {
      label: "生成草稿",
      onClick: async () => {
        if ((await selectProject(projectId)) === false) return;
        await generateChapter();
      },
    },
    { label: "AI审稿当前稿", onClick: reviewDraft },
    { label: "本地初审当前稿", onClick: localReviewCurrent },
    { label: "确认当前稿", onClick: confirmDraft },
    { label: "要求重写（重新随机）当前稿", onClick: rewriteDraft },
    { label: "根据审稿精修当前稿", onClick: refineDraft },
    { label: "查看生成时会带的上下文", onClick: () => showContextPreview(projectId) },
    { label: "记忆库", onClick: () => openMemoryStudio() },
    { label: "大纲与章节", onClick: () => openPlanningStudio("outline") },
    { label: "世界观与人物", onClick: () => openPlanningStudio("world") },
    { label: "项目专属设置", onClick: () => openGenSettings("project") },
    { label: "记录与诊断", onClick: () => openRecordsStudio("connection") },
    { label: "模型服务", onClick: () => openModelStudio() },
    { label: "打开作品文件夹", onClick: () => call("open_folder", "project", projectId) },
    // 树上只导出被右键的这一部；导入不挂在这里，避免以为会覆盖这一行。
    { label: "导出作品包…", onClick: () => exportProjectPackage(projectId) },
    "-",
    { label: "删除作品", danger: true, onClick: () => deleteProject(target.project) },
  ];
}

async function runOnChapterDraft(projectId, chapter, action) {
  if (!(await openChapter(projectId, chapter))) return;
  await action();
}

async function runOnDraft(projectId, draftId, action) {
  if (!(await loadDraft(projectId, draftId, { silent: true }))) return;
  await action();
}

async function localReviewCurrent() {
  if (!requireDraft()) return;
  if (blockIfGenerating() || !(await flushSave()).ok) return;
  const result = await call("local_review", state.projectId, state.draftId);
  openDrawer({
    kicker: result.existing ? "已有本地初审" : "本地初审完成",
    title: `初审 · ${result.review.chapter_id || ""}`,
    content: result.review.details || "暂无说明",
  });
  loadOverview(state.projectId).catch(() => {});
}

async function showContextPreview(projectId) {
  const result = await call("context_preview", projectId);
  openDrawer({ kicker: "生成上下文", title: "生成时会携带的上下文", content: result.details });
}

function promptName({ title, desc, value, onSubmit }) {
  const box = input(value || "", { placeholder: "新名称" });
  openModal({
    title,
    desc,
    body: field("名称", box),
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "保存",
        style: "primary",
        onClick: async () => {
          const name = box.value.trim();
          if (!name) {
            toast("名称不能为空。");
            return;
          }
          closeModal();
          await onSubmit(name);
        },
      },
    ],
  });
  setTimeout(() => {
    box.focus();
    box.select();
  }, 30);
}

async function renameProject(project) {
  promptName({
    title: "重命名作品",
    desc: `内部编号 ${project.project_id} 不会改变。`,
    value: project.title || project.project_id,
    onSubmit: async (title) => {
      const result = await call("rename_project", project.project_id, title);
      state.workspace = result.workspace || [];
      renderTree();
      if (state.projectId === project.project_id) {
        $("projectChip").textContent = title;
        await loadOverview(project.project_id);
      }
      toast("作品已重命名。");
    },
  });
}

async function renameChapter(projectId, chapter) {
  promptName({
    title: "重命名章节",
    desc: `章节编号 ${chapter.chapter_id} 不会改变。`,
    value: chapter.title || chapter.chapter_id,
    onSubmit: async (title) => {
      const result = await call("rename_chapter", projectId, chapter.chapter_id, title);
      state.workspace = result.workspace || [];
      renderTree();
      if (state.projectId === projectId && state.chapterId === chapter.chapter_id) {
        const hint = $("draftHint").textContent;
        $("draftTitle").textContent = state.draftId
          ? `${chapter.chapter_id} · ${title}`
          : title;
        $("draftHint").textContent = hint;
      }
      toast("章节已重命名。");
    },
  });
}

function confirmTyped({ title, desc, phrase, onConfirm }) {
  const box = input("", { placeholder: phrase });
  const note = document.createElement("p");
  note.textContent = `请输入：${phrase}`;
  const body = document.createElement("div");
  body.append(note, field("确认语句", box));
  openModal({
    title,
    desc,
    body,
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "确认",
        style: "success",
        onClick: async () => {
          if (box.value.trim() !== phrase) {
            toast(`未输入“${phrase}”，已取消。`);
            return;
          }
          closeModal();
          await onConfirm();
        },
      },
    ],
  });
}

async function deleteProject(project) {
  confirmTyped({
    title: "删除作品",
    desc: `将删除整个作品：${project.title}\n\n作品目录会移入回收站，草稿、定稿、设置和本作品密钥都会一起移走。`,
    phrase: "确认删除",
    onConfirm: async () => {
      const result = await call("delete_project", project.project_id, "确认删除");
      state.workspace = result.workspace || [];
      state.projectId = state.workspace[0]?.project_id || "";
      state.chapterId = "";
      state.draftId = "";
      $("editor").value = "";
      renderTree();
      if (state.projectId) await selectProject(state.projectId);
      toast("作品已移入回收站。");
    },
  });
}

async function deleteChapterDrafts(projectId, chapter) {
  const note = document.createElement("p");
  note.textContent = `将删除章节 ${chapter.chapter_id} 的草稿、AI审稿和精修请求。已确认章节会保留，相关文件先移入回收站。`;
  openModal({
    title: "删除本章草稿",
    desc: chapter.title || chapter.chapter_id,
    body: note,
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "删除草稿",
        style: "success",
        onClick: async () => {
          const result = await call("delete_chapter_drafts", projectId, chapter.chapter_id);
          closeModal();
          await applyWorkspaceResult(result, projectId);
          const deleted = (result.result?.deleted_draft_ids || []).length;
          toast(`已删除本章草稿 ${deleted} 个。`);
        },
      },
    ],
  });
}

async function deleteConfirmedChapter(projectId, chapter) {
  confirmTyped({
    title: "删除已确认章节",
    desc: `将删除已确认章节：${chapter.chapter_id}\n标题：${chapter.title || ""}\n\n定稿和该章草稿都会移入回收站。若只想清草稿，请改用“删除本章草稿”。`,
    phrase: "确认删除定稿",
    onConfirm: async () => {
      const result = await call("delete_confirmed_chapter", projectId, chapter.chapter_id, "确认删除定稿");
      await applyWorkspaceResult(result, projectId);
      toast("已确认章节已移入回收站。");
    },
  });
}

async function maybeOfferAutoMemory(projectId) {
  let candidate;
  try {
    candidate = await call("memory_auto_candidate", projectId);
  } catch (error) {
    return;
  }
  if (!candidate?.ready) return;
  const note = document.createElement("p");
  note.textContent = candidate.confirm_text || "已累计足够章节，可以生成记忆银行草稿。";
  openModal({
    title: "自动记忆总结",
    desc: "生成结果先写入记忆库编辑区，仍需你保存后才会进入记忆银行。",
    body: note,
    actions: [
      { label: "暂不生成", onClick: closeModal },
      {
        label: "开始生成",
        style: "primary",
        onClick: async () => {
          closeModal();
          await openMemoryStudio();
          const ids = candidate.source_chapter_ids || [];
          studio.checked = new Set(ids);
          renderMemoryStudio();
          await runMemoryJob("generate_memory", "正在根据已确认章节生成记忆…");
        },
      },
    ],
  });
}

async function showProjectHealth() {
  if (!requireProject()) return;
  const data = await call("project_health_detail", state.projectId);
  openDrawer({
    kicker: currentProject()?.title || state.projectId,
    title: "作品概览",
    content: `${data.summary}\n\n${data.providers}`,
  });
}

async function showRecentModelCalls() {
  await openRecordsStudio("calls");
}

async function showAbout() {
  const data = await call("about");
  openDrawer({ kicker: "帮助", title: data.title, content: data.text });
}

async function emptyTrash() {
  const note = document.createElement("p");
  note.textContent = "将彻底删除当前项目库下所有回收站文件，包括被删除的作品和草稿。清空后不能从软件内恢复。";
  openModal({
    title: "清空回收站",
    desc: "这是不可恢复的清理。",
    body: note,
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "清空",
        style: "success",
        onClick: async () => {
          const result = await call("empty_trash");
          closeModal();
          toast(`回收站已清空：删除 ${result.removed_count || 0} 项。`);
        },
      },
    ],
  });
}

function draftInWorkspace(projectId, draftId) {
  if (!projectId || !draftId) return false;
  const project = (state.workspace || []).find((item) => item.project_id === projectId);
  return Boolean(
    project?.chapters?.some((chapter) => (chapter.drafts || []).some((draft) => draft.draft_id === draftId))
  );
}

function clearEditorBuffer() {
  state.navigationId += 1;
  clearTimeout(state.saveTimer);
  state.saveTimer = 0;
  state.savedSnapshot = null;
  state.dirty = false;
  state.saveError = "";
  state.draftId = "";
  state.chapterId = "";
  state.draftIds = [];
  state.draftIndex = -1;
  $("editor").value = "";
  $("draftTitle").textContent = "开始写作";
  $("draftHint").textContent = "";
  $("versionLabel").textContent = "—";
  state.hasReview = false;
  state.reviewText = "";
  state.reviewNotice = "";
  state.reviewBox = null;
  setReviewBadge(false);
  updateCountPill();
  updateDock();
}

async function changeDataRoot() {
  if (blockIfGenerating()) return;
  if (studio.mode && !(await guardStudioLeave())) return;
  if (!(await flushSave()).ok || blockIfGenerating()) return;
  const editor = $("editor");
  state.changingRoot = true;
  const wasReadOnly = editor.readOnly;
  editor.readOnly = true;
  try {
    const result = await call("choose_data_root");
    clearEditorBuffer();
    state.projectId = "";
    state.projectsRoot = result.projectsRoot;
    state.workspace = result.workspace || [];
    state.memoryReminders = [];
    state.memoryReminderShown.clear();
    state.inputBudgetNotice = null;
    state.inputBudgetRetry = null;
    $("inputBudgetPanel").hidden = true;
    $("inputBudgetEntry").hidden = true;
    closeDrawer();
    await closeStudio({ discard: true });
    if (window.ThinkTrace && ThinkTrace.isIdle()) ThinkTrace.dispose();
    ["outline", "world"].forEach(kind => {
      const pane = $(`pane-${kind}`);
      if (pane) { pane.dataset.selected = ""; pane.dataset.projectId = ""; }
    });
    state.projectId = state.workspace[0]?.project_id || "";
    $("projectChip").textContent = currentProject()?.title || "未选择作品";
    renderTree();
    if (state.projectId) await loadOverview(state.projectId);
    else $("summaryText").textContent = "当前项目库没有作品。";
    await refreshModelPill();
    toast("已切换项目库，旧编辑已保存在原库。");
  } catch (error) {
    if (!error.cancelled) toast(error.message);
  } finally {
    state.changingRoot = false;
    editor.readOnly = wasReadOnly;
  }
}

async function exportProjectPackage(projectId) {
  if (blockIfGenerating()) return;
  if (!projectId) {
    toast("请先选择作品。");
    return;
  }
  if (projectId === state.projectId && !(await flushSave()).ok) return;
  try {
    await call("export_project_package", projectId);
    toast("作品包已导出。");
  } catch (error) {
    if (!error.cancelled) toast(error.message);
  }
}

function openPackageSheet() {
  const body = document.createElement("div");
  body.className = "stack";
  const exportCurrent = document.createElement("button");
  exportCurrent.type = "button";
  exportCurrent.className = "btn quiet block";
  exportCurrent.textContent = "导出当前作品包…";
  exportCurrent.addEventListener("click", async () => {
    if (!state.projectId) {
      toast("请先选择作品。");
      return;
    }
    closeModal();
    await exportProjectPackage(state.projectId);
  });
  const importPkg = document.createElement("button");
  importPkg.type = "button";
  importPkg.className = "btn quiet block";
  importPkg.textContent = "导入作品包…";
  importPkg.addEventListener("click", async () => {
    closeModal();
    await importProjectPackage();
  });
  body.append(exportCurrent, importPkg);
  openModal({
    title: "导入导出",
    desc: "把整部作品打包带走，或从作品包恢复到当前项目库。作品包包含草稿、大纲、人物、记忆和审稿，不含 API Key。「导出 TXT」仍然只导出已确认章节正文。",
    body,
    actions: [{ label: "取消", onClick: closeModal }],
  });
}

async function importProjectPackage() {
  if (blockIfGenerating()) return;
  let inspect;
  try {
    inspect = await call("pick_and_inspect_project_package");
  } catch (error) {
    if (!error.cancelled) toast(error.message);
    return;
  }
  openImportConfirmModal(inspect);
}

function openImportConfirmModal(inspect) {
  const conflict = Boolean(inspect.conflict);
  const valid = Boolean(inspect.source_project_id_valid);
  const canKeep = valid && !conflict;
  const canOverwrite = conflict && valid;
  const suggested = inspect.suggested_new_project_id || "";
  const inventory = inspect.inventory || {};
  const defaultMode = canKeep ? "keep_id" : "new_id";
  const body = document.createElement("div");
  body.className = "stack";
  const summary = document.createElement("p");
  summary.style.whiteSpace = "pre-wrap";
  summary.textContent = [
    `作品：《${inspect.title || inspect.source_project_id}》`,
    `原编号：${inspect.source_project_id}`,
    `导出时间：${inspect.exported_at || "—"}`,
    `内容：定稿 ${inventory.confirmed_chapter_count || 0} · 草稿 ${inventory.draft_count || 0} · 审稿 ${inventory.review_count || 0} · 资料 ${inventory.planning_item_count || 0} · 记忆 ${inventory.memory_bank_item_count || 0}`,
  ].join("\n");
  const list = document.createElement("div");
  list.className = "choice-list";
  const radios = [];
  function addChoice(mode, label) {
    const wrap = document.createElement("label");
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "import-mode";
    radio.value = mode;
    radio.checked = mode === defaultMode;
    const text = document.createElement("span");
    text.textContent = label;
    wrap.append(radio, text);
    list.append(wrap);
    radios.push(radio);
    radio.addEventListener("change", syncOverwrite);
  }
  if (canKeep) addChoice("keep_id", "沿用原编号导入");
  addChoice("new_id", `作为新作品导入（编号将为 ${suggested}）`);
  if (canOverwrite) {
    addChoice(
      "overwrite",
      `覆盖已有作品「${inspect.existing_title || inspect.source_project_id}」（编号 ${inspect.source_project_id}）`
    );
  }
  const confirmWrap = document.createElement("div");
  confirmWrap.hidden = true;
  const box = input("", { placeholder: "确认覆盖" });
  const note = document.createElement("p");
  note.textContent = "请输入：确认覆盖";
  confirmWrap.append(note, field("确认语句", box));
  function selectedMode() {
    return radios.find((item) => item.checked)?.value || defaultMode;
  }
  function syncOverwrite() {
    confirmWrap.hidden = selectedMode() !== "overwrite";
  }
  syncOverwrite();
  body.append(summary, list, confirmWrap);
  openModal({
    title: "导入作品包",
    desc: "",
    body,
    actions: [
      { label: "取消", onClick: closeModal },
      {
        label: "开始导入",
        style: "success",
        onClick: async () => {
          const mode = selectedMode();
          const confirmText = mode === "overwrite" ? box.value.trim() : "";
          if (mode === "overwrite" && confirmText !== "确认覆盖") {
            toast("未输入「确认覆盖」，已取消。");
            return;
          }
          closeModal();
          await runImportPackage(inspect, mode, confirmText);
        },
      },
    ],
  });
}

async function runImportPackage(inspect, mode, confirmText) {
  if (blockIfGenerating()) return;
  const previousProjectId = state.projectId;
  const previousDraftId = state.draftId;
  if (!(await flushSave()).ok) return;
  clearTimeout(state.saveTimer);
  state.saveTimer = 0;
  state.importing = true;
  $("editor").readOnly = true;
  try {
    const result = await call(
      "import_project_package",
      inspect.path,
      mode,
      confirmText || "",
      mode === "new_id" ? inspect.suggested_new_project_id || "" : ""
    );
    const imported = result.imported || {};
    state.workspace = result.workspace || [];
    renderTree();
    const importedId = imported.project_id || "";
    // 同 id 覆盖：必须 force 重载磁盘正文。不同 id：先清空再 select，避免旧 draftId 写到新作品。
    if (importedId && importedId === previousProjectId) {
      if (previousDraftId && draftInWorkspace(importedId, previousDraftId)) {
        try {
          await loadDraft(importedId, previousDraftId, { force: true });
        } catch (error) {
          clearEditorBuffer();
          toast(error.message || "加载失败");
        }
      } else {
        clearEditorBuffer();
      }
    } else {
      clearEditorBuffer();
      if (importedId) await selectProject(importedId);
    }
    if (importedId) await loadOverview(importedId);
    const title = imported.title || importedId;
    if (mode === "overwrite") toast(`已导入作品《${title}》。`);
    else toast(`已导入作品《${title}》。请在模型设置中重新填写 API Key。`);
  } catch (error) {
    if (!error.cancelled) toast(error.message);
  } finally {
    state.importing = false;
    if (!state.generating) $("editor").readOnly = false;
  }
}

async function applyWorkspaceResult(result, projectId) {
  state.workspace = result.workspace || [];
  if (state.draftId && state.projectId === projectId) {
    const stillThere = state.workspace
      .find((item) => item.project_id === projectId)
      ?.chapters?.some((chapter) => (chapter.drafts || []).some((draft) => draft.draft_id === state.draftId));
    if (!stillThere) {
      state.draftId = "";
      state.chapterId = "";
      $("editor").value = "";
      $("draftTitle").textContent = "开始写作";
      setReviewBadge(false);
    }
  }
  renderTree();
  await loadOverview(projectId);
}

function bindEvents() {
  $("studioBody").addEventListener("input", refreshStudioSaveStatus);
  $("studioBody").addEventListener("change", refreshStudioSaveStatus);
  $("inputBudgetClose").addEventListener("click", () => { $("inputBudgetPanel").hidden = true; });
  $("inputBudgetEntry").addEventListener("click", () => {
    const notice = state.inputBudgetNotice;
    if (notice && notice.projectId === state.projectId) $("inputBudgetPanel").hidden = false;
  });
  $("retryInputBudgetBtn").addEventListener("click", () => retryInputBudget().catch(error => toast(error.message)));
  [["raiseInputBudgetBtn", "raise"], ["reduceInputChaptersBtn", "chapters"], ["editInputMemoryBtn", "memory"]].forEach(([id, kind]) => {
    $(id).addEventListener("click", () => adjustInputBudget(kind).catch(error => toast(error.message)));
  });
  $("searchInput").addEventListener("input", () => {
    if (!searchQuery()) {
      state.treeSearchOpen = { projects: Object.create(null), groups: Object.create(null) };
      revealInTree(state.projectId, state.chapterId);
    }
    renderTree();
  });
  $("refreshBtn").addEventListener("click", () => refreshWorkspace().catch((error) => toast(error.message)));
  $("newProjectBtn").addEventListener("click", () => createProject().catch((error) => toast(error.message)));
  $("newChapterBtn").addEventListener("click", () => generateChapter().catch((error) => toast(error.message)));
  $("settingsBtn").addEventListener("click", openSettings);
  $("focusBtn").addEventListener("click", () => toggleFocus().catch((error) => toast(error.message)));
  $("inspectorToggle").addEventListener("click", () => toggleInspector().catch((error) => toast(error.message)));
  $("modelPill").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleModelMenu().catch((error) => toast(error.message));
  });
  $("modelMenu").addEventListener("click", (event) => event.stopPropagation());
  $("genBtn").addEventListener("click", () => openGenSettings("global").catch((error) => toast(error.message)));
  $("healthBtn").addEventListener("click", () => showProjectHealth().catch((error) => toast(error.message)));
  $("recordsBtn").addEventListener("click", () => openRecordsStudio("connection").catch((error) => toast(error.message)));
  $("aboutBtn").addEventListener("click", () => showAbout().catch((error) => toast(error.message)));
  $("trashBtn").addEventListener("click", () => emptyTrash().catch((error) => toast(error.message)));
  $("historyBackupsBtn").addEventListener("click", () => openBackupStudio().catch(error => toast(error.message)));
  ThinkTrace.bind();
  $("modelBtn").addEventListener("click", () => openModelStudio().catch((error) => toast(error.message)));
  $("widthBtn").addEventListener("click", async () => {
    state.prefs.editorWidth = state.prefs.editorWidth === "fill" ? "comfort" : "fill";
    applyPrefs();
    try {
      await call("save_prefs", { editorWidth: state.prefs.editorWidth });
    } catch (error) {
      toast(error.message);
    }
  });
  $("inspectorTabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-tab]");
    if (!tab) return;
    setInspectorTab(tab.dataset.tab);
  });
  $("dataRootBtn").addEventListener("click", () => changeDataRoot().catch(error => toast(error.message)));
  $("openFolderBtn").addEventListener("click", async () => {
    if (!state.projectId) return toast("请先选择作品。");
    try {
      await call("open_folder", "project", state.projectId);
    } catch (error) {
      toast(error.message);
    }
  });
  $("exportBtn").addEventListener("click", async () => {
    if (!state.projectId) return toast("请先选择作品。");
    try {
      if (blockIfGenerating() || !(await flushSave()).ok) return;
      await call("export_txt", state.projectId);
      toast("已导出 TXT。");
    } catch (error) {
      if (!error.cancelled) toast(error.message);
    }
  });
  $("packageBtn").addEventListener("click", () => openPackageSheet());
  $("prevBtn").addEventListener("click", async () => {
    if (state.draftIndex > 0) {
      await loadDraft(state.projectId, state.draftIds[state.draftIndex - 1]);
    }
  });
  $("nextBtn").addEventListener("click", async () => {
    if (state.draftIndex >= 0 && state.draftIndex < state.draftIds.length - 1) {
      await loadDraft(state.projectId, state.draftIds[state.draftIndex + 1]);
    }
  });
  $("rewriteBtn").addEventListener("click", () => rewriteDraft().catch((error) => toast(error.message)));
  $("refineBtn").addEventListener("click", () => refineDraft().catch((error) => toast(error.message)));
  $("reviewBtn").addEventListener("click", () => reviewDraft().catch((error) => toast(error.message)));
  const stopTask = async () => {
    try {
      const result = await call("cancel_job", state.activeJobId);
      toast(result.message);
      if (result.stopping && state.generating) {
        ["cancelJobBtn", "cancelStudioJobBtn"].forEach(id => {
          $(id).disabled = true;
          $(id).textContent = "正在停止…";
        });
      }
    } catch (error) { toast(error.message); }
  };
  $("cancelJobBtn").addEventListener("click", stopTask);
  $("cancelStudioJobBtn").addEventListener("click", stopTask);
  $("confirmBtn").addEventListener("click", () => confirmDraft().catch((error) => toast(error.message)));
  $("editor").addEventListener("input", scheduleSave);
  $("editor").addEventListener("select", updateCountPill);
  $("editor").addEventListener("keyup", updateCountPill);
  $("editor").addEventListener("mouseup", updateCountPill);
  $("editor").addEventListener("scroll", () => {
    const el = $("editor");
    state.follow = el.scrollTop + el.clientHeight >= el.scrollHeight - 48;
  });
  $("studioClose").addEventListener("click", () => closeStudio());
  $("drawerClose").addEventListener("click", closeDrawer);
  $("modal").addEventListener("click", (event) => {
    if (event.target === $("modal")) closeModal();
  });
  document.addEventListener("click", () => {
    hideTreeMenu();
    hideModelMenu();
  });
  document.addEventListener("contextmenu", (event) => {
    if (!$("tree").contains(event.target)) hideTreeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (studio.mode) saveActiveStudio();
      else saveDraft();
    }
    if ((event.ctrlKey || event.metaKey) && event.key === ",") {
      event.preventDefault();
      openSettings();
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "\\") {
      event.preventDefault();
      toggleFocus();
    }
    if (event.key === "Escape") {
      if (state.modalCancel) { closeModal(); return; }
      if (!$("inputBudgetPanel").hidden) {
        $("inputBudgetPanel").hidden = true;
        return;
      }
      if (window.ThinkTrace && ThinkTrace.isOpen()) {
        ThinkTrace.close();
        return;
      }
      hideTreeMenu();
      hideModelMenu();
      closeModal();
      closeDrawer();
      closeStudio();
    }
  });
}

window.__workbenchPush = function workbenchPush(event, payload) {
  if (event === "job_started") {
    if (payload.job_id > state.lastJobId) {
      state.lastJobId = payload.job_id;
      state.activeJobId = payload.job_id;
      // The backend counts all jobs, including jobs without a thinking panel.
      if (window.ThinkTrace) ThinkTrace.acceptJob(payload.job_id);
      state.inputBudgetNotice = null;
      $("inputBudgetPanel").hidden = true;
      $("inputBudgetEntry").hidden = true;
    }
    return;
  }
  if (payload?.job_id > state.lastJobId && state.generating) {
    state.lastJobId = payload.job_id;
    state.activeJobId = payload.job_id;
  }
  if (payload?.job_id && payload.job_id !== state.activeJobId) return;
  if (event.endsWith("_done")) state.activeJobId = 0;
  if (window.ThinkTrace && ThinkTrace.handle(event, payload)) return;
  if (event === "draft_chunk") appendEditor(payload?.text || "", payload?.chapter_id || "");
  if (event === "review_chunk" && state.reviewBox) {
    state.reviewBox.textContent += payload?.text || "";
    state.reviewBox.scrollIntoView({ block: "end", behavior: "smooth" });
  }
  if (event === "draft_done") finishDraft(payload);
  if (event === "review_done") finishReview(payload);
  handleStudioPush(event, payload);
  if (payload?.input_budget) {
    const retry = state.inputBudgetRetry;
    const feature = { generate_draft: "draft_generation", rewrite_draft: "draft_generation",
      refine_draft: "ai_refinement", ai_review: "ai_review" }[retry?.method];
    showInputBudgetNotice(payload.input_budget, state.projectId,
      feature === payload.input_budget.feature_id ? retry : null);
  }
  if (event.endsWith("_done")) state.inputBudgetRetry = null;
};

window.__workbenchFlushBeforeClose = async function workbenchFlushBeforeClose(attemptId = 0) {
  state.closeAttempt = Number(attemptId) || 0;
  if (state.changingRoot) return { ok: false, error: "正在切换项目库，请稍候。" };
  if (state.generating) {
    const error = "请等待当前任务完成，或点击“停止任务”后再关闭。";
    toast(error);
    return { ok: false, error };
  }
  if (studio.mode) {
    const waiting = studioHasChanges();
    if (waiting) await call("wait_close_decision", state.closeAttempt, true);
    try { if (!(await guardStudioLeave())) return { ok: false }; }
    finally { if (waiting) await call("wait_close_decision", state.closeAttempt, false); }
  }
  const editor = $("editor");
  state.closeEditorWasReadOnly = Boolean(editor?.readOnly);
  state.closing = true;
  const pendingSave = flushSave();
  if (editor) editor.readOnly = true;
  const result = await pendingSave;
  if (!result?.ok) {
    state.closing = false;
    if (editor) editor.readOnly = state.closeEditorWasReadOnly;
  }
  return result || { ok: true };
};

window.__workbenchCancelClose = function workbenchCancelClose(attemptId = 0, message = "") {
  if ((Number(attemptId) || 0) !== state.closeAttempt) return;
  state.closing = false;
  const editor = $("editor");
  if (editor) editor.readOnly = state.closeEditorWasReadOnly;
  if (message) toast(message);
};

async function boot() {
  $("refreshBtn").innerHTML = iconSvg("refresh");
  $("drawerClose").innerHTML = iconSvg("close");
  $("studioClose").textContent = "关闭";
  bindEvents();
  applyPrefs();
  setInterval(refreshSavePill, 5000);
  const data = await call("bootstrap");
  state.projectsRoot = data.projectsRoot || "";
  state.prefs = { ...state.prefs, ...(data.prefs || {}) };
  state.workspace = data.workspace || [];
  applyPrefs();
  await refreshModelPill();
  if (state.workspace[0]) await selectProject(state.workspace[0].project_id);
  renderTree();
  state.ready = true;
}

window.addEventListener("pywebviewready", () => {
  boot().catch((error) => toast(error.message));
});
