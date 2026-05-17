# MVP-1 Draft Commit Boundary Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Implement Draft Review / Explicit Commit / Confirmed Chapter boundary and a minimal safe project state summary.

## Scope

Allowed:

```text
draft status checks
explicit draft commit
confirmed chapter artifact and index
metadata-only commit log
safe project state summary
unit tests
documentation updates
```

Not allowed:

```text
real LLM provider calls
frontend
automatic Memory Bank updates
automatic RAG updates
automatic export updates
DOCX export
complex scoring/revision
reference project edits
```

## Storage Structure

Drafts:

```text
data/drafts/*.json
data/drafts_index.json
```

Confirmed chapters:

```text
data/confirmed_chapters/<chapter_id>.json
data/confirmed_chapters.json
```

Commit metadata log:

```text
data/commit_log.json
```

Project state summary:

```text
public_project_state(store)
```

## Safety Boundary

`generate_draft(...)` writes draft artifacts only. It does not create confirmed chapters.

`commit_draft(...)` is the only operation in this slice that writes confirmed chapter files. It creates a `pre_commit` checkpoint before writing confirmed artifacts.

This slice intentionally does not update:

```text
data/memory_bank.json
rag/
data/rag.json
exports/
data/export_settings.json
```

`data/commit_log.json` records metadata only:

```text
commit_id
timestamp
draft_id
chapter_id
status
provider
model
usage
checkpoint_id
```

It does not record prompt text, system prompt text, generated chapter content, or plaintext secrets.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 55 tests
OK
```

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_draft_commit_boundary\README.md
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\drafts.py
src\novel_agent_workbench\project_state.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_draft_generation.py
```

## Known Not Implemented

- No UI.
- No real LLM provider.
- No scoring or revision pipeline.
- No DOCX export.
- No automatic Memory Bank, RAG, or export update after commit.
- No crash-atomic multi-file transaction beyond per-file atomic writes and pre-commit checkpoint.

## Next Step

Build a minimal backend command/API facade around the current services so the future UI can call project creation, draft generation, draft list/read, explicit commit, and safe state summary through one stable application service layer.
