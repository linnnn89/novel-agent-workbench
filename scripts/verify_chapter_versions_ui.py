"""One isolated real WebView2 workflow for version deletion and chapter defaults."""
import json
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir


def main():
    with tempfile.TemporaryDirectory(prefix="novel-versions-ui-") as directory:
        root = Path(directory)
        api = WorkbenchBridge(projects_root=root / "projects", repo_root=ROOT,
                              settings_path=root / "settings.json")
        api.app.create_project("test", title="单版本删除与章节编号验收")
        drafts = DraftGenerationService(api.app._open_store("test"))
        versions = [drafts.save_provider_draft_version(
            chapter_id="chapter_006", title="chapter_006", content=f"第{n}版正文。",
            provider_role="writer", provider="mock", model="mock") for n in (1, 2, 3)]
        api.chapter_input("test", "chapter_006", "旧标题", "确认前的旧要求", str(api.projects_root))
        window = webview.create_window("小说工作台 · 章节版本隔离验收", str(modern_ui_dir() / "index.html"),
                                       js_api=api, width=1120, height=760)
        api.bind_window(window)
        passed = []

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
                  window.rightVersion=label=>{const b=[...document.querySelectorAll('.tree-draft')]
                    .find(b=>b.textContent.trim()===label);if(!b)throw Error('missing '+label);
                    const box=b.getBoundingClientRect();b.dispatchEvent(new MouseEvent('contextmenu',
                      {bubbles:true,clientX:box.x+40,clientY:box.y+10}));};
                  await until(()=>state.ready);await selectProject('test');return true;""")
                ui("await loadDraft('test'," + json.dumps(versions[0].draft_id) + ");$('confirmBtn').click();"
                   "await until(()=>!$('modal').hidden);press('modalFoot','确认这一版');"
                   "await until(()=>$('modal').hidden);return true;")
                assert len(api.app.list_confirmed_chapters("test")) == 1
                ui("$('newChapterBtn').click();await until(()=>!$('modal').hidden);return true;")
                values = ui("return [...$('modalBody').querySelectorAll('input,textarea')].map(e=>e.value);")
                assert values[0] == "chapter_007" and values[1] == "" and values[2] != "确认前的旧要求", values
                ui("press('modalFoot','取消');return true;")
                last = drafts.save_provider_draft_version(
                    chapter_id="chapter_007", title="chapter_007", content="下一章草稿。",
                    provider_role="writer", provider="mock", model="mock")
                ui("await refreshWorkspace();return true;")
                print("PASS: confirming a cached chapter opens the next available ID, with no old title/prompt", flush=True)
                ui("await loadDraft('test'," + json.dumps(versions[2].draft_id) + ");rightVersion('ver2');return true;")
                labels = ui("return [...$('ctxMenu').querySelectorAll('button')].map(b=>b.textContent);")
                assert "删除此版本" in labels, labels
                if "--inspect" in sys.argv:
                    print("MENU_READY: visual inspection of real version menu", flush=True)
                    time.sleep(20)
                ui("press('ctxMenu','删除此版本');await until(()=>!$('modal').hidden);return true;")
                # Explicit cancellation must leave the selected version untouched.
                ui("press('modalFoot','取消');rightVersion('ver2');press('ctxMenu','删除此版本');"
                   "await until(()=>!$('modal').hidden);return true;")
                if "--inspect" in sys.argv:
                    print("DIALOG_READY: visual inspection of deletion dialog", flush=True)
                    time.sleep(20)
                ui("press('modalFoot','删除版本');await until(()=>$('modal').hidden&&"
                   "document.querySelectorAll('.tree-draft').length===2);return true;")
                assert ui("return state.draftId;") == versions[2].draft_id
                assert ui("return $('editor').value;") == "第3版正文。"
                assert ui("return state.draftIds;") == [versions[0].draft_id, versions[2].draft_id]
                ui("rightVersion('ver3');press('ctxMenu','删除此版本');await until(()=>!$('modal').hidden);"
                   "press('modalFoot','删除版本');await until(()=>state.draftIds.length===1&&state.draftId==="
                   + json.dumps(versions[0].draft_id) + ");return true;")
                assert ui("return $('editor').value;") == "第1版正文。"
                # Backend protection is surfaced to the user; no dialog silently removes a confirmed source.
                ui("rightVersion('ver1');press('ctxMenu','删除此版本');await until(()=>!$('modal').hidden);"
                   "press('modalFoot','删除版本');await until(()=>$('toast').textContent.includes('当前确认稿'));"
                   "press('modalFoot','取消');return true;")
                assert len(api.app.list_drafts("test")) == 2
                ui("await loadDraft('test'," + json.dumps(last.draft_id) + ");rightVersion('ver1');"
                   "press('ctxMenu','删除此版本');await until(()=>!$('modal').hidden);press('modalFoot','删除版本');"
                   "await until(()=>$('modal').hidden&&!state.draftId);return true;")
                empty = ui("return {text:$('editor').value,ids:state.draftIds,label:$('versionLabel').textContent};")
                assert empty == {"text": "", "ids": [], "label": "—"}, empty
                print("PASS: right-click deletion, cancel, sibling selection, current fallback, confirmed protection, last-version clearing", flush=True)
                assert not ui("return qaErrors;"), "JavaScript runtime errors"
                passed.append(True)
            except Exception:
                traceback.print_exc()
            finally:
                window.destroy()

        webview.start(run, gui="edgechromium", debug=False, private_mode=True)
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
