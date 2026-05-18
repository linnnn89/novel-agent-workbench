# MVP-6 Confirmed Context Update Queue

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add an explicit metadata queue between confirmed chapters and future formal context updates. This prepares for Memory Bank/RAG/export work without automatically mutating those systems.

## Files Changed

```text
src/novel_agent_workbench/context_queue.py
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
data/context_update_queue.json
```

Queue item fields:

```text
update_id
chapter_id
title
source_draft_id
confirmed_chapter_id
status
created_at
updated_at
source
text_stats
targets
reason_code
```

No chapter content, prompt text, raw Provider response, or plaintext secret is stored.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> enqueue-context-updates <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-context-updates <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> mark-context-update <project_id> <update_id> --status acknowledged --reason-code manual_done
```

## Safety Boundary

The queue does not update Memory Bank, RAG, exports, DOCX, drafts, confirmed chapters, or Providers. It only records that a confirmed chapter is pending future explicit context work.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_context_queue tests.test_audit tests.test_application_service tests.test_cli
```

Result:

```text
Ran 48 tests in 3.030s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 153 tests in 9.021s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Next Step

Commit this slice, then consider MVP-6.5 context update preview/exportable plan.
