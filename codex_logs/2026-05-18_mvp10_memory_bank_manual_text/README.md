# MVP-10 Memory Bank Manual Text

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add the first safe Memory Bank text write path after the placeholder commit gate.

This phase allows only explicit human-supplied Memory Bank text. It does not auto-extract chapter text, call Providers, update world book, update RAG/export, mutate drafts/confirmed chapters, or assemble Provider prompts.

## Files Changed

```text
src/novel_agent_workbench/memory_bank.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
tests/test_context_assembler.py
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

`MemoryBankService` exposes:

```text
list_memory_items(include_text=False)
read_memory_item(memory_id, include_text=False)
set_memory_text(memory_id, text)
```

Default list/read surfaces are metadata-only. Manual text is returned only through an explicit `include_text=True` read.

`set_memory_text` creates a `pre_memory_text_update` checkpoint, validates nonempty text, enforces a 1200 character limit, rejects obvious secret-like values, and writes:

```text
status=ready
text_status=manual
safety.manual_text=true
safety.provider_called=false
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-memory-items <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> set-memory-text <project_id> <memory_id> --text "Manual continuity note."
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-memory-item <project_id> <memory_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-memory-item <project_id> <memory_id> --include-text
```

## Safety Boundary

- No Provider calls.
- No automatic extraction from confirmed chapters.
- No prompt text in Memory Bank operations.
- No plaintext secrets in outputs.
- No default exposure of manual Memory Bank text.
- No world book, RAG, export, draft, or confirmed chapter mutation.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_context_assembler
```

Result before final full regression:

```text
Ran 17 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 177 tests
OK
```

Secret scan for the previously supplied Chutes key fragments:

```text
No matches.
```

## Known Limits

- Manual text is stored in `data/memory_bank.json`, so future prompt assembly must still decide when and how to include it.
- There is no world book implementation yet.
- There is no automatic extraction or LLM-assisted Memory Bank editing yet.
- The local Context Assembler still has only dry-run behavior and does not render a final Provider prompt.

## Next Step

MVP-10.5 should add Memory Bank item lifecycle controls such as disable/enable, archive-by-`.trash` policy discussion if needed, and metadata-only review status before any automatic extraction or real prompt assembly.
