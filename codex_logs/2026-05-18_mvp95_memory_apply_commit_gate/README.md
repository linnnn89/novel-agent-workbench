# MVP-9.5 Memory Bank Apply Commit Gate

Date: 2026-05-18, Asia/Shanghai.

## Goal

Create the first explicit Memory Bank write path while keeping it reversible and content-safe.

## Behavior

`commit-memory-apply-preview`:

```text
1. reads a Memory Apply Preview
2. creates a pre_memory_apply checkpoint
3. writes placeholder entries into data/memory_bank.json
4. skips duplicate source tasks on repeated commits
```

Written entries:

```text
entry_type=formal_context_placeholder
status=manual_text_required
text=""
text_status=not_extracted
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> commit-memory-apply-preview <project_id> <preview_id>
```

## Safety Boundary

- Creates checkpoint before writing.
- No chapter text copied.
- No prompt copied.
- No existing Memory Bank text copied.
- No secrets copied.
- No Provider call.
- No world book write.
- No RAG write.
- No export write.
- No draft or confirmed chapter mutation.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_context_assembler tests.test_application_service tests.test_audit tests.test_project_foundation
```

Result:

```text
Ran 45 tests in 3.918s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result: pending.

```text
Ran 172 tests in 13.761s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.
