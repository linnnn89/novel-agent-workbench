# MVP-12 Mock Context Draft

Date: 2026-05-18, Asia/Shanghai.

## Goal

Create the first context-aware draft generation path while keeping it local and mock-only.

## Files Changed

```text
src/novel_agent_workbench/drafts.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
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

`DraftGenerationService.generate_context_draft(...)`:

1. Requires writer provider to be `mock`.
2. Builds a prompt render dry-run with local explicit text inclusion.
3. Renders an in-memory prompt from enabled manual Memory Bank context plus operator prompt.
4. Sends that prompt only to the local mock writer.
5. Writes a normal draft artifact plus safe `context_generation` metadata.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> generate-context-draft <project_id> --chapter-id chapter_002 --prompt "Draft the next scene." --max-context-tokens 4096
```

## Safety Boundary

- Mock writer only.
- No real Provider calls.
- No auto-commit.
- No prompt logs.
- No operator prompt text in metadata outputs.
- No Memory Bank text in metadata outputs.
- No Memory Bank/world book/RAG/export/DOCX side effects.
- Draft content may contain mock generated text only.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_context_assembler
```

Result:

```text
Ran 30 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 190 tests
OK
```

Secret scan for the previously supplied Chutes key fragments:

```text
No matches.
```

## Known Limits

- Real Provider context-aware generation is not enabled.
- Final prompt rendering is not persisted.
- Context package uses manual Memory Bank text only; no world book/RAG integration yet.

## Next Step

MVP-12.5 should add audit checks for context-generation draft metadata consistency and prompt/context leakage before any real Provider uses assembled context.
