# MVP-8.5 Formal Context Task Queue

Date: 2026-05-18, Asia/Shanghai.

## Goal

Turn formal context plans into manual per-category task metadata.

This is not Memory Bank application and not text extraction.

## Storage

New project data file:

```text
data/formal_context_task_queue.json
```

Each task records:

```text
task_id
plan_id
preview_id
update_id
chapter_id
category_id
priority
target
memory_weight
recommendation
status
safety
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> enqueue-formal-context-tasks <project_id> <plan_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-formal-context-tasks <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> mark-formal-context-task <project_id> <task_id> --status acknowledged --reason-code manual_done
```

## Safety Boundary

- No chapter text copied.
- No prompt copied.
- No Memory Bank text copied.
- No secrets copied.
- No Provider call.
- No Memory Bank write.
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
Ran 31 tests in 2.505s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result: pending.

```text
Ran 166 tests in 12.140s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.
