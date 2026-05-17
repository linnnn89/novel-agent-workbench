# MVP-1 Draft Generation Service Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Implement the backend-only Draft Generation Service skeleton.

## Scope

Allowed:

```text
Mock writer provider call
draft artifact JSON
draft index JSON
unit tests for no confirmed-state side effects
documentation updates
```

Not allowed:

```text
real LLM provider calls
frontend
confirmed chapter commit
Memory Bank update
RAG update
export update
DOCX export
reference project edits
```

## Design

Added `drafts.py` with:

- `DraftGenerationRequest`
- `DraftGenerationResult`
- `DraftGenerationService`
- `DraftGenerationError`

Draft output is stored under:

```text
data/drafts/*.json
data/drafts_index.json
```

The service uses the existing `ProviderRequest` and `generate_with_provider(...)` path. Current generation is writer-role only and relies on the deterministic local `mock` provider.

Draft artifacts include generated output and request summaries:

```text
prompt_chars
system_prompt_chars
metadata_keys
```

They do not store prompt text, system prompt text, metadata values, or plaintext secrets.

## Safety Boundary

This slice intentionally does not create or modify:

```text
data/chapters.json
data/confirmed_chapters.json
chapters/
rag/
data/rag.json
exports/
data/memory_bank.json
data/export_settings.json
```

Provider call logs may be written by the Provider layer, but those logs also exclude prompt text and plaintext secrets.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 46 tests
OK
```

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_draft_generation_service\README.md
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\drafts.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_draft_generation.py
```

## Next Step

Add a Draft Review / Draft Commit boundary. The next slice should define how a draft can be promoted to confirmed chapter, with tests proving that only explicit commit updates formal context.
