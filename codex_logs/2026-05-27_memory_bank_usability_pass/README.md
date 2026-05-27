# Memory Bank Usability Pass

Date: 2026-05-27, Asia/Shanghai.

## Operation

Improved the desktop Memory Bank window for practical use:

- added vertical scrolling to the confirmed-chapter checklist;
- added vertical scrolling and undo support to the Memory Bank body editor;
- made the update prompt preview use the same backend provider request preview as the actual API generation path;
- added a manual-copy prompt view that includes both System and User messages;
- added unsaved-change marking in the window title and confirmation before refresh/close;
- added `Ctrl+S` as a save shortcut.
- added automatic 5-confirmed-chapter Memory Bank summary triggering after draft confirmation;
- added a progress popup while automatic Memory Bank summary generation runs in the background;
- added an auto-summary result review window with an explicit save button that records the summarized chapter range.
- adjusted Memory Bank generation defaults to `top_p=1.0`, `stream=true`, and fixed `max_tokens=8000`.
- revised the Memory Bank generation System message from a compression-oriented role to a long-term continuity maintenance role.
- revised the Memory Bank generation User message into explicit update principles, priority memory categories, compression principles, and output requirements.
- connected Memory Bank generation streaming callbacks to the automatic 5-chapter summary popup, so returned text appears live and the same window becomes the review/save surface.

## Files Changed

- `src/novel_agent_workbench/desktop_app.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/memory_bank.py`
- `src/novel_agent_workbench/__init__.py`
- `tests/test_memory_bank_api_generation.py`
- `codex_logs/2026-05-27_memory_bank_usability_pass/README.md`
- `codex_logs/README.md`

## Safety Boundaries

- No real Provider/API calls were made.
- No project data files or Memory Bank JSON files were modified.
- The generation and save gates remain explicit: API generation still fills the editor only, and persistence still requires saving.
- The underlying Memory Bank storage schema was not changed.
- Runtime auto-summary calls the configured writer Provider only after a successful desktop draft confirmation and only when 5 confirmed chapters have accumulated beyond the Memory Bank progress marker.

## Verification

```powershell
py -3.14 -m unittest discover -s tests
py -3.14 -m compileall src tests
git diff --check
```

Results:

- Unit tests: 3 tests OK.
- Compile: OK.
- Diff whitespace check: OK, with Git line-ending warnings only.

Note: `py -3.13` is not installed on this machine; Python 3.14 was used because the project requires `>=3.13`.

## Next Step

Manually open the desktop app and exercise `资料库 > 记忆库` with a real project containing many confirmed chapters and a long Memory Bank body.
