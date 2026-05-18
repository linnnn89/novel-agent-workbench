# MVP-9 Memory Apply Preview

Date: 2026-05-18, Asia/Shanghai.

## Goal

Create a metadata-only preview of future Memory Bank writes.

This is not a Memory Bank write and not text extraction.

## Storage

New project data files:

```text
data/memory_apply_previews/*.json
data/memory_apply_previews_index.json
```

Preview artifacts include:

```text
preview_id
task_count
world_book_enabled
items
summary
safety
recommendation
```

Each item records task/category metadata only:

```text
task_id
plan_id
chapter_id
category_id
priority
target
memory_weight
duplicate_risk
proposed_action
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> create-memory-apply-preview <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-memory-apply-previews <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-memory-apply-preview <project_id> <preview_id>
```

## Safety Boundary

- No `memory_bank.json` write.
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
py -3.13 -m unittest tests.test_context_assembler tests.test_application_service tests.test_audit
```

Result:

```text
Ran 34 tests in 2.959s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result: pending.

```text
Ran 169 tests in 13.079s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.
