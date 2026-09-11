"""Three real Windows UI regressions; deterministic local delays, no model calls.

Run with --red before a fix to retain the failing baseline separately.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "work" / "studio-safety-check"
DATA = RUN / uuid4().hex[:8]
DATA.mkdir(parents=True)
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir
from novel_agent_workbench.storage import ProjectStore

api = WorkbenchBridge(projects_root=DATA / "projects", repo_root=ROOT)
api.app.create_project("test", title="异步保护测试")
store = ProjectStore.open(api.projects_root, "test")
store.write_json(store.data_file_path("memory_bank.json"), {"items": [
    {"memory_id": "main_memory_bank", "text": "磁盘记忆原文。", "status": "ready"}
]})
settings = api.app._read_global_settings()
settings["provider_profiles"]["ui_mock"] = {"profile_id": "ui_mock", "display_name": "本地测试接入商", "adapter": "mock", "enabled": True}
api.app._write_global_settings(settings)
window = webview.create_window("小说工作台 [TDD 保护复核]", url=str(modern_ui_dir() / "index.html"), js_api=api, width=1120, height=720)
api.bind_window(window)
observations = {}
finished = threading.Event()
successful = False


def ui(script):
    ready, values = threading.Event(), []
    window.evaluate_js("(async()=>{try{" + script + "}catch(e){return {error:String(e),stack:e.stack}}})()", callback=lambda value: (values.append(value), ready.set()))
    if not ready.wait(20):
        raise AssertionError("UI did not respond")
    if isinstance(values[0], dict) and "error" in values[0]:
        raise AssertionError(values[0])
    return values[0]


@contextmanager
def delayed(owner, method, *, replacement=None, failure=False):
    entered, release = threading.Event(), threading.Event()
    original = getattr(owner, method)

    def controlled(*args, **kwargs):
        entered.set()
        if not release.wait(12):
            raise AssertionError("Test did not release the operation")
        if failure:
            raise OSError("TDD 模拟读写失败")
        return (replacement or original)(*args, **kwargs)

    with patch.object(owner, method, controlled):
        try:
            yield entered, release
        finally:
            release.set()


class StudioSafetyTests(unittest.TestCase):
    def setUp(self):
        ui('await closeStudio({discard:true});return true;')

    def test_settings_save_cannot_mark_later_tab_edits_as_saved(self):
        ui('''await openGenSettings("project");press("studioTabs","采样与上下文");edit(studio.genFields.max_context_tokens,"120001");return true;''')
        with delayed(WorkbenchApplicationService, "update_generation_settings") as (entered, release):
            ui('press("studioBody","保存项目设置");return true;')
            self.assertTrue(entered.wait(8))
            during = ui('''press("studioTabs","提示词");
              const typed=studio.genFields.system ? edit(studio.genFields.system,"保存开始后输入的新提示词") : false;
              return {tab:studio.genTab,typed};''')
            release.set()
            ui('await until(()=>!studio.saving&&$("studioStatus").textContent==="创作设置已保存。");return true;')
        after = ui('return {dirty:studioHasChanges(),status:$("studioEditStatus").textContent};')
        disk = api.app.generation_settings("test")
        observations["settings_save"] = {"during": during, "after": after, "disk_budget": disk["context"]["max_context_tokens"], "late_prompt_saved": disk["prompting"]["system_prompt"] == "保存开始后输入的新提示词"}
        self.assertEqual(disk["context"]["max_context_tokens"], 120001)
        self.assertEqual(during["tab"], "sample", "Saving must keep the current tab until the write finishes")
        self.assertFalse(during["typed"], "A later edit must not be mistaken for the completed write")
        ui('''press("studioTabs","提示词");edit(studio.genFields.system,"保存失败后仍要保留的文字");return true;''')
        with delayed(WorkbenchApplicationService, "update_generation_settings", failure=True) as (entered, release):
            ui('press("studioBody","保存项目设置");return true;')
            self.assertTrue(entered.wait(8))
            release.set()
            ui('await until(()=>!studio.saving&&$("toast").textContent.includes("TDD 模拟读写失败"));return true;')
        self.assertTrue(ui('return studioHasChanges()&&!studio.genFields.system.disabled&&studio.genFields.system.value==="保存失败后仍要保留的文字";'))

    def test_model_refresh_protects_form_and_unlocks_on_success_or_failure(self):
        ui('''await openModelStudio("provider");press("studioBody","本地测试接入商");await until(()=>studio.selectedProvider==="ui_mock");return true;''')
        phases = []
        for failure in (False, True):
            with delayed(WorkbenchApplicationService, "refresh_provider_models", replacement=lambda *_: {"model_count": 1}, failure=failure) as (entered, release):
                ui('$("studioStatus").textContent="";press("studioBody","刷新模型");return true;')
                self.assertTrue(entered.wait(8))
                during = ui('''const name=$("studioBody").querySelector(".studio-form input");
                  return {blocked:!edit(name,"刷新时输入的新名字"),closeDisabled:$("studioClose").disabled};''')
                release.set()
                ui('await until(()=>!state.generating&&!studio.saving&&Boolean($("studioStatus").textContent));return true;')
            after = ui('''const name=$("studioBody").querySelector(".studio-form input");return {name:name.value,enabled:!name.disabled&&!$("studioClose").disabled,status:$("studioStatus").textContent};''')
            phases.append({"failure": failure, "during": during, "after": after})
        observations["model_refresh"] = phases
        for phase in phases:
            self.assertTrue(phase["during"]["blocked"], "Catalog completion must not erase a name typed during refresh")
            self.assertTrue(phase["after"]["enabled"], "The form must be usable again after success or failure")

    def test_memory_reload_cannot_overwrite_new_typing(self):
        ui('await openMemoryStudio();return true;')
        with delayed(WorkbenchBridge, "memory_state") as (entered, release):
            ui('press("studioBody","从磁盘重新加载");return true;')
            self.assertTrue(entered.wait(8))
            blocked = ui('return !edit(studio.memoryEditor,"读取期间刚输入的记忆");')
            release.set()
            ui('await until(()=>!studio.saving&&$("toast").textContent==="已从磁盘重新加载已保存记忆。");return true;')
        after = ui('return {text:studio.memoryEditor.value,enabled:!studio.memoryEditor.disabled&&!$("studioClose").disabled};')
        observations["memory_reload"] = {"typing_blocked": blocked, "after": after}
        self.assertTrue(blocked, "Reading saved memory must not discard typing that happened while waiting")
        self.assertEqual(after["text"], "磁盘记忆原文。")
        self.assertTrue(after["enabled"])


def run():
    global successful
    try:
        for _ in range(150):
            if window.evaluate_js('typeof state!=="undefined"&&state.ready'):
                break
            time.sleep(.1)
        ui('''window.__errors=[];window.addEventListener("unhandledrejection",e=>__errors.push(String(e.reason)));window.addEventListener("error",e=>__errors.push(e.message));
          window.until=async(fn)=>{const end=Date.now()+10000;while(!fn()){if(Date.now()>end)throw Error("Timeout: "+fn);await new Promise(r=>setTimeout(r,25));}};
          window.press=(root,text)=>{const b=Array.from($(root).querySelectorAll("button")).find(b=>b.textContent===text||b.querySelector(".tree-title")?.textContent===text);if(!b)throw Error("Missing button: "+text);b.click();};
          window.edit=(node,text)=>{if(node.disabled||node.readOnly)return false;node.value=text;node.dispatchEvent(new Event("input",{bubbles:true}));return true;};
          await selectProject("test");return true;''')
        suite = unittest.TestSuite(StudioSafetyTests(name) for name in (
            "test_settings_save_cannot_mark_later_tab_edits_as_saved",
            "test_model_refresh_protects_form_and_unlocks_on_success_or_failure",
            "test_memory_reload_cannot_overwrite_new_typing",
        ))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        errors = window.evaluate_js("window.__errors")
        successful = result.wasSuccessful() and not errors
        report = {"passed": successful, "tests": result.testsRun, "failures": len(result.failures), "errors": errors, "observations": observations, "isolated_data": str(DATA)}
        report_path = RUN / ("red.json" if "--red" in sys.argv else "green.json")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
        print("REPORT", report_path, flush=True)
    finally:
        window.destroy()
        finished.set()


webview.start(run, gui="edgechromium", debug=False, private_mode=True)
finished.wait(30)
raise SystemExit(0 if successful else 1)
