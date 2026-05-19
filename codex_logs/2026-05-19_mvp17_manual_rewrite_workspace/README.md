# MVP-17 Manual Rewrite Workspace Skeleton

Date: 2026-05-19, Asia/Shanghai.

## Goal

Turn a `needs_manual_rewrite` style suggestion decision into a human rewrite task artifact.

This is workspace metadata only. It does not call Providers, generate drafts, edit drafts, create revision requests, commit chapters, or update Memory Bank/RAG/export.

## Files Changed

```text
src/novel_agent_workbench/manual_rewrite.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/__init__.py
tests/test_manual_rewrite.py
tests/test_application_service.py
README.md
src/README.md
tests/README.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## Storage

```text
data/manual_rewrite_tasks/*.json
data/manual_rewrite_tasks_index.json
```

Task fields:

```text
task_id
suggestion_id
check_id
draft_id
chapter_id
status
reason_code
created_at
updated_at
safety
```

Supported status:

```text
pending
in_progress
done
skipped
```

## CLI

```powershell
create-manual-rewrite-task <project_id> <suggestion_id>
list-manual-rewrite-tasks <project_id> [--status pending]
read-manual-rewrite-task <project_id> <task_id>
mark-manual-rewrite-task <project_id> <task_id> --status in_progress --reason-code started
```

## Safety Boundary

Manual rewrite tasks must not:

- call Providers,
- generate drafts,
- modify draft artifacts,
- create revision requests,
- auto-revise,
- auto-commit,
- create confirmed chapters,
- update Memory Bank,
- update RAG,
- create exports.

Tasks can only be created from style suggestions with a `needs_manual_rewrite` decision. `accepted` and `ignored` suggestions are rejected. Duplicate tasks for one suggestion are rejected.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_manual_rewrite tests.test_application_service
```

Result:

```text
Ran 17 tests in 2.889s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 238 tests in 24.864s
OK
```

Leak scan:

```powershell
rg -n "<redacted secret and real-corpus sentinel patterns>" I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result:

```text
No matches.
```

Patch check:

```powershell
git -c safe.directory=I:/AI-NOVEL/novel_agent_workbench diff --check
```

Result:

```text
OK. Git reported line-ending conversion warnings only.
```

Prepublish summary:

```json
{
  "blocker_count": 0,
  "finding_count": 4,
  "warning_count": 4
}
```

The four warnings are existing local Chutes runtime warnings. They are not blockers.

## Next

Future UI can show manual rewrite tasks as a queue in the draft review side panel. The actual human edit surface should be a separate explicit step and should still avoid overwriting old drafts.
