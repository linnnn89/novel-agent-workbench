# MVP-11 Context Package Preview

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add a read-only local context package preview from enabled manual Memory Bank text.

This phase verifies local priority, lifecycle, and token-budget behavior before final Provider prompt rendering exists.

## Files Changed

```text
src/novel_agent_workbench/context_assembler.py
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

`ContextAssemblerService.package_preview(...)` returns:

```text
project_id
mode
token_budget
provider_api_boundary
include_text
sections
skipped
warnings
```

Default output is metadata-only:

```text
include_text=false
```

Manual Memory Bank text appears only when explicitly requested:

```text
include_text=true
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> context-package-preview <project_id> --max-context-tokens 4096
py -3.13 -m novel_agent_workbench.cli --projects-root <root> context-package-preview <project_id> --max-context-tokens 4096 --include-text
```

## Selection Rules

```text
enabled=false -> skip_reason=memory_item_disabled
status not ready or empty text -> skip_reason=manual_text_missing
budget overflow -> skip_reason=token_budget_exceeded
```

## Safety Boundary

- Read-only.
- No artifact write.
- No Provider call.
- No final prompt rendering.
- No prompt log.
- No chapter content read.
- No world book/RAG/export update.
- No draft or confirmed chapter mutation.
- No plaintext secrets.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_context_assembler
```

Result:

```text
Ran 24 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 184 tests
OK
```

Secret scan for the previously supplied Chutes key fragments:

```text
No matches.
```

## Known Limits

- This is not yet final prompt rendering.
- It does not include world book, RAG, style templates, or chapter-specific prompt material.
- It does not call Providers.
- It does not persist package preview artifacts.

## Next Step

MVP-11.5 should add a no-write Prompt Render Dry-Run that combines an operator-supplied draft prompt with the context package preview and reports a redacted prompt envelope by default.
