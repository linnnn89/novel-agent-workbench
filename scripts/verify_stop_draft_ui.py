"""One isolated WebView2 stop/save workflow; no external API or user data."""
import json
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir
from novel_agent_workbench.providers import ProviderResponse
from novel_agent_workbench.task_control import current_job


def main():
    with tempfile.TemporaryDirectory(prefix="novel-stop-ui-") as directory:
        root = Path(directory)
        api = WorkbenchBridge(projects_root=root / "projects", repo_root=ROOT,
                              settings_path=root / "settings.json")
        api.app.create_project("test", title="中止草稿隔离验收")
        store = api.app._open_store("test")
        drafts = DraftGenerationService(store)
        old = drafts.save_provider_draft_version(chapter_id="chapter_001", title="本章",
            content="原来的正文。", provider_role="writer", provider="mock", model="mock")
        window = webview.create_window("小说工作台 · 中止草稿验收", str(modern_ui_dir() / "index.html"),
                                       js_api=api, width=1120, height=760)
        api.bind_window(window)
        passed = []
        entered = threading.Event()
        expected = "已经接收的草稿正文。收到哪里就保存到哪里。"
        prompt = "停止后仍需恢复的发送要求"

        def provider(store, request):
            request.stream_callback(expected)
            entered.set()
            control = current_job()
            assert control.event.wait(55), "Stop was not selected"
            control.check()

        def ui(script):
            ready, result = threading.Event(), []
            window.evaluate_js("(async()=>{try{" + script + "}catch(e){return {error:String(e),stack:e.stack}}})()",
                               callback=lambda value: (result.append(value), ready.set()))
            assert ready.wait(20), "UI call timed out"
            assert not isinstance(result[0], dict) or "error" not in result[0], result
            return result[0]

        def run():
            try:
                assert window.events.loaded.wait(20)
                ui("""window.qaErrors=[];window.addEventListener('error',e=>qaErrors.push(e.message));
                  window.addEventListener('unhandledrejection',e=>qaErrors.push(String(e.reason)));
                  window.until=async pred=>{const end=Date.now()+10000;while(!pred()){
                    if(Date.now()>end)throw Error('condition timeout');await new Promise(r=>setTimeout(r,40));}};
                  window.press=(id,text)=>{const b=[...$(id).querySelectorAll('button')].find(b=>b.textContent===text);
                    if(!b)throw Error('missing '+text);b.click();};
                  await until(()=>state.ready);await selectProject('test');return true;""")
                with patch.object(WorkbenchApplicationService, "_runtime_store", return_value=store), \
                     patch("novel_agent_workbench.drafts.generate_with_provider", side_effect=provider):
                    for keep in (False, True):
                        entered.clear()
                        ui("await loadDraft('test'," + json.dumps(old.draft_id) + ");await generateChapter();" + """
                          const inputs=$('modalBody').querySelectorAll('input,textarea');
                          inputs[0].value='chapter_001';inputs[1].value='本章';
                          inputs[2].value=""" + json.dumps(prompt) + ";press('modalFoot','生成草稿');return true;")
                        assert entered.wait(10)
                        ui("""await until(()=>state.activeJobId);$('cancelJobBtn').click();
                          await until(()=>!$('modal').hidden);return true;""")
                        labels = ui("return [...$('modalFoot').querySelectorAll('button')].map(b=>b.textContent);")
                        assert labels == ["返回", "否，丢弃并停止", "是，保存并停止"], labels
                        if not keep:
                            print("MODAL_READY: isolated stop dialog available for visual inspection", flush=True)
                            if "--inspect" in sys.argv: time.sleep(30)
                            ui("""press('modalFoot','返回');if(!state.generating)throw Error('Return stopped task');
                              $('cancelJobBtn').click();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
                              if(!$('modal').hidden||!state.generating)throw Error('Esc stopped task');
                              $('cancelJobBtn').click();return true;""")
                        label = "是，保存并停止" if keep else "否，丢弃并停止"
                        ui("press('modalFoot'," + json.dumps(label) + ");await until(()=>!state.generating);return true;")
                        assert len(api.app.list_drafts("test")) == (2 if keep else 1)
                        view = ui("return {id:state.draftId,text:$('editor').value,readonly:$('editor').readOnly,modal:$('modal').hidden};")
                        assert not view["readonly"] and view["modal"], view
                        if keep:
                            assert view["id"] != old.draft_id and view["text"] == expected, view
                            assert api.app.read_draft("test", view["id"])["output_incomplete"]
                        else:
                            assert view["id"] == old.draft_id and view["text"] == "原来的正文。", view
                        ui("closeDrawer();await generateChapter();return true;")
                        restored = ui("return [...$('modalBody').querySelectorAll('input,textarea')].map(e=>e.value);")
                        assert restored == ["chapter_001", "本章", prompt], restored
                        ui("closeModal();return true;")
                        print("PASS: " + ("save" if keep else "discard") + "; API job stopped, correct draft opened, input restored", flush=True)
                    # Rewriting uses the same stop dialog and saves a new version of the source chapter.
                    entered.clear()
                    ui("$('rewriteBtn').click();await until(()=>!$('modal').hidden);press('modalFoot','继续');return true;")
                    assert entered.wait(10)
                    ui("""await until(()=>state.activeJobId);$('cancelJobBtn').click();press('modalFoot','是，保存并停止');
                      await until(()=>!state.generating);return true;""")
                    assert len(api.app.list_drafts("test")) == 3
                    assert ui("return $('editor').value;") == expected
                    print("PASS: rewrite stop saves another draft version", flush=True)
                    with patch("novel_agent_workbench.reviews.generate_with_provider", return_value=ProviderResponse(
                            "请补充人物动机。", {}, "mock", "mock", "stop")):
                        ui("$('reviewBtn').click();await until(()=>!state.generating&&state.hasReview);return true;")
                    entered.clear()
                    with patch("novel_agent_workbench.application_service.generate_with_provider", side_effect=provider):
                        ui("$('refineBtn').click();await until(()=>!$('modal').hidden);press('modalFoot','继续');return true;")
                        assert entered.wait(10)
                        ui("""await until(()=>state.activeJobId);$('cancelJobBtn').click();press('modalFoot','是，保存并停止');
                          await until(()=>!state.generating);return true;""")
                    assert len(api.app.list_drafts("test")) == 4
                    refined = api.app.read_draft("test", ui("return state.draftId;"))
                    assert refined["content"] == expected and refined["generation_cancelled"]
                    assert ui("return $('draftHint').textContent;").endswith("手动停止后保存，请核对并补全")
                    print("PASS: AI refinement stop saves a draft with explicit cancelled status", flush=True)
                assert not ui("return qaErrors;"), "JavaScript runtime errors"
                passed.append(True)
            except Exception:
                traceback.print_exc()
            finally:
                if api._job_control: api._job_control.cancel()
                window.destroy()

        webview.start(run, gui="edgechromium", debug=False, private_mode=True)
        return 0 if passed else 1


if __name__ == "__main__": raise SystemExit(main())
