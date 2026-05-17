# MVP-3 Chapter Workflow

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add the minimal chapter workflow state machine:

```text
planned -> drafting -> draft_ready -> committed / blocked
```

This remains backend-only. No UI, DOCX, scoring/revision workflow, automatic Memory Bank update, RAG update, or export creation was added.

## Storage

New metadata-only file:

```text
data\chapters_workflow.json
```

Each chapter entry tracks:

```text
chapter_id
title
status
created_at
updated_at
latest_draft_id
confirmed_chapter_id
error_summary
```

It must not store prompt text, system prompt text, generated content, raw provider response, request body, or plaintext secrets.

## Code Changes

New module:

```text
src\novel_agent_workbench\chapters.py
```

Updated modules:

```text
src\novel_agent_workbench\drafts.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\project_state.py
src\novel_agent_workbench\audit.py
src\novel_agent_workbench\__init__.py
```

## CLI

New commands:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> mark-chapter-planned <project_id> chapter_001 --title "Opening"
py -3.13 -m novel_agent_workbench.cli --projects-root <root> chapter-status <project_id> chapter_001
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-chapters <project_id>
```

## Behavior

Draft generation:

```text
before provider call: drafting
success: draft_ready + latest_draft_id
failure: blocked + metadata-only error_summary
```

Explicit commit:

```text
success: committed + confirmed_chapter_id
failure: metadata-only error_summary
```

If a chapter is already `committed`, a later failed commit does not downgrade it to `blocked`.

## Audit Boundary

`audit-project` now scans `data\chapters_workflow.json` for prompt, secret, or content-looking leaks.

## Tests

Targeted command:

```powershell
py -3.13 -m unittest tests.test_chapter_workflow
```

Result:

```text
Ran 5 tests
OK
```

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 117 tests in 4.848s
OK
```
