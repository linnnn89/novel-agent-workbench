const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/novel_agent_workbench/modern_ui/app.js"), "utf8");
function extract(name) {
  const start = source.indexOf(`async function ${name}(`);
  const end = source.indexOf("\nasync function ", start + 10);
  return source.slice(start, end < 0 ? undefined : end);
}
async function refinement(saved, current) {
  let dialog, calls = [], begun = false;
  const context = {
    requireDraft: () => true,
    state: { hasReview: true, projectId: "p", draftId: "d", chapterId: "c" },
    saveDraft: async () => ({ ok: saved }),
    call: async (name, ...args) => { calls.push([name, ...args]); return { has_review: current }; },
    promptText: (options) => { dialog = options; },
    beginStream: () => { begun = true; context.state.draftId = ""; },
    toast() {}, setInspectorTab() {}, setBusy() {}, ThinkTrace: { finish() {} },
  };
  vm.createContext(context);
  vm.runInContext(extract("refineDraft"), context);
  await context.refineDraft();
  if (dialog) await dialog.onSubmit("instruction");
  return { dialog, calls, begun };
}
(async () => {
  let result = await refinement(false, true);
  assert.equal(result.dialog, undefined);
  assert.equal(result.calls.length, 0);
  assert.equal(result.begun, false);
  result = await refinement(true, false);
  assert.equal(result.dialog, undefined);
  assert.equal(result.calls.length, 1);
  assert.equal(result.begun, false);
  result = await refinement(true, true);
  assert.equal(result.begun, true);
  assert.deepEqual(result.calls[1], ["refine_draft", "p", "d", "instruction"]);

  let message = "";
  const context = {
    state: { streamProjectId: "p", projectId: "p" },
    setBusy() {}, ThinkTrace: { finish() {} },
    refreshWorkspace: async () => {}, loadDraft: async () => {}, toast: (text) => { message = text; },
  };
  vm.createContext(context);
  vm.runInContext(extract("finishDraft"), context);
  await context.finishDraft({ ok: true, data: { draft_id: "new", output_incomplete: true } });
  assert.match(message, /不完整候选/);
  await context.finishDraft({ ok: true, data: { draft_id: "new", output_incomplete: false } });
  assert.doesNotMatch(message, /不完整候选/);
  console.log("PASS: save failure, stale review, valid dispatch, truncated and complete completion notices");
})().catch((error) => { console.error(error); process.exitCode = 1; });
