# Desktop Memory Bank UI

Date: 2026-05-24, Asia/Shanghai.

## Operation

Turned the desktop `Memory Bank` menu entry into a project-level memory editor.

The window now supports:

- showing the current project Memory Bank body as one editable text area;
- saving the edited AI/manual summary through `set_memory_text`;
- recording the checked confirmed chapters as Memory Bank source metadata, including `last_updated_chapter_id`;
- enabling/disabling whether the project Memory Bank enters generation context through `set_memory_item_enabled`;
- showing and saving a visible Memory Bank target token value; the default is 5000 tokens and it is used only inside the LLM update prompt as a compression target, not as an API output cap or text truncation limit;
- estimating the current Memory Bank body token count in the editor, comparing it with the target token value, and recommending compression when the estimate is over target;
- exposing a separate Memory Bank compression prompt preview button; that prompt tells the LLM the current estimated tokens and target tokens, then asks it to rewrite the Memory Bank toward the target without hard deletion of recent critical facts;
- listing confirmed chapters with checkbox-style selection for batch Memory Bank updates;
- prominently showing which chapter the Memory Bank has already covered and recommending the next chapter range to select;
- previewing the prompt that should be sent to an LLM to incrementally update the Memory Bank from all checked confirmed chapters;
- previewing the current assembled context package without calling a Provider.
- opening the right-click `查看生成时会带的上下文` as a read-only context package preview instead of creating formal memory-summary tasks.
- hiding legacy empty Memory Bank placeholders from the user-facing context preview and translating skipped-item reasons into readable Chinese labels.

The UI no longer exposes world-building, character relationships, chapter summary, style memory, or foreshadowing as separate user-filled chapter entries. Those aspects now appear only inside the LLM update prompt. The prompt asks the other AI to preserve still-valid old Memory Bank content, merge new confirmed chapters, keep the updated Memory Bank around the visible target token value where possible, and only compress older low-impact memory when the whole memory is becoming too long.

## Files Changed

- `src/novel_agent_workbench/desktop_app.py`
- `src/novel_agent_workbench/memory_bank.py`
- `src/novel_agent_workbench/application_service.py`
- `tests/test_desktop_app.py`
- `tests/test_context_assembler.py`
- `codex_logs/README.md`
- `codex_logs/2026-05-24_desktop_memory_bank_ui/README.md`

## Safety Boundaries

- During this Codex implementation/QA pass, no real LLM/API calls were made.
- Product boundary: the software may later add explicit user-triggered actions such as `发送给 AI 更新记忆`; those actions can call the configured provider after user intent/configuration is clear. This log's "no real call" statement is not a ban on product model calls.
- No automatic chapter text extraction into Memory Bank.
- Drafts still do not update Memory Bank.
- Right-click context preview is read-only and does not enqueue context or Memory Bank tasks.
- In the current Memory Bank window, checked confirmed chapters are used only to build a prompt preview and save local source-progress metadata. A future explicit send button can call a real model if the user triggers it.
- The Memory Bank target token value is a prompt instruction for the model to compress toward; the software does not use it to hard-cut model output or reject longer saved Memory Bank text.
- The token estimate is approximate and UI-only. It is used to guide prompt wording, not to block saving or API output.
- The context preview no longer prints raw internal skip codes such as `manual_text_missing` or long placeholder IDs for empty legacy Memory Bank items.
- RAG and export are not updated.

## Verification

```powershell
py -3.13 -m unittest tests.test_desktop_app
py -3.13 -m unittest discover -s tests
$env:PYTHONPATH='src'; py -3.13 -m novel_agent_workbench.cli prepublish-check
```

Results:

- `tests.test_desktop_app`: 13 tests OK.
- Full test suite: 174 tests OK.
- `prepublish-check`: 0 blockers, 0 warnings.

## Next Step

Build the Windows EXE and manually test `资料库 > 记忆库` plus right-click `记忆库` on project/chapter/draft nodes.
