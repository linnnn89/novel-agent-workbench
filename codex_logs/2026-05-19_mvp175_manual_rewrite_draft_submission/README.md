# MVP-17.5 Manual Rewrite Draft Submission

Date: 2026-05-19, Asia/Shanghai.

## Goal

Allow a manual rewrite task to submit explicit human text as a new draft candidate.

This is the first manual rewrite path that stores human draft content, but only inside a new draft artifact. It does not overwrite old drafts, auto-commit, create revision requests, call Providers, or update Memory Bank/RAG/export.

## Files Changed

```text
src/novel_agent_workbench/manual_rewrite.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/__init__.py
tests/test_manual_rewrite.py
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

New draft candidate:

```text
data/drafts/*.json
data/drafts_index.json
```

Updated task metadata:

```text
data/manual_rewrite_tasks/*.json
data/manual_rewrite_tasks_index.json
```

New draft source marker:

```text
manual_rewrite.manual_rewrite_task_id
manual_rewrite.source_suggestion_id
manual_rewrite.source_check_id
manual_rewrite.source_draft_id
```

The submitted text is stored only as draft `content`. CLI/facade submission results are metadata-only.

## CLI

```powershell
submit-manual-rewrite-draft <project_id> <task_id> --text "human rewrite text"
submit-manual-rewrite-draft <project_id> <task_id> --text-stdin
```

## Safety Boundary

Manual rewrite draft submission must not:

- call Providers,
- overwrite the source draft,
- create revision requests,
- auto-commit,
- create confirmed chapters,
- update Memory Bank,
- update RAG,
- create exports.

Empty text, skipped tasks, and duplicate submissions are rejected.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_manual_rewrite tests.test_application_service
```

Result:

```text
Ran 20 tests in 4.449s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 241 tests in 26.190s
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

Future work can add a manual comparison view between source draft and submitted manual rewrite candidate. That comparison should remain metadata-only by default and should not auto-commit.
