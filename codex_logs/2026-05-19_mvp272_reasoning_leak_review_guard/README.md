# 2026-05-19 MVP-27.2 Reasoning Leak Review Guard

Scope:

- Added a `review-draft` guard for `<think` / `</think>` reasoning markup.
- Matching drafts skip scorer Provider calls.
- Matching drafts get a metadata-only `local_guard` review with issue code `reasoning_leak_detected`.
- Matching drafts are automatically marked `needs_revision` with reason code `reasoning_leak`.
- Chapter workflow moves to `needs_revision`.

Boundaries:

- No real Provider call.
- No draft overwrite.
- No automatic revision draft generation.
- No auto-commit.
- No UI.
- No DOCX/export.
- No Memory Bank/RAG/export updates.
- No deletion of real files.

Verification:

```powershell
py -3.13 -m unittest tests.test_reviews
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 18 tests in tests.test_reviews: OK
Ran 296 tests: OK
```
