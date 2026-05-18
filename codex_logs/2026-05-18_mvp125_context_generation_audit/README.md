# MVP-12.5 Context Generation Audit

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add read-only audit checks for context-aware draft metadata before real Providers are allowed to use assembled context.

## Files Changed

```text
src/novel_agent_workbench/audit.py
tests/test_audit.py
README.md
src/README.md
tests/README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_logs/README.md
I:/AI-NOVEL/PROJECT_INDEX.md
```

## Design

Audit checks context-aware draft metadata only:

```text
drafts_index.json context_aware entries
draft artifact context_generation metadata
```

It deliberately does not treat normal draft `content` as an audit failure, because draft artifacts are the human-review surface for generated text.

## New Finding Codes

```text
invalid_context_generation_draft_index_entry
unsafe_context_generation_draft_path
missing_context_generation_draft_artifact
context_generation_metadata_missing
context_generation_mode_invalid
context_generation_text_flag_invalid
context_generation_section_count_mismatch
possible_secret_in_context_generation
possible_prompt_in_context_generation
context_generation_forbidden_metadata_key
```

## Safety Boundary

- Audit remains read-only.
- No Provider calls.
- No prompt reconstruction.
- No artifact writes.
- No draft content rejection unless leak-prone metadata is polluted.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_audit
```

Result:

```text
Ran 18 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 193 tests
OK
```

Secret scan for the previously supplied Chutes key fragments:

```text
No matches.
```

## Pause Point

Paused after this stable audit hardening slice. Recommended resume point:

```text
MVP-13 decision: real-provider context-aware gate vs one more mock-only review cycle.
```

## Next Step

MVP-13 can start designing a real-provider context-aware gate, but only after deciding whether real context-aware generation should reuse Chutes first or stay mock-only through one more review cycle.
