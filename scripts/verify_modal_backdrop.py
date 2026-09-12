"""Real WebView regression for accidental dialog dismissal; isolated data only."""
from pathlib import Path
import sys
import tempfile
import traceback
import time


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    import webview
    from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir

    with tempfile.TemporaryDirectory(prefix="novel-modal-check-") as directory:
        data = Path(directory)
        api = WorkbenchBridge(projects_root=data / "projects", repo_root=root,
                              settings_path=data / "desktop_settings.local.json")
        api.app.create_project("cache_test", title="章节缓存验收")
        window = webview.create_window("弹窗外部点击验证", url=str(modern_ui_dir() / "index.html"),
                                       js_api=api, width=1120, height=720)
        api.bind_window(window)
        passed = []

        def run():
            try:
                assert window.events.loaded.wait(20), "Application did not load"
                result = window.evaluate_js("""(() => {
                  promptText({title:'填写要求',desc:'外部点击不得丢失输入',onSubmit:()=>{}});
                  const input = $('modalBody').querySelector('textarea');
                  input.value = '尚未提交的写作要求';
                  const backdrop = document.elementFromPoint(5,5);
                  if(backdrop !== $('modal')) throw Error('Probe did not hit the backdrop');
                  backdrop.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:5,clientY:5}));
                  if($('modal').hidden || input.value !== '尚未提交的写作要求' || !input.isConnected)
                    throw Error('Outside click dismissed dialog or lost input');
                  const cancel = Array.from($('modalFoot').querySelectorAll('button')).find(b=>b.textContent==='取消');
                  cancel.click();
                  if(!$('modal').hidden) throw Error('Explicit cancel no longer closes dialog');
                  return 'PASS: outside click preserves dialog and text; Cancel closes it';
                })()""")
                assert isinstance(result, str) and result.startswith("PASS:"), result
                print(result, flush=True)
                window.evaluate_js("""(async () => {
                  while (!state.ready) await new Promise(r=>setTimeout(r,50));
                  await generateChapter();
                  const controls = $('modalBody').querySelectorAll('input,textarea');
                  controls[1].value = '缓存标题';
                  controls[2].value = '取消后恢复的本次要求';
                  controls[1].dispatchEvent(new Event('input',{bubbles:true}));
                  controls[2].dispatchEvent(new Event('input',{bubbles:true}));
                  closeModal();
                  await generateChapter();
                  const restored = $('modalBody').querySelectorAll('input,textarea');
                  if(restored[1].value !== '缓存标题' || restored[2].value !== '取消后恢复的本次要求')
                    throw Error('New-chapter inputs were not restored');
                  closeModal();
                  window.cacheCheck = 'PASS';
                })().catch(e=>{window.cacheCheck='FAIL: '+e.message;});""")
                deadline = time.monotonic() + 25
                outcome = None
                while time.monotonic() < deadline:
                    outcome = window.evaluate_js("window.cacheCheck || null")
                    if outcome:
                        break
                    time.sleep(.1)
                assert outcome == "PASS", outcome
                print("PASS: actual new-chapter dialog restores title and prompt after Cancel", flush=True)
                passed.append(True)
            except Exception:
                traceback.print_exc()
            finally:
                window.destroy()

        webview.start(run, gui="edgechromium", debug=False, private_mode=True)
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
