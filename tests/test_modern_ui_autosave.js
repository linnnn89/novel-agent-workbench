const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");


function loadApp(saveDraft) {
  const nodes = new Map();
  const node = (id) => {
    if (!nodes.has(id)) {
      nodes.set(id, {
        classList: { add() {}, remove() {}, toggle() {} },
        hidden: false,
        readOnly: false,
        textContent: "",
        value: "",
      });
    }
    return nodes.get(id);
  };
  const context = {
    clearTimeout,
    console,
    document: {
      documentElement: { dataset: {}, style: { setProperty() {} } },
      getElementById: node,
    },
    requestAnimationFrame(callback) { callback(); },
    setInterval() { return 0; },
    setTimeout(callback) { callback(); return 0; },
    window: {
      addEventListener() {},
      pywebview: { api: { save_draft: saveDraft } },
    },
  };
  vm.createContext(context);
  const appPath = path.join(__dirname, "..", "src", "novel_agent_workbench", "modern_ui", "app.js");
  const source = `${fs.readFileSync(appPath, "utf8")}\n` +
    "globalThis.__autosaveTest = { state, saveDraft, flushSave };";
  vm.runInContext(source, context, { filename: appPath });
  return { hooks: context.__autosaveTest, node, window: context.window };
}


test("close flush waits for an in-flight save before persisting the latest text", async () => {
  const calls = [];
  let releaseFirstSave;
  const firstSave = new Promise((resolve) => { releaseFirstSave = resolve; });
  const { hooks, node } = loadApp(async (_projectId, _draftId, text) => {
    calls.push(text);
    if (calls.length === 1) await firstSave;
    return { ok: true, data: {} };
  });
  hooks.state.projectId = "story";
  hooks.state.draftId = "draft-1";
  node("editor").value = "older text";

  const inFlight = hooks.saveDraft();
  node("editor").value = "latest text";
  const closingFlush = hooks.flushSave();

  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(calls, ["older text"]);
  releaseFirstSave();
  await Promise.all([inFlight, closingFlush]);
  assert.deepEqual(calls, ["older text", "latest text"]);
});


test("close flush reports a failed final save and restores editing", async () => {
  const { hooks, node, window } = loadApp(async () => ({ ok: false, error: "disk full" }));
  hooks.state.projectId = "story";
  hooks.state.draftId = "draft-1";
  node("editor").value = "unsaved text";

  const result = await window.__workbenchFlushBeforeClose();

  assert.equal(result.ok, false);
  assert.equal(result.error, "disk full");
  assert.equal(node("editor").readOnly, false);
});


test("close flush refuses to exit while generation is active", async () => {
  const { hooks, node, window } = loadApp(async () => ({ ok: true, data: {} }));
  hooks.state.projectId = "story";
  hooks.state.draftId = "draft-1";
  hooks.state.generating = true;
  node("editor").readOnly = true;

  const result = await window.__workbenchFlushBeforeClose();

  assert.equal(result.ok, false);
  assert.equal(node("editor").readOnly, true);
});
