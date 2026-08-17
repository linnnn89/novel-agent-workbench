const FONTS = {
  literary: { label: "衬线文学体", value: "var(--font-literary)" },
  sans: { label: "现代黑体", value: "var(--font-sans)" },
  kai: { label: "楷体手感", value: "var(--font-kai)" },
  mono: { label: "等宽草稿", value: "var(--font-mono)" },
};

const state = {
  ready: false,
  workspace: [],
  prefs: { theme: "system", fontFamily: "literary", fontSize: 16, focusMode: false },
  projectId: "",
  chapterId: "",
  draftId: "",
  draftIds: [],
  draftIndex: -1,
  generating: false,
  follow: true,
  saveTimer: 0,
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
  $("app").classList.toggle("focus-mode", Boolean(state.prefs.focusMode));
  $("focusBtn").textContent = state.prefs.focusMode ? "退出专注" : "专注";
}

function countChars(text) {
  return Array.from(String(text || "").replace(/\s+/g, "")).length;
}

function setBusy(busy, label) {
  state.generating = busy;
  $("streamVeil").hidden = !busy;
  $("streamLabel").textContent = label || "模型正在书写…";
  $("editor").disabled = busy;
  ["rewriteBtn", "refineBtn", "reviewBtn", "confirmBtn", "newChapterBtn"].forEach((id) => {
    $(id).disabled = busy;
  });
}

function closeModal() {
  $("modal").hidden = true;
  $("modalBody").innerHTML = "";
  $("modalFoot").innerHTML = "";
}

function openModal({ title, desc, body, actions }) {
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

function openDrawer({ kicker, title, content }) {
  $("drawerKicker").textContent = kicker || "";
  $("drawerTitle").textContent = title || "";
  $("drawerBody").innerHTML = "";
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

function renderTree() {
  const query = $("searchInput").value.trim().toLowerCase();
  const root = $("tree");
  root.innerHTML = "";
  state.workspace.forEach((project) => {
    const visibleChapters = (project.chapters || []).filter((chapter) => {
      if (!query) return true;
      const hay = `${project.title} ${project.project_id} ${chapter.title} ${chapter.chapter_id}`.toLowerCase();
      return hay.includes(query);
    });
    if (query && !visibleChapters.length && !`${project.title} ${project.project_id}`.toLowerCase().includes(query)) {
      return;
    }
    const box = document.createElement("div");
    box.className = `tree-project${project.project_id === state.projectId ? " active" : ""}`;
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = `<span class="tree-title">${escapeHtml(project.title)}</span>`;
    button.addEventListener("click", () => selectProject(project.project_id));
    button.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showTreeMenu(event, { kind: "project", project });
    });
    box.append(button);
    const list = document.createElement("div");
    list.className = "chapters";
    visibleChapters.forEach((chapter) => {
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
      list.append(row);
    });
    box.append(list);
    root.append(box);
  });
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

async function selectProject(projectId) {
  state.projectId = projectId;
  $("projectChip").textContent = currentProject()?.title || "未选择作品";
  renderTree();
  await loadOverview(projectId);
}

async function loadOverview(projectId) {
  const overview = await call("project_overview", projectId);
  $("projectChip").textContent = currentProject()?.title || projectId;
  $("modelPill").textContent = overview.model_status;
  $("summaryText").textContent = `章节 ${overview.chapter_count} · 草稿 ${overview.draft_count}\n已确认 ${overview.committed_chapter_count} · 审稿 ${overview.review_count}`;
  $("contextText").textContent = `大纲与资料 ${overview.planning_item_count} 项\n记忆库 ${overview.memory_bank_item_count} 项\n生成前会按预算组装，不会自动联网。`;
}

async function openChapter(projectId, chapter) {
  await selectProject(projectId);
  state.chapterId = chapter.chapter_id;
  const latest = [...(chapter.drafts || [])].pop();
  renderTree();
  if (latest?.draft_id) {
    await loadDraft(projectId, latest.draft_id);
  } else {
    $("draftTitle").textContent = chapter.title || chapter.chapter_id;
    $("draftHint").textContent = "这一章还没有可读草稿";
    $("editor").value = "";
    $("countPill").textContent = "字数 0";
  }
}

async function loadDraft(projectId, draftId, { silent = false } = {}) {
  const draft = await call("open_draft", projectId, draftId);
  state.projectId = draft.project_id;
  state.chapterId = draft.chapter_id;
  state.draftId = draft.draft_id;
  state.draftIds = draft.draft_ids || [];
  state.draftIndex = draft.index ?? -1;
  $("draftTitle").textContent = `${draft.chapter_id} · ${draft.title}`;
  $("draftHint").textContent = `${draft.version_label} · ${draft.status_label} · 编辑会自动保存`;
  $("versionLabel").textContent = draft.version_label;
  $("editor").value = draft.content || "";
  $("countPill").textContent = `字数 ${countChars(draft.content)}`;
  $("savePill").textContent = "已自动保存";
  $("prevBtn").disabled = state.draftIndex <= 0;
  $("nextBtn").disabled = state.draftIndex < 0 || state.draftIndex >= state.draftIds.length - 1;
  renderTree();
  if (!silent) $("editor").focus();
}

function scheduleSave() {
  $("countPill").textContent = `字数 ${countChars($("editor").value)}`;
  if (!state.draftId || state.generating) return;
  $("savePill").textContent = "保存中…";
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(saveDraft, 700);
}

async function saveDraft() {
  if (!state.projectId || !state.draftId || state.generating) return;
  try {
    await call("save_draft", state.projectId, state.draftId, $("editor").value);
    $("savePill").textContent = "已自动保存";
  } catch (error) {
    $("savePill").textContent = "保存失败";
    toast(error.message);
  }
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
        label: "预览格式",
        onClick: async () => {
          try {
            const preview = await call("preview_prompt", state.projectId, chapter.value.trim(), prompt.value);
            openDrawer({ kicker: "不会联网", title: "将发送给模型的结构", content: preview.details });
          } catch (error) {
            toast(error.message);
          }
        },
      },
      {
        label: "生成草稿",
        style: "primary",
        onClick: async () => {
          try {
            closeModal();
            beginStream(chapter.value.trim(), title.value.trim() || chapter.value.trim());
            await call("generate_draft", state.projectId, chapter.value.trim(), title.value.trim(), prompt.value);
          } catch (error) {
            setBusy(false);
            toast(error.message);
          }
        },
      },
    ],
  });
}

