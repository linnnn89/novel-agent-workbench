# Chapter Regeneration Prompt

Date: 2026-05-28, Asia/Shanghai.

## Operation

Changed desktop `要求重写（重新随机）` behavior from old-draft-based rewriting to source-free chapter regeneration.

## Root Cause

The previous desktop path built a prompt containing `【上一版稿件】` and the current draft body. This made the model revise or imitate the existing chapter instead of treating the target chapter as unwritten.

## Files Changed

- `src/novel_agent_workbench/desktop_app.py`
- `scripts/build_windows_exe.ps1`
- `tests/test_draft_regeneration_prompt.py`
- `tests/README.md`
- `codex_logs/README.md`
- `codex_logs/2026-05-28_chapter_regeneration_prompt/README.md`

## Safety Boundaries

- The old draft is still preserved as its own draft artifact.
- Regeneration creates another draft version for the same chapter.
- The Provider prompt no longer includes the previous draft body for this UI action.
- Old-draft-based fixes remain available through `根据审稿精修`.
- Windows EXE rebuilds now stage PyInstaller output and replace only the executable/runtime files, preserving `dist\NovelAgentWorkbench\用户数据`.

## Verification

```powershell
py -3.13 -m unittest tests.test_draft_regeneration_prompt
py -3.13 -m unittest discover -s tests
py -3.13 -m compileall src tests
git diff --check
```
