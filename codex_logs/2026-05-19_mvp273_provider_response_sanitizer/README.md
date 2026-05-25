# 2026-05-19 MVP-27.3 Provider Response Sanitizer

Scope:

- Added Provider response sanitization before draft content is saved.
- Removes `<think>...</think>` reasoning blocks.
- Removes standalone `<think>` tags.
- Records only `request_summary.response_sanitizer` metadata.
- Keeps future UI/read/commit flows on clean draft content.

Boundaries:

- Does not overwrite existing drafts.
- Does not store removed reasoning text.
- Does not call extra Providers.
- Does not auto-create revision drafts.
- Does not auto-commit.
- Does not update Memory Bank/RAG/export.
- Does not create DOCX or UI.
- Does not delete real files.

Verification:

```powershell
py -3.13 -m unittest tests.test_draft_generation
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 17 tests in tests.test_draft_generation: OK
Ran 297 tests: OK
```
