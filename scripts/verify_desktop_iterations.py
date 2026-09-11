"""One real WebView acceptance workflow; all files and providers are isolated."""
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "work" / "desktop-iteration-check"
RUN.mkdir(parents=True, exist_ok=True)
DATA = RUN / ("ui-" + uuid4().hex[:8])
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge, WindowCloseSaveCoordinator, modern_ui_dir
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.storage import ProjectStore

LIB_A, LIB_B = DATA / "library-a", DATA / "library-b"
api = WorkbenchBridge(projects_root=LIB_A, repo_root=ROOT, settings_path=DATA / "desktop_settings.local.json")
api.app.create_project("same_id", title="迭代验收作品")
store_a = ProjectStore.open(LIB_A, "same_id")
drafts_a = DraftGenerationService(store_a)
confirmed = drafts_a.save_provider_draft_version(chapter_id="chapter_1", content="第一章已确认。", title="第一章", provider_role="writer", provider="mock", model="mock")
api.app.accept_draft_manually("same_id", confirmed.draft_id)
api.app.commit_draft("same_id", confirmed.draft_id, replace_existing=True)
draft = drafts_a.save_provider_draft_version(chapter_id="chapter_2", content="A 库原稿。", title="第二章", provider_role="writer", provider="mock", model="mock")
api.app.create_planning_item("same_id", "outline", text="总纲原文。", title="验收总纲", active=True)
api.app.create_planning_item("same_id", "chapter_plan", text="章节计划原文。", title="验收章节计划", item_type="chapter_plan", active=True)
store_a.write_json(store_a.data_file_path("memory_bank.json"), {"items": [{"memory_id": "main_memory_bank", "text": "记忆原文。", "status": "ready", "source_chapter_ids": ["chapter_1"]}]})
store_a.create_checkpoint(label="pre_delete_chapter_2_drafts", include_secrets=False)
settings = api.app._read_global_settings()
settings["provider_profiles"]["ui_mock"] = {"profile_id": "ui_mock", "display_name": "本地验收模型", "adapter": "mock", "enabled": True}
settings["model_profiles"]["ui_mock::mock"] = {"model_ref": "ui_mock::mock", "provider_profile_id": "ui_mock", "model_id": "mock", "enabled": True}
settings["primary_model_ref"] = "ui_mock::mock"
api.app._write_global_settings(settings)
shutil.copytree(LIB_A, LIB_B)
app_b = WorkbenchApplicationService.open(LIB_B)
store_b = ProjectStore.open(LIB_B, "same_id")
drafts_b = DraftGenerationService(store_b)
drafts_b.update_draft_content(draft.draft_id, text="B 库同名稿件，不可被 A 覆盖。")

window = webview.create_window("小说创作工作台 [迭代验收]", url=str(modern_ui_dir() / "index.html"), js_api=api, width=1120, height=720, min_size=(1120, 720), text_select=True, confirm_close=False)
api.bind_window(window)
closer = WindowCloseSaveCoordinator(window)
api._close_coordinator = closer
window.events.closing += closer.on_closing
results = {"isolated_data": str(DATA)}
completed = threading.Event()

def evaluate(script):
    ready, box = threading.Event(), []
    window.evaluate_js("(async()=>{try{" + script + "}catch(e){return {__error:String(e),stack:e.stack}}})()", callback=lambda value: (box.append(value), ready.set()))
    if not ready.wait(25):
        raise RuntimeError("UI script timed out")
    if isinstance(box[0], dict) and "__error" in box[0]:
        raise RuntimeError(box[0])
    return box[0]

def phase(name):
    if "--pause-for-inspection" not in sys.argv:
        return
    gate = RUN / (name + ".continue")
    gate.unlink(missing_ok=True)
    (RUN / "phase.json").write_text(json.dumps({"phase": name, "pid": os.getpid()}), encoding="utf8")
    print("PHASE", name, "PID", os.getpid(), flush=True)
    deadline = time.monotonic() + 180
    while not gate.exists() and time.monotonic() < deadline:
        time.sleep(.2)
    if not gate.exists():
        raise RuntimeError("Screenshot phase timed out: " + name)

