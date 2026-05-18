# MVP-6.5 Context Update Preview

Date: 2026-05-18, Asia/Shanghai.

## Goal

Create metadata-only preview artifacts from confirmed-context queue items. This gives future UI or manual review a stable plan artifact before any Memory Bank/RAG/export mutation exists.

## Files Changed

```text
src/novel_agent_workbench/context_previews.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
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

## Storage

```text
data/context_update_previews/*.json
data/context_update_previews_index.json
```

Preview fields:

```text
preview_id
update_id
chapter_id
title
source_draft_id
confirmed_chapter_id
status
created_at
source
text_stats
target_plan
safety
recommendation
```

No chapter text, prompt text, raw Provider response, request body, or plaintext secret is stored.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> create-context-preview <project_id> <update_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-context-previews <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-context-preview <project_id> <preview_id>
```

## Safety Boundary

Preview artifacts are not formal context updates. They do not update Memory Bank, RAG, exports, DOCX, drafts, confirmed chapters, or Providers.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_context_queue tests.test_audit tests.test_application_service tests.test_cli
```

Result:

```text
Ran 51 tests in 3.545s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 156 tests in 10.156s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Next Step

Commit this slice, then stop for a product decision on the formal context policy schema.
