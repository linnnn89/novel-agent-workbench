# MVP-7.5 Formal Context Extraction Plan

Date: 2026-05-18, Asia/Shanghai.

## Goal

Turn the MVP-7 formal context priority policy into a durable, metadata-only extraction plan artifact.

This is still not extraction and not Memory Bank/RAG/export writing.

## Storage Structure

New project data files:

```text
data/formal_context_plans/*.json
data/formal_context_plans_index.json
```

Plan artifacts are created from context update previews and include:

```text
plan_id
preview_id
update_id
chapter_id
title
source_draft_id
confirmed_chapter_id
status
created_at
priority_order
categories
text_stats
safety
recommendation
```

Category order:

```text
world_building
character_relationships
chapter_summary
style_memory
foreshadowing
```

## Safety Boundary

- No chapter text copied.
- No prompt copied.
- No secrets copied.
- No Provider call.
- No draft or confirmed chapter mutation.
- No Memory Bank write.
- No RAG write.
- No export write.
- Duplicate plan for the same preview is rejected.

## Files Changed

```text
src/novel_agent_workbench/formal_context.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/__init__.py
tests/test_context_queue.py
tests/test_application_service.py
README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
src/README.md
tests/README.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_context_queue tests.test_application_service tests.test_audit
```

Result:

```text
Ran 36 tests in 2.893s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result: pending.

```text
Ran 159 tests in 10.374s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Next Step

Commit this slice, then continue toward MVP-8 manual formal context apply queue.