function beginStream(chapterId, title) {
  state.follow = true;
  state.chapterId = chapterId;
  state.draftId = "";
  $("draftTitle").textContent = `${chapterId} · ${title}`;
  $("draftHint").textContent = "正在生成草稿 · 返回文字会实时写入稿纸";
  $("editor").value = "";
  $("countPill").textContent = "字数 0";
  $("savePill").textContent = "正在生成…";
  const think = $("thinkBody");
  if (think) think.textContent = "";
  if ($("thinkPanel")) $("thinkPanel").hidden = true;
  setBusy(true, "模型正在书写…");
}

function appendThinking(text) {
  if (!text) return;
  const panel = $("thinkPanel");
  const body = $("thinkBody");
  if (!panel || !body) return;
  panel.hidden = false;
  body.textContent += text;
  body.parentElement.scrollTo({ top: body.parentElement.scrollHeight, behavior: "smooth" });
}

function appendEditor(text) {
  const editor = $("editor");
  editor.value += text;
  $("countPill").textContent = `字数 ${countChars(editor.value)}`;
  if (state.follow) {
    editor.scrollTo({ top: editor.scrollHeight, behavior: "smooth" });
  }
}

async function finishDraft(payload) {
  setBusy(false);
  if (!payload?.ok) {
    $("savePill").textContent = "生成失败";
    toast(payload?.error || "生成失败");
    return;
  }
  const draftId = payload.data?.draft_id;
  await refreshWorkspace();
  if (draftId) {
    await loadDraft(state.projectId, draftId, { silent: true });
    toast("新草稿已写入，尚未成为确认稿。");
  }
}

