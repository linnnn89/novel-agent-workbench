# World Materials Editor Delete

Date: 2026-05-28, Asia/Shanghai.

## Operation

Fixed the desktop `世界观与人物` Planning Library page so character/world/constraint records can be selected one by one, edited, and deleted.

## Root Cause

The page rendered a read-only text summary and only exposed creation actions. Multiple character records could be added, but there was no per-record selection path for editing or deletion. The project tree right-click menu also only exposed `记忆库` and `大纲与章节`, not `世界观与人物`.

## Files Changed

- `src/novel_agent_workbench/desktop_app.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/planning_library.py`
- `tests/test_planning_library_records.py`
- `tests/README.md`
- `codex_logs/README.md`
- `codex_logs/2026-05-28_world_materials_editor_delete/README.md`

## Safety Boundaries

- Editing and deletion remain manual UI actions.
- Deleting a Planning Library item creates a checkpoint first.
- No Provider call is made by these UI actions or tests.
- Existing Planning Library JSON schema is preserved.

## Verification

```powershell
py -3.13 -m unittest discover -s tests
py -3.13 -m compileall src tests
git diff --check
```