def run():
    try:
        for _ in range(120):
            if window.evaluate_js('typeof state !== "undefined" && state.ready'):
                break
            time.sleep(.1)
        evaluate('''window.__uiErrors=[];
          window.addEventListener("error",e=>__uiErrors.push(e.message));
          window.addEventListener("unhandledrejection",e=>__uiErrors.push(String(e.reason)));
          window.until=async(fn)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error("UI wait timed out: "+fn);await new Promise(r=>setTimeout(r,50));}};
          window.press=(root,text)=>{const b=Array.from($(root).querySelectorAll("button")).find(b=>b.textContent===text||(b.classList.contains("choice")&&b.textContent.endsWith(text)));if(!b)throw Error("Missing button: "+text);b.scrollIntoView({block:"center"});b.click();};
          window.edit=(control,text)=>{control.value=text;control.dispatchEvent(new Event("input",{bubbles:true}));};
          window.waitDialog=()=>until(()=>!$("modal").hidden&&$("modalTitle").textContent==="还有未保存的修改");
          await selectProject("same_id");return true;''')
        evaluate('''await openMemoryStudio();edit(studio.memoryEditor,"记忆待保存。");$("studioClose").click();await waitDialog();press("modalFoot","返回编辑");await until(()=>!studio.leaving);return true;''')
        assert window.evaluate_js('studio.memoryEditor.value') == "记忆待保存。"
        with patch.object(WorkbenchApplicationService, "set_memory_text", side_effect=OSError("验收模拟：磁盘暂不可写")):
            evaluate('''$("studioClose").click();await waitDialog();press("modalFoot","保存并继续");await until(()=>$("toast").textContent.includes("磁盘暂不可写")&&!studio.saving);return true;''')
            assert window.evaluate_js('!$("modal").hidden&&studio.mode==="memory"&&studio.memoryEditor.value==="记忆待保存。"')
        evaluate('''press("modalFoot","保存并继续");await until(()=>studio.mode===""&&!studio.leaving);return true;''')
        assert "记忆待保存。" in store_a.data_file_path("memory_bank.json").read_text(encoding="utf8")
        results["unsaved_memory"] = {"return_preserves_text": True, "save_failure_keeps_editor_and_dialog": True, "retry_saves": True}

        evaluate('''await openPlanningStudio("outline");press("studioBody","验收总纲");await until(()=>studio.planForm.title.value==="验收总纲");edit(studio.planForm.editor,"总纲不应丢失。");press("studioBody","验收章节计划");await waitDialog();press("modalFoot","返回编辑");await until(()=>!studio.leaving);return true;''')
        assert window.evaluate_js('studio.planForm.editor.value') == "总纲不应丢失。"
        results["planning_layout"] = evaluate('''await Promise.all($("studio").getAnimations().map(a=>a.finished));
          const editor=studio.planForm.editor.getBoundingClientRect();const save=Array.from($("studioBody").querySelectorAll("button")).find(b=>b.textContent==="保存当前").getBoundingClientRect();
          return {editor:editor.toJSON(),save:save.toJSON(),height:innerHeight,width:innerWidth,status:$("studioEditStatus").textContent,propertiesCollapsed:!$("studioBody").querySelector("details").open};''')
        layout = results["planning_layout"]
        assert layout["editor"]["height"] >= 160 and layout["editor"]["bottom"] <= layout["height"]
        assert layout["save"]["bottom"] <= layout["height"] and layout["propertiesCollapsed"] and layout["status"] == "有未保存修改"
        phase("planning")
        evaluate('''press("studioBody","验收章节计划");await waitDialog();press("modalFoot","放弃修改");await until(()=>studio.planForm.title.value==="验收章节计划"&&!studio.leaving);press("studioBody","验收总纲");await until(()=>studio.planForm.title.value==="验收总纲");return true;''')
        assert window.evaluate_js('studio.planForm.editor.value') == "总纲原文。"
        evaluate('''edit(studio.planForm.editor,"总纲已保存。");press("studioBody","验收章节计划");await waitDialog();press("modalFoot","保存并继续");await until(()=>studio.planForm.title.value==="验收章节计划"&&!studio.leaving);press("studioBody","验收总纲");await until(()=>studio.planForm.title.value==="验收总纲");return true;''')
        assert window.evaluate_js('studio.planForm.editor.value') == "总纲已保存。"
        results["planning_switch"] = {"return": True, "discard": True, "save_and_switch": True}

        evaluate('''await closeStudio();await openGenSettings("project");press("studioTabs","采样与上下文");edit(studio.genFields.max_context_tokens,"123456");$("studioClose").click();await waitDialog();press("modalFoot","保存并继续");await until(()=>studio.mode===""&&!studio.leaving);return true;''')
        assert api.app.generation_settings("same_id")["context"]["max_context_tokens"] == 123456
        evaluate('''await openModelStudio("provider");const name=$("studioBody").querySelector(".studio-form input");edit(name,"临时改名不保存");press("studioTabs","功能分配");await waitDialog();press("modalFoot","放弃修改");await until(()=>studio.tab==="assign"&&!studio.leaving);const toggle=$("studioBody").querySelector("input[role=switch]");toggle.click();$("studioClose").click();await waitDialog();press("modalFoot","保存并继续");await until(()=>studio.mode===""&&!studio.leaving);return true;''')
        assert "临时改名不保存" not in json.dumps(api.app._read_global_settings(), ensure_ascii=False)
        results["settings_guard"] = {"project_settings_saved": True, "provider_discarded": True, "assignments_saved": True}

        evaluate('''await openMemoryStudio();edit(studio.memoryEditor,"退出时待保存。");return true;''')
        assert closer.on_closing() is False
        evaluate('''await waitDialog();await new Promise(r=>setTimeout(r,9000));return true;''')
        assert closer._close_in_progress and closer._watchdog is None
        evaluate('''press("modalFoot","返回编辑");await until(()=>!studio.leaving);return true;''')
        for _ in range(30):
            if not closer._close_in_progress:
                break
            time.sleep(.1)
        assert not closer._close_in_progress
        assert window.evaluate_js('studio.memoryEditor.value') == "退出时待保存。"
        results["native_close_guard"] = {"decision_wait_over_8s": True, "return_keeps_window_and_text": True}
        evaluate('''$("studioClose").click();await waitDialog();press("modalFoot","放弃修改");await until(()=>studio.mode===""&&!studio.leaving);return true;''')

        evaluate('await loadDraft("same_id",' + json.dumps(draft.draft_id) + ');return true;')
        with patch.object(window, "create_file_dialog", return_value=[str(LIB_B)]):
            evaluate('''edit($("editor"),"A 库切换前最后输入。");$("dataRootBtn").click();await until(()=>state.projectsRoot.endsWith("library-b")&&!state.changingRoot);return true;''')
        assert drafts_a.read_draft(draft.draft_id)["content"] == "A 库切换前最后输入。"
        assert drafts_b.read_draft(draft.draft_id)["content"] == "B 库同名稿件，不可被 A 覆盖。"
        assert window.evaluate_js('!state.draftId && $("editor").value===""')
        assert json.loads(api.settings_path.read_text(encoding="utf8"))["projects_root"] == str(LIB_B.resolve())
        rejected = api.save_draft("same_id", draft.draft_id, "迟到请求不得写入 B。", str(LIB_A))
        assert not rejected["ok"]
        evaluate('await loadDraft("same_id",' + json.dumps(draft.draft_id) + ');return true;')
        with patch.object(window, "create_file_dialog", return_value=[str(LIB_A)]), patch("novel_agent_workbench.modern_desktop.atomic_write_json_file", side_effect=OSError("验收模拟：位置无法保存")):
            evaluate('''$("dataRootBtn").click();await until(()=>$("toast").textContent.includes("位置无法保存")&&!state.changingRoot);return true;''')
        assert api.projects_root == LIB_B.resolve()
        assert window.evaluate_js('$("editor").value') == "B 库同名稿件，不可被 A 覆盖。"
        results["library_switch"] = {"saves_original_library": True, "same_ids_do_not_overwrite": True, "old_editor_cleared": True, "late_save_rejected": True, "remembered_root": True, "failed_switch_preserves_current": True}

        evaluate('''$("historyBackupsBtn").click();await until(()=>studio.mode==="backups");const b=Array.from($("studioBody").querySelectorAll("button.choice")).find(b=>b.textContent.includes("删除章节"));if(!b)throw Error("Expected deletion checkpoint");b.click();await until(()=>!Array.from($("studioBody").querySelectorAll("button")).find(b=>b.textContent==="恢复为新作品副本").disabled);return true;''')
        results["backup_preview"] = window.evaluate_js('$("studioBody").querySelector("pre").textContent')
        results["backup_usage"] = window.evaluate_js('Array.from($("studioBody").querySelectorAll("p")).find(p=>p.textContent.includes("共占用")).textContent')
        opened, opened_path = threading.Event(), []
        with patch.object(os, "startfile", side_effect=lambda path: (opened_path.append(Path(path)), opened.set())):
            evaluate('press("studioBody","打开项目库整理备份");return true;')
            assert opened.wait(5), "Backup management button did not request the folder"
        assert opened_path == [LIB_B]
        results["backup_management_opens_current_library"] = True
        phase("history")
        restored_id = evaluate('''press("studioBody","恢复为新作品副本");await until(()=>!state.generating&&!studio.saving&&studio.mode===""&&state.projectId!=="same_id");return state.projectId;''')
        recovered = ProjectStore.open(LIB_B, restored_id)
        assert DraftGenerationService(recovered).read_draft(draft.draft_id)["content"] == "A 库原稿。"
        assert "记忆原文。" in recovered.data_file_path("memory_bank.json").read_text(encoding="utf8")
        assert drafts_b.read_draft(draft.draft_id)["content"] == "B 库同名稿件，不可被 A 覆盖。"
        results["backup_restore"] = {"new_project": restored_id, "backup_drafts_and_memory_restored": True, "source_unchanged": True}
        results["errors"] = window.evaluate_js("window.__uiErrors")
        assert results["errors"] == []
        evaluate('await loadDraft(' + json.dumps(restored_id) + ',' + json.dumps(draft.draft_id) + ''');edit($("editor"),"退出时的最后正文。");await openMemoryStudio();edit(studio.memoryEditor,"退出时的最后记忆。");return true;''')
        window.destroy()
        evaluate('''await waitDialog();press("modalFoot","保存并继续");return true;''')
        assert window.events.closed.wait(20), "Native close did not finish after saving"
        assert DraftGenerationService(recovered).read_draft(draft.draft_id)["content"] == "退出时的最后正文。"
        assert "退出时的最后记忆。" in recovered.data_file_path("memory_bank.json").read_text(encoding="utf8")
        results["native_save_and_exit"] = {"draft_saved": True, "memory_saved": True, "window_closed": True}
        results["passed"] = True
    except Exception:
        results["error"] = traceback.format_exc()
    finally:
        (RUN / "ui_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps(results, ensure_ascii=False), flush=True)
        if not window.events.closed.is_set():
            closer._allow_close = True
            window.destroy()
        completed.set()

webview.start(run, gui="edgechromium", debug=False, private_mode=True)
completed.wait(30)
raise SystemExit(0 if results.get("passed") else 1)
