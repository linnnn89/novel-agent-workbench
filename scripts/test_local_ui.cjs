// Run production app.js with a small DOM/bridge double; no browser or paid API.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/novel_agent_workbench/modern_ui/app.js"), "utf8");
let checks = 0;
function harness() {
  const elements = new Map();
  const element = () => ({ value: "", textContent: "", hidden: true, readOnly: false, disabled: false,
    dataset: {}, classList: { add() {}, remove() {}, toggle() {} }, style: { setProperty() {} },
    append() {}, removeAttribute() {}, setAttribute() {}, focus() {}, scrollTo() {}, scrollIntoView() {} });
  const get = (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  const context = { console, setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    document: { getElementById: get, createElement: element },
    window: { addEventListener() {} }, studio: { mode: "" },
    ThinkTrace: { start() {}, finish() {}, handle: () => false, isIdle: () => true, dispose() {} } };
  vm.createContext(context);
  vm.runInContext(source + "\nglobalThis.S = state;", context);
  Object.assign(context, { renderTree() {}, revealInTree() {}, loadOverview: async () => {},
    setReviewBadge() {}, refreshWorkspace: async () => {}, renderInspector() {},
    setInspectorTab() {}, handleStudioPush() {}, toast: (text) => { context.lastToast = text; },
    openModal: (options) => { context.dialog = options; }, openDrawer: (options) => { context.drawer = options; } });
  Object.assign(context.S, { projectId: "p", draftId: "old", chapterId: "chapter_1", draftIds: ["old"], draftIndex: 0 });
  get("editor").value = "尚未保存的新正文";
  context.get = get;
  context.calls = [];
  context.call = async (name, ...args) => {
    context.calls.push([name, ...args]);
    if (name === "save_draft") throw new Error("磁盘写入失败");
    return { project_id: "p", chapter_id: "chapter_2", draft_id: "new", content: "另一章", draft_ids: ["new"] };
  };
  return context;
}
async function check(name, test) { await test(); checks++; console.log(`PASS ${name}`); }

(async () => {
  for (const [name, operation] of [
    ["保存失败阻止打开草稿", c => c.loadDraft("p", "new")],
    ["保存失败阻止重新打开当前草稿", c => c.loadDraft("p", "old")],
    ["保存失败阻止切换作品", c => c.selectProject("other")],
    ["保存失败阻止切换章节", c => c.openChapter("p", { chapter_id: "chapter_2" })],
    ["保存失败阻止确认", c => c.confirmDraft()],
    ["保存失败阻止重写", c => c.rewriteDraft()],
    ["保存失败阻止本地审稿", c => c.localReviewCurrent()],
    ["保存失败阻止作品导出", c => c.exportProjectPackage("p")],
    ["保存失败阻止覆盖导入", c => c.runImportPackage({}, "replace", "")],
  ]) await check(name, async () => {
    const c = harness(); await operation(c);
    assert.equal(c.S.draftId, "old"); assert.equal(c.S.projectId, "p");
    assert.equal(c.get("editor").value, "尚未保存的新正文");
    assert.deepEqual(c.calls.map(call => call[0]), ["save_draft"]);
    assert.equal(c.dialog, undefined);
  });

  await check("保存失败标记不会被计时刷新冒充成功", async () => {
    const c = harness(); c.S.lastSavedAt = Date.now(); await c.saveDraft(); c.refreshSavePill();
    assert.match(c.get("savePill").textContent, /保存失败/);
  });

  await check("右键动作在打开失败后不作用于旧稿件", async () => {
    const c = harness(); let called = false;
    await c.runOnDraft("p", "new", async () => { called = true; });
    assert.equal(called, false);
  });

  await check("连续关闭/切换共用同一次保存且保留失败", async () => {
    const c = harness(); let reject;
    c.call = () => new Promise((_, failure) => { reject = failure; });
    const first = c.flushSave(), second = c.flushSave();
    await new Promise(setImmediate); assert.equal(c.get("editor").readOnly, true);
    reject(new Error("失败"));
    assert.equal((await first).ok, false); assert.equal((await second).ok, false);
    assert.equal(c.get("editor").readOnly, false);
  });

  await check("相同正文不重复请求保存", async () => {
    const c = harness(); let writes = 0;
    c.call = async () => { writes++; return { changed: true }; };
    await c.saveDraft(); await c.saveDraft();
    assert.equal(writes, 1);
    c.get("editor").value += "新增"; await c.saveDraft(); assert.equal(writes, 2);
  });

  await check("重新打开后首次保存仍核对磁盘状态", async () => {
    const c = harness(); let writes = 0;
    c.S.draftId = "";
    c.call = async name => {
      if (name === "save_draft") { writes++; return { changed: false }; }
      return { project_id: "p", chapter_id: "chapter_1", draft_id: "old", content: "磁盘中的正文", draft_ids: ["old"] };
    };
    await c.loadDraft("p", "old"); await c.flushSave(); await c.flushSave();
    assert.equal(writes, 1);
  });

  await check("确认章节修改只提醒一次且不调用AI或改写记忆", async () => {
    const c = harness();
    c.call = async (name) => { assert.equal(name, "save_draft"); return {
      memory_reminder: { chapter_id: "chapter_1", message: "请手工核对" } }; };
    await c.saveDraft(); c.get("editor").value += "再编辑"; await c.saveDraft();
    assert.equal(c.S.memoryReminders.length, 1);
    c.showMemoryReminder(); assert.equal(c.dialog.title, "请核对记忆银行");
  });

  await check("生成前保存失败保留原稿", async () => {
    const c = harness();
    c.call = async (name) => {
      if (name === "save_draft") throw new Error("写入失败");
      if (name === "chapter_input") return { chapter_id: "chapter_2", title: "", prompt: "写作" };
      assert.equal(name, "suggest_chapter"); return { chapter_id: "chapter_2", default_prompt: "写作" };
    };
    // Inputs and form layout are presentation-only doubles.
    c.input = value => ({ value, addEventListener() {} }); c.field = () => ({});
    await c.generateChapter();
    await c.dialog.actions.find(a => a.label === "生成草稿").onClick();
    assert.equal(c.S.draftId, "old"); assert.equal(c.get("editor").value, "尚未保存的新正文");
  });

  await check("失败或停止恢复原稿并保留可复制片段", async () => {
    const c = harness(); c.beginStream("p", "chapter_1", "重写"); c.appendEditor("生成了一半");
    await c.finishDraft({ ok: false, cancelled: true, error: "已停止" });
    assert.equal(c.S.draftId, "old"); assert.equal(c.get("editor").value, "尚未保存的新正文");
    assert.equal(c.drawer.content, "生成了一半"); assert.equal(c.get("editor").readOnly, false);
  });

  await check("连续点击重写只启动一个任务且保留正确原稿", async () => {
    const c = harness(); let jobs = 0;
    c.promptText = options => { c.rewriteDialog = options; };
    c.call = async name => { if (name === "rewrite_draft") jobs++; return {}; };
    await c.rewriteDraft();
    await Promise.all([c.rewriteDialog.onSubmit("重写"), c.rewriteDialog.onSubmit("重写")]);
    assert.equal(jobs, 1);
    assert.equal(c.S.streamSource.draftId, "old");
    assert.equal(c.S.generating, true);
  });

  await check("旧任务的迟到内容和完成通知被忽略", async () => {
    const c = harness(); c.S.generating = true; c.get("editor").value = "";
    c.window.__workbenchPush("job_started", { job_id: 1 });
    c.window.__workbenchPush("job_started", { job_id: 2 });
    c.window.__workbenchPush("draft_chunk", { job_id: 1, text: "旧内容" });
    c.window.__workbenchPush("draft_done", { job_id: 1, ok: false });
    assert.equal(c.get("editor").value, ""); assert.equal(c.S.generating, true);
    c.window.__workbenchPush("draft_chunk", { job_id: 2, text: "新内容" });
    assert.equal(c.get("editor").value, "新内容");
  });

  await check("关闭时保存失败维持编辑区可用", async () => {
    const c = harness(); const result = await c.window.__workbenchFlushBeforeClose(1);
    assert.equal(result.ok, false); assert.equal(c.get("editor").readOnly, false); assert.equal(c.S.closing, false);
  });

  await check("两次打开响应乱序时保留最后选择", async () => {
    const c = harness(); const resolvers = {};
    c.call = async (name, project, draft) => {
      if (name === "save_draft") return {};
      return new Promise(resolve => { resolvers[draft] = resolve; });
    };
    const first = c.loadDraft("p", "first"); await new Promise(setImmediate);
    const second = c.loadDraft("p", "second"); await new Promise(setImmediate);
    const data = id => ({ project_id: "p", chapter_id: "chapter_2", draft_id: id, content: id, draft_ids: [id] });
    resolvers.second(data("second")); await second;
    resolvers.first(data("first")); await first;
    assert.equal(c.S.draftId, "second"); assert.equal(c.get("editor").readOnly, false);
  });
  console.log(`Completed ${checks} UI regression checks.`);
})().catch(error => { console.error(error); process.exitCode = 1; });
