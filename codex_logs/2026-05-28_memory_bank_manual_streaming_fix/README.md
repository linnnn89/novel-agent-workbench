# Memory Bank Manual Streaming Fix

Date: 2026-05-28, Asia/Shanghai.

## Operation

Fixed the desktop Memory Bank manual API generation path after EXE testing showed that clicking manual Memory Bank generation did not show live text streaming or a progress bar.

## Root Cause

The automatic 5-chapter Memory Bank summary path already opened a streaming progress window and passed `stream_callback` into `generate_memory_bank_text(...)`.

The manual `资料库 > 记忆库` generation path only disabled buttons and waited for the Provider response. It did not open a progress window and did not pass a streaming callback, so users saw no live text and no progress bar.

## Files Changed

- `src/novel_agent_workbench/desktop_app.py`
- `tests/test_memory_bank_api_generation.py`
- `codex_logs/README.md`
- `codex_logs/2026-05-28_memory_bank_manual_streaming_fix/README.md`

## Safety Boundaries

- The manual path still requires the existing confirmation before calling the writer Provider.
- The generated Memory Bank text is still only filled into the editor; persistence still requires clicking `保存记忆正文`.
- No Provider call is made by automated tests.

## Verification

```powershell
py -3.13 -m unittest discover -s tests
py -3.13 -m compileall src tests
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File I:\AI-NOVEL\novel_agent_workbench\scripts\build_windows_exe.ps1 -SkipInstall
```

## Next Step

Retest the rebuilt EXE by opening `资料库 > 记忆库`, selecting confirmed chapters, and clicking manual Memory Bank generation. The generation window should show an indeterminate progress bar and live streamed text, then fill the final text back into the Memory Bank editor.