async function rewriteDraft() {
  if (!requireDraft()) return;
  await saveDraft();
  promptText({
    title: "重新生成",
    desc: "会生成一个全新版本，不会覆盖当前草稿，也不会参考上一版正文。",
    onSubmit: async (instruction) => {
      const project = currentProject();
      const chapter = project?.chapters?.find((item) => item.chapter_id === state.chapterId);
      beginStream(state.chapterId, chapter?.title || state.chapterId);
      try {
        await call("rewrite_draft", state.projectId, state.draftId, instruction);
      } catch (error) {
        setBusy(false);
        toast(error.message);
      }
    },
  });
}

async function refineDraft() {
  if (!requireDraft()) return;
  await saveDraft();
  promptText({
    title: "根据审稿精修",
    desc: "必须以当前 AI 审稿意见为主约束。没有审稿时不能精修。",
    onSubmit: async (instruction) => {
      beginStream(state.chapterId, `精修 ${state.chapterId}`);
      try {
        await call("refine_draft", state.projectId, state.draftId, instruction);
      } catch (error) {
        setBusy(false);
        toast(error.message);
      }
    },
  });
}

async function reviewDraft() {
  if (!requireDraft()) return;
  await saveDraft();
  try {
    const result = await call("ai_review", state.projectId, state.draftId);
    if (result?.existing) {
      openDrawer({ kicker: "已有审稿", title: `审稿 · ${result.review.chapter_id}`, content: result.review.details });
      return;
    }
    const box = document.createElement("div");
    box.className = "review-stream";
    box.textContent = "";
    openDrawer({ kicker: "AI 审稿", title: "正在阅读这一稿", content: box });
    setBusy(true, "正在审稿…");
    state.reviewBox = box;
  } catch (error) {
    toast(error.message);
  }
}

function finishReview(payload) {
  setBusy(false);
  if (!payload?.ok) {
    toast(payload?.error || "审稿失败");
    return;
  }
  const review = payload.data || {};
  openDrawer({ kicker: "AI 审稿完成", title: `审稿 · ${review.chapter_id || ""}`, content: review.details || review.comment || "暂无说明" });
  loadOverview(state.projectId).catch(() => {});
}

async function confirmDraft() {
  if (!requireDraft()) return;
  await saveDraft();
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
            const projectId = state.projectId;
            const draftId = state.draftId;
            await call("confirm_draft", projectId, draftId);
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
  const body = document.createElement("div");
  body.append(field("外观", theme), field("正文字体", font), field("正文字号", sizeRow));
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
  applyPrefs();
  await call("save_prefs", { focusMode: state.prefs.focusMode });
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
    { label: "生成草稿", onClick: () => generateChapter() },
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
    { label: "模型服务", onClick: () => openModelStudio() },
    { label: "打开作品文件夹", onClick: () => call("open_folder", "project", projectId) },
    "-",
    { label: "删除作品", danger: true, onClick: () => deleteProject(target.project) },
  ];
}

async function runOnChapterDraft(projectId, chapter, action) {
  await openChapter(projectId, chapter);
  await action();
}

async function runOnDraft(projectId, draftId, action) {
  await loadDraft(projectId, draftId, { silent: true });
  await action();
}

async function localReviewCurrent() {
  if (!requireDraft()) return;
  await saveDraft();
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
    }
  }
  renderTree();
  await loadOverview(projectId);
}

