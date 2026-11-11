"""One isolated WebView2 theme regression; no model calls or personal data."""
import base64
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import webview
from novel_agent_workbench.modern_desktop import WorkbenchBridge, modern_ui_dir


def contrast(foreground, background):
    def luminance(value):
        channels = [int(n) / 255 for n in re.findall(r"\d+", value)[:3]]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + .05) / (low + .05)


def main():
    evidence = Path(tempfile.mkdtemp(prefix="novel-theme-qa-"))
    observations, passed = {}, []
    with tempfile.TemporaryDirectory(prefix="novel-theme-data-") as directory:
        root = Path(directory)
        api = WorkbenchBridge(projects_root=root / "projects", repo_root=ROOT, settings_path=root / "prefs.json")
        api.app.create_project("test", title="主题与概览验收")
        window = webview.create_window("小说工作台 · 主题回归", str(modern_ui_dir() / "index.html"),
                                       js_api=api, width=1280, height=900)
        api.bind_window(window)

        def ui(script):
            ready, values = threading.Event(), []
            window.evaluate_js("(async()=>{try{" + script + "}catch(e){return {error:String(e),stack:e.stack}}})()",
                               callback=lambda value: (values.append(value), ready.set()))
            assert ready.wait(20), "UI timeout"
            assert not isinstance(values[0], dict) or "error" not in values[0], values
            return values[0]

        def devtools(method, parameters):
            from webview.platforms.winforms import BrowserView
            from System import Action
            form = BrowserView.instances[window.uid]
            tasks = []
            form.Invoke(Action(lambda: tasks.append(form.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(
                method, json.dumps(parameters)))))
            deadline = time.monotonic() + 10
            while not tasks[0].IsCompleted and time.monotonic() < deadline:
                time.sleep(.02)
            assert tasks[0].IsCompleted, method + " timeout"
            return json.loads(str(tasks[0].Result))

        def snapshot(name):
            (evidence / name).write_bytes(base64.b64decode(devtools("Page.captureScreenshot", {})["data"]))

        def run():
            try:
                assert window.events.loaded.wait(20)
                ui("""window.qaErrors=[];window.addEventListener('error',e=>qaErrors.push(e.message));
                  window.addEventListener('unhandledrejection',e=>qaErrors.push(String(e.reason)));
                  window.until=async pred=>{const end=Date.now()+10000;while(!pred()){
                    if(Date.now()>end)throw Error('condition timeout');await new Promise(r=>setTimeout(r,40));}};
                  await until(()=>state.ready);await selectProject('test');return true;""")
                expected = {
                    "light": ["rgb(63, 77, 102)", "rgb(63, 77, 102)", "rgb(63, 107, 79)", "rgb(180, 35, 24)"],
                    "dark": ["rgb(197, 205, 216)", "rgb(197, 205, 216)", "rgb(134, 179, 150)", "rgb(249, 112, 102)"],
                }
                for theme in expected:
                    ui("""openSettings();const theme=$('modalBody').querySelector('select');
                      theme.value=""" + json.dumps(theme) + """;theme.dispatchEvent(new Event('change',{bubbles:true}));
                      $('modalFoot').querySelector('button').click();await until(()=>$('modal').hidden);
                      $('trashBtn').click();await until(()=>!$('modal').hidden);
                      const b=document.createElement('div');b.id='qaButtons';b.style.cssText='display:flex;gap:8px;margin-top:12px';
                      for(const kind of ['primary','accent','success','danger']){const button=document.createElement('button');
                        button.className='btn '+kind;button.textContent=kind;b.append(button);}$('modalBody').append(b);
                      await new Promise(r=>setTimeout(r,200));return true;""")
                    colors = ui("""return [...$('qaButtons').children].map(b=>{const s=getComputedStyle(b);
                      return {kind:b.textContent,background:s.backgroundColor,color:s.color};});""")
                    for entry in colors:
                        # Translucent backgrounds require compositing; reject them below by exact color.
                        entry["contrast"] = (round(contrast(entry["color"], entry["background"]), 2)
                                             if entry["background"].startswith("rgb(") else None)
                    observations[theme] = colors
                    assert ui("return $('modalFoot').querySelector('.btn.danger')?.textContent==='清空';")
                    snapshot(theme + "-dialog.png")
                    ui("closeModal();return true;")
                    box = ui("const r=$('trashBtn').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};")
                    devtools("Input.dispatchMouseEvent", {"type": "mouseMoved", **box})
                    time.sleep(.2)
                    observations[theme + "_trash_hover"] = ui("const s=getComputedStyle($('trashBtn'));return {background:s.backgroundColor,color:s.color};")
                    snapshot(theme + "-overview.png")
                for theme, backgrounds in expected.items():
                    assert [entry["background"] for entry in observations[theme]] == backgrounds, observations
                    assert all(entry["contrast"] >= 4.5 for entry in observations[theme]), observations
                    assert observations[theme + "_trash_hover"]["color"] == backgrounds[-1], observations
                assert ui("""return document.querySelector('[data-tab="chapter"]').textContent==='概览'
                  && ['summaryText','contextText','healthBtn','recordsBtn','openFolderBtn','exportBtn','packageBtn','aboutBtn']
                    .every(id=>document.querySelectorAll('#'+id).length===1&&$(id).getBoundingClientRect().height>0);""")
                devtools("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
                reduced = ui("""ThinkTrace.start();openSettings();return {
                  sheet:getComputedStyle(document.querySelector('.sheet')).animationName,
                  dot:getComputedStyle(document.querySelector('.think-dot')).animationName,
                  pulse:getComputedStyle(document.querySelector('.pulse')).animationName};""")
                assert reduced == {"sheet": "none", "dot": "pulse-opacity", "pulse": "pulse-opacity"}, reduced
                observations["reduced_motion"] = reduced
                ui("closeModal();ThinkTrace.finish(true);return true;")
                assert not ui("return qaErrors;"), "JavaScript runtime errors"
                passed.append(True)
                print("PASS: light/dark backgrounds, text contrast, deletion dialog, trash hover, overview and reduced motion", flush=True)
            except Exception:
                traceback.print_exc()
            finally:
                (evidence / "results.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
                window.destroy()
        webview.start(run, gui="edgechromium", debug=False, private_mode=True)
    print("Evidence: " + str(evidence), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
