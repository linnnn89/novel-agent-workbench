"""Three isolated WebView2 feedback regressions; no model calls or personal data.

Run with an optional case name: memory, thinking, or review. Evidence goes to TEMP.
"""
from pathlib import Path
import base64
import json
import sys
import tempfile
import threading
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.storage import ProjectStore
from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir
from novel_agent_workbench.providers import ProviderResponse
from novel_agent_workbench.task_control import current_job


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "all"
    if case not in {"all", "memory", "thinking", "review"}:
        raise SystemExit("Expected memory, thinking, review, or all")
    evidence = Path(tempfile.mkdtemp(prefix="novel-feedback-qa-"))
    entered, release = threading.Event(), threading.Event()
    observations = {}
    succeeded = []

    with tempfile.TemporaryDirectory(prefix="novel-feedback-data-") as temp:
        root = Path(temp)
        api = WorkbenchBridge(projects_root=root / "projects", repo_root=ROOT, settings_path=root / "prefs.json")
        api.app.create_project("test", title="反馈回归 · 隔离项目")
        store = ProjectStore.open(api.projects_root, "test")
        drafts = DraftGenerationService(store)
        draft_ids = []
        for number in (1, 2):
            draft = drafts.save_provider_draft_version(
                chapter_id=f"chapter_{number}", title=f"测试第 {number} 章", content=f"第 {number} 章的测试正文。",
                provider_role="writer", provider="mock", model="mock")
            draft_ids.append(draft.draft_id)
            api.app.accept_draft_manually("test", draft.draft_id, reason_code="ui_test")
            api.app.commit_draft("test", draft.draft_id)
        window = webview.create_window("小说工作台 · 反馈回归", str(modern_ui_dir() / "index.html"),
                                       js_api=api, width=1120, height=760)
        api.bind_window(window)

        def ui(script):
            ready, result = threading.Event(), []
            window.evaluate_js("(async()=>{try{" + script + "}catch(e){return {error:String(e),stack:e.stack}}})()",
                               callback=lambda value: (result.append(value), ready.set()))
            assert ready.wait(20), "UI timeout"
            assert not isinstance(result[0], dict) or "error" not in result[0], result
            return result[0]

        def screenshot(name):
            from webview.platforms.winforms import BrowserView
            from System import Action
            form = BrowserView.instances[window.uid]
            tasks = []
            form.Invoke(Action(lambda: tasks.append(form.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
                "Page.captureScreenshot", "{}"))))
            deadline = time.monotonic() + 10
            while not tasks[0].IsCompleted and time.monotonic() < deadline:
                time.sleep(.05)
            assert tasks[0].IsCompleted, "Screenshot timeout"
            (evidence / name).write_bytes(base64.b64decode(json.loads(str(tasks[0].Result))["data"]))

        def memory():
            sent = []

            def reply(app, project_id, **kwargs):
                sent.extend(chapter["chapter_id"] for chapter in kwargs["chapters"])
                entered.set()
                assert release.wait(15), "Memory response not released"
                kwargs["stream_callback"]("只总结第 1 章的测试记忆。")
                return {"text": "只总结第 1 章的测试记忆。"}

            with patch.object(WorkbenchApplicationService, "generate_memory_bank_text", reply):
                ui("""await openMemoryStudio();press('studioBody','清空');
                  $('studioBody').querySelector('.studio-scroll input').click();
                  press('studioBody','按勾选章节生成');return true;""")
                assert entered.wait(10), "Memory request did not start"
                try:
                    during = ui("""press('studioBody','全选');return {readonly:studio.memoryEditor.readOnly,
                      selected:[...studio.checked],stopAvailable:!$('cancelStudioJobBtn').disabled&&!$('cancelStudioJobBtn').hidden,
                      traceToggleEnabled:!$('thinkBarToggle').disabled};""")
                    assert during["readonly"] and during["selected"] == ["chapter_1"], during
                    assert during["stopAvailable"] and during["traceToggleEnabled"], during
                    memory_path = store.data_file_path("memory_bank.json")
                    before = memory_path.read_bytes()
                    rejected = api.save_memory_workspace({"project_id": "test", "text": "运行中不应保存的内容", "chapter_ids": ["chapter_2"]})
                    assert rejected["ok"] is False and memory_path.read_bytes() == before, rejected
                finally:
                    release.set()
                ui("await until(()=>!studio.memoryBusy);press('studioBody','全选');await saveMemoryStudio();return true;")
                saved = api.app.ensure_main_memory_item("test")
                assert sent == ["chapter_1"] and saved["source_chapter_ids"] == ["chapter_1"], saved
                assert saved["text"] == "只总结第 1 章的测试记忆。"
                # Compressing the current memory must not add newly selected chapters.
                with patch.object(WorkbenchApplicationService, "generate_memory_bank_compression_text",
                                  return_value={"text": "第 1 章的缩写记忆。"}):
                    ui("""press('studioBody','全选');press('studioBody','压缩当前记忆');
                      await until(()=>!studio.memoryBusy&&studio.memoryEditor.value==='第 1 章的缩写记忆。');
                      await saveMemoryStudio();return true;""")
                assert api.app.ensure_main_memory_item("test")["source_chapter_ids"] == ["chapter_1"]
                with patch.object(WorkbenchApplicationService, "generate_memory_bank_compression_text",
                                  side_effect=OSError("模拟压缩失败")):
                    ui("""press('studioBody','压缩当前记忆');await until(()=>!studio.memoryBusy&&$('studioStatus').textContent.includes('失败'));
                      return true;""")
                assert ui("return !studio.memoryEditor.readOnly&&studio.memoryEditor.value==='第 1 章的缩写记忆。';")
                observations["memory"] = {"during": during, "sent": sent, "saved_sources": saved["source_chapter_ids"]}
                screenshot("memory.png")

        def thinking():
            ui(r"""await openMemoryStudio();ThinkTrace.start();
              ThinkTrace.handle('think_chunk',{text:Array.from({length:90},(_,i)=>'第 '+(i+1)+' 行测试思考文本').join('\n')});
              $('thinkBarBody').scrollTop=0;return true;""")
            first_meta = ui("return $('thinkBarMeta').textContent;")
            time.sleep(2.2)
            at_tick = ui("return {top:$('thinkBarBody').scrollTop,meta:$('thinkBarMeta').textContent};")
            assert at_tick["top"] == 0 and at_tick["meta"] != first_meta, at_tick
            assert ui(r"""ThinkTrace.handle('think_chunk',{text:'\n下一段'});return $('thinkBarBody').scrollTop===0;""")
            assert ui(r"""$('thinkBarToggle').click();ThinkTrace.handle('think_chunk',{text:'\n折叠期间继续返回'});
              ThinkTrace.handle('think_status',{phase:'writing'});return $('thinkBarBody').hidden;""")
            ui("$('thinkBarToggle').click();return true;")
            assert ui("return !$('thinkBarBody').hidden&&$('thinkBarBody').textContent.includes('折叠期间继续返回');")
            # After scrolling back down, new text should follow the bottom again.
            ui("$('thinkBarBody').scrollTop=$('thinkBarBody').scrollHeight;return true;")
            time.sleep(.1)
            assert ui(r"""ThinkTrace.handle('think_chunk',{text:'\n最新一段'});const b=$('thinkBarBody');
              return b.scrollHeight-b.clientHeight-b.scrollTop<2&&$('thinkBarTitle').textContent==='正在输出正文';""")
            screenshot("thinking.png")
            ui("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return true;")
            assert ui("""ThinkTrace.handle('think_chunk',{text:'关闭后仍在后台接收'});ThinkTrace.finish(true);
              return $('thinkBar').hidden;""")
            observations["thinking"] = {"timer_updates_without_scrolling": at_tick, "collapse_and_close_respected": True}

        def review():
            ui('await closeStudio({discard:true});await loadDraft("test",' + json.dumps(draft_ids[0]) + ');return true;')
            with patch.object(WorkbenchApplicationService, "_runtime_store", return_value=store):
                with patch("novel_agent_workbench.reviews.generate_with_provider", side_effect=OSError("模拟连接中断")):
                    ui("""$('reviewBtn').click();await until(()=>!state.generating&&$('toast').textContent.includes('模拟连接中断'));
                      return true;""")
                time.sleep(3.3)
                failed = ui("return {pane:$('pane-review').textContent,toastHidden:$('toast').hidden};")
                assert "审稿失败" in failed["pane"] and "正在阅读" not in failed["pane"] and failed["toastHidden"], failed
                screenshot("review-failed.png")

                cancelled_entered = threading.Event()

                def interrupted_provider(store, request):
                    time.sleep(.1)
                    request.stream_callback("停止前已返回的审稿片段。")
                    cancelled_entered.set()
                    control = current_job()
                    assert control.event.wait(10), "Stop was not received"
                    control.check()

                with patch("novel_agent_workbench.reviews.generate_with_provider", side_effect=interrupted_provider):
                    ui("$('reviewBtn').click();return true;")
                    assert cancelled_entered.wait(10), "Review did not start"
                    ui("$('cancelJobBtn').click();await until(()=>!state.generating);return true;")
                stopped = ui("return $('pane-review').textContent;")
                assert "审稿已停止" in stopped and "停止前已返回" in stopped and "正在阅读" not in stopped, stopped

                with patch("novel_agent_workbench.reviews.generate_with_provider",
                           return_value=ProviderResponse("人物动机需要补充，这是截断的审稿意见。", {}, "mock", "mock", "length")):
                    ui("""$('reviewBtn').click();await until(()=>!state.generating&&state.reviewText.includes('人物动机'));
                      return true;""")
                truncated = ui("return {pane:$('pane-review').textContent,refineDisabled:$('refineBtn').disabled};")
                assert "人物动机" in truncated["pane"] and "截断" in truncated["pane"] and truncated["refineDisabled"], truncated
                ui('await loadDraft("test",' + json.dumps(draft_ids[1]) + ');await loadDraft("test",' + json.dumps(draft_ids[0]) + ');return true;')
                assert ui("return $('pane-review').textContent.includes('人物动机')&&$('pane-review').textContent.includes('截断')&&$('refineBtn').disabled;")
                screenshot("review-truncated.png")
                with patch("novel_agent_workbench.reviews.generate_with_provider",
                           return_value=ProviderResponse("这是完整的审稿意见。", {}, "mock", "mock", "stop")):
                    ui("""$('reviewBtn').click();await until(()=>!state.generating&&state.reviewText.includes('完整的审稿'));
                      return true;""")
                assert ui("return !$('refineBtn').disabled&&!$('pane-review').textContent.includes('截断');")
                observations["review"] = {"failure": failed, "stopped": stopped, "truncated": truncated,
                                          "truncated_survives_reopen": True, "complete_review_enables_refine": True}

        def run():
            try:
                assert window.events.loaded.wait(20)
                ui("""window.qaErrors=[];window.addEventListener('error',e=>qaErrors.push(e.message));
                  window.addEventListener('unhandledrejection',e=>qaErrors.push(String(e.reason)));
                  window.until=async pred=>{const stop=Date.now()+10000;while(!pred()){if(Date.now()>stop)throw Error('condition timeout');await new Promise(r=>setTimeout(r,40));}};
                  window.press=(id,text)=>{const b=[...$(id).querySelectorAll('button')].find(b=>b.textContent===text);if(!b)throw Error('missing button '+text);b.click();};
                  await until(()=>state.ready);await selectProject('test');return true;""")
                for name, check in [("memory", memory), ("thinking", thinking), ("review", review)]:
                    if case in {"all", name}:
                        check()
                        print("PASS: " + name, flush=True)
                assert not ui("return qaErrors;"), "JavaScript runtime errors"
                succeeded.append(True)
            except Exception:
                traceback.print_exc()
            finally:
                release.set()
                (evidence / "results.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
                window.destroy()

        webview.start(run, gui="edgechromium", debug=False, private_mode=True)
    print("Evidence: " + str(evidence), flush=True)
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
