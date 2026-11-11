"""One real WebView2 workflow; temporary data, dummy keys and loopback HTTP only."""
import base64
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir
from test_subscription_providers import local_provider


def main():
    evidence = Path(tempfile.mkdtemp(prefix="novel-subscription-ui-"))
    passed = []
    with tempfile.TemporaryDirectory(prefix="novel-subscription-data-") as directory, local_provider() as (base, _, requests):
        root = Path(directory)
        api = WorkbenchBridge(projects_root=root / "projects", repo_root=ROOT, settings_path=root / "prefs.json")
        api.app.create_project("test", title="订阅接入隔离验收")
        draft = DraftGenerationService(api.app._open_store("test")).save_provider_draft_version(
            chapter_id="chapter_1", title="测试章", content="测试章正文。", provider_role="writer", provider="mock", model="mock")
        api.app.accept_draft_manually("test", draft.draft_id)
        api.app.commit_draft("test", draft.draft_id)
        for profile_id in ("opencode_go", "commandcode_goat"):
            api.app.upsert_provider_profile(profile_id, display_name="OpenCode Go" if profile_id == "opencode_go" else "Command Code GOAT",
                adapter=profile_id, base_url=base + ("/go/openai/v1" if profile_id == "opencode_go" else "/cmd/v1"))
        window = webview.create_window("小说工作台 · 订阅接入验收", str(modern_ui_dir() / "index.html"),
                                       js_api=api, width=1280, height=900)
        api.bind_window(window)

        def ui(script):
            ready, values = threading.Event(), []
            window.evaluate_js("(async()=>{try{" + script + "}catch(e){return {error:String(e),stack:e.stack}}})()",
                               callback=lambda value: (values.append(value), ready.set()))
            assert ready.wait(20), "UI timeout"
            assert not isinstance(values[0], dict) or "error" not in values[0], values
            return values[0]

        def screenshot(name):
            from webview.platforms.winforms import BrowserView
            from System import Action
            form = BrowserView.instances[window.uid]
            tasks = []
            form.Invoke(Action(lambda: tasks.append(form.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
                "Page.captureScreenshot", "{}"))))
            deadline = time.monotonic() + 10
            while not tasks[0].IsCompleted and time.monotonic() < deadline:
                time.sleep(.02)
            assert tasks[0].IsCompleted, "Screenshot timeout"
            (evidence / name).write_bytes(base64.b64decode(json.loads(str(tasks[0].Result))["data"]))

        def run():
            try:
                assert window.events.loaded.wait(20)
                ui("""window.qaErrors=[];window.addEventListener('error',e=>qaErrors.push(e.message));
                  window.addEventListener('unhandledrejection',e=>qaErrors.push(String(e.reason)));
                  window.until=async pred=>{const end=Date.now()+10000;while(!pred()){
                    if(Date.now()>end)throw Error('condition timeout');await new Promise(r=>setTimeout(r,40));}};
                  window.press=(id,text)=>{const b=[...$(id).querySelectorAll('button')]
                    .find(b=>b.textContent===text||b.querySelector('.tree-title')?.textContent===text);
                    if(!b)throw Error('missing '+text);b.click();};
                  await until(()=>state.ready);await selectProject('test');return true;""")
                for profile_id, label, model in (("opencode_go", "OpenCode Go", "go-free"),
                                                  ("commandcode_goat", "Command Code GOAT", "vendor/goat-model")):
                    ui("await closeStudio({discard:true});await openModelStudio('provider');press('studioBody'," + json.dumps(label)
                       + ");await until(()=>studio.selectedProvider===" + json.dumps(profile_id) + ");return true;")
                    count = len(requests)
                    ui("""const key=$('studioBody').querySelector('input[type=password]');
                      key.value='dummy-test-key';key.dispatchEvent(new Event('input',{bubbles:true}));
                      press('studioBody','保存当前设置');await until(()=>!studio.saving&&providerById(studio.selectedProvider).has_api_key);
                      return true;""")
                    assert len(requests) == count, "Saving settings unexpectedly accessed the network"
                    ui("""press('studioBody','刷新模型');await until(()=>!state.generating&&!studio.saving&&
                      studio.model.models.some(m=>m.provider_profile_id===studio.selectedProvider));return true;""")
                    assert ui("return $('studioBody').textContent.includes('Chat Completions')&&$('studioBody').querySelector('input[type=password]').value==='';")
                    screenshot(profile_id + "-provider.png")
                    ui("press('studioTabs','模型目录');await until(()=>studio.tab==='models'&&$('studioBody').querySelector('table'));return true;")
                    assert ui("return !$('studioBody').textContent.includes('messages-only')&&!$('studioBody').textContent.includes('premium');")
                    ui("""press('studioTabs','功能分配');await until(()=>studio.tab==='assign'&&$('studioBody').querySelector('.search-select input'));
                      const input=$('studioBody').querySelector('.search-select input');input.focus();
                      const option=[...$('studioBody').querySelectorAll('.search-select-item')].find(b=>b.textContent.includes("""
                       + json.dumps("[" + model + "]") + """));if(!option)throw Error('missing assignment model');
                      option.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));press('studioBody','保存功能分配');
                      await until(()=>!studio.saving&&studio.model.primary_model_ref===""" + json.dumps(profile_id + "::" + model) + ");return true;")
                    ui("""await closeStudio({discard:true});await openMemoryStudio();press('studioBody','按勾选章节生成');
                      await until(()=>!studio.memoryBusy&&studio.memoryEditor.value==='本地测试正文。');return true;""")
                    screenshot(profile_id + "-memory.png")
                    assert requests[-1]["body"]["model"] == model
                    print("PASS: " + label + " save key, refresh catalog, assign model and stream memory", flush=True)
                assert not ui("return qaErrors;"), "JavaScript runtime errors"
                passed.append(True)
            except Exception:
                traceback.print_exc()
            finally:
                window.destroy()
        webview.start(run, gui="edgechromium", debug=False, private_mode=True)
    print("Evidence: " + str(evidence), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