function bindEvents() {
  $("searchInput").addEventListener("input", renderTree);
  $("refreshBtn").addEventListener("click", () => refreshWorkspace().catch((error) => toast(error.message)));
  $("newProjectBtn").addEventListener("click", () => createProject().catch((error) => toast(error.message)));
  $("newChapterBtn").addEventListener("click", () => generateChapter().catch((error) => toast(error.message)));
  $("settingsBtn").addEventListener("click", openSettings);
  $("focusBtn").addEventListener("click", () => toggleFocus().catch((error) => toast(error.message)));
  $("genBtn").addEventListener("click", () => openGenSettings("global").catch((error) => toast(error.message)));
  $("healthBtn").addEventListener("click", () => showProjectHealth().catch((error) => toast(error.message)));
  $("aboutBtn").addEventListener("click", () => showAbout().catch((error) => toast(error.message)));
  $("trashBtn").addEventListener("click", () => emptyTrash().catch((error) => toast(error.message)));
  $("thinkClose").addEventListener("click", () => {
    $("thinkPanel").hidden = true;
  });
  $("modelBtn").addEventListener("click", () => openModelStudio().catch((error) => toast(error.message)));
  $("outlineBtn").addEventListener("click", () => openPlanningStudio("outline").catch((error) => toast(error.message)));
  $("worldBtn").addEventListener("click", () => openPlanningStudio("world").catch((error) => toast(error.message)));
  $("memoryBtn").addEventListener("click", () => openMemoryStudio().catch((error) => toast(error.message)));
  $("dataRootBtn").addEventListener("click", async () => {
    try {
      const result = await call("choose_data_root");
      state.workspace = result.workspace || [];
      state.projectId = state.workspace[0]?.project_id || "";
      renderTree();
      if (state.projectId) await selectProject(state.projectId);
      toast("已切换项目库。");
    } catch (error) {
      if (!error.cancelled) toast(error.message);
    }
  });
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
      await call("export_txt", state.projectId);
      toast("已导出 TXT。");
    } catch (error) {
      if (!error.cancelled) toast(error.message);
    }
  });
  $("prevBtn").addEventListener("click", async () => {
    if (state.draftIndex > 0) {
      await saveDraft();
      await loadDraft(state.projectId, state.draftIds[state.draftIndex - 1]);
    }
  });
  $("nextBtn").addEventListener("click", async () => {
    if (state.draftIndex >= 0 && state.draftIndex < state.draftIds.length - 1) {
      await saveDraft();
      await loadDraft(state.projectId, state.draftIds[state.draftIndex + 1]);
    }
  });
  $("rewriteBtn").addEventListener("click", () => rewriteDraft().catch((error) => toast(error.message)));
  $("refineBtn").addEventListener("click", () => refineDraft().catch((error) => toast(error.message)));
  $("reviewBtn").addEventListener("click", () => reviewDraft().catch((error) => toast(error.message)));
  $("confirmBtn").addEventListener("click", () => confirmDraft().catch((error) => toast(error.message)));
  $("editor").addEventListener("input", scheduleSave);
  $("editor").addEventListener("scroll", () => {
    const el = $("editor");
    state.follow = el.scrollTop + el.clientHeight >= el.scrollHeight - 48;
  });
  $("studioClose").addEventListener("click", closeStudio);
  $("drawerClose").addEventListener("click", closeDrawer);
  $("modal").addEventListener("click", (event) => {
    if (event.target === $("modal")) closeModal();
  });
  document.addEventListener("click", hideTreeMenu);
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
      hideTreeMenu();
      closeModal();
      closeDrawer();
      closeStudio();
    }
  });
}

window.__workbenchPush = function workbenchPush(event, payload) {
  if (event === "draft_chunk") appendEditor(payload?.text || "");
  if (event === "reason_chunk") appendThinking(payload?.text || "");
  if (event === "review_chunk" && state.reviewBox) {
    state.reviewBox.textContent += payload?.text || "";
    $("drawerBody").scrollTo({ top: $("drawerBody").scrollHeight, behavior: "smooth" });
  }
  if (event === "draft_done") finishDraft(payload);
  if (event === "review_done") finishReview(payload);
  handleStudioPush(event, payload);
};

async function boot() {
  bindEvents();
  applyPrefs();
  const data = await call("bootstrap");
  state.prefs = { ...state.prefs, ...(data.prefs || {}) };
  state.workspace = data.workspace || [];
  applyPrefs();
  if (state.workspace[0]) await selectProject(state.workspace[0].project_id);
  renderTree();
  state.ready = true;
}

window.addEventListener("pywebviewready", () => {
  boot().catch((error) => toast(error.message));
});
