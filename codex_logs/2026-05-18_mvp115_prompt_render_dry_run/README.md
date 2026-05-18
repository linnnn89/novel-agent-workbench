# MVP-11.5 Prompt Render Dry-Run

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add a no-write prompt/message envelope preview before any Provider call uses Memory Bank context.

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

`ContextAssemblerService.prompt_render_dry_run(...)` combines:

```text
operator prompt
optional system prompt
context package preview
```

Default output is redacted:

```text
include_prompt_text=false
include_context_text=false
```

Explicit inspection flags:

```text
include_prompt_text=true
include_context_text=true
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> prompt-render-dry-run <project_id> --prompt "Draft the next scene." --max-context-tokens 4096
py -3.13 -m novel_agent_workbench.cli --projects-root <root> prompt-render-dry-run <project_id> --prompt "Draft the next scene." --max-context-tokens 4096 --include-prompt-text --include-context-text
```

## Safety Boundary

- No Provider call.
- No prompt log.
- No artifact write.
- No draft generation.
- No confirmed chapter content read.
- No world book/RAG/export update.
- Prompt text and context text are redacted by default.
- Text inclusion is explicit and local only.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_context_assembler
```

Result:

```text
Ran 27 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 187 tests
OK
```

Secret scan for the previously supplied Chutes key fragments:

```text
No matches.
```

## Next Step

MVP-12 should connect prompt render dry-run to a controlled mock-only generation path first, so context-aware generation can be tested without real Providers or automatic commit.
