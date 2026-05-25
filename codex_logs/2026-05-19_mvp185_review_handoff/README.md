# 2026-05-19 MVP-18.5 Review Handoff

## Goal

Create an explicit metadata-only handoff from a selected manual rewrite candidate to a later review step.

## Scope

- Added `ReviewHandoffService`.
- Added storage:
  - `data/review_handoffs/*.json`
  - `data/review_handoffs_index.json`
- Added CLI:
  - `create-review-handoff-from-manual-comparison`
  - `list-review-handoffs`
  - `read-review-handoff`
- Added facade methods on `WorkbenchApplicationService`.
- Added public state fields:
  - `review_handoff_count`
  - `latest_review_handoff`
- Added audit checks for review handoff artifacts.

## Safety Boundary

Review handoffs can only be created from manual rewrite comparisons already decided as `selected_for_review`.

This slice does not:

- call Providers or LLMs,
- run `review-draft`,
- overwrite drafts,
- auto-commit drafts,
- create confirmed chapters,
- update Memory Bank,
- update RAG,
- create exports,
- modify the old reference project.

## Verification

Targeted commands:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest discover -s novel_agent_workbench\tests -p "test_review_handoffs.py"
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest discover -s novel_agent_workbench\tests -p "test_manual_rewrite_comparison.py"
```

Result:

```text
review handoffs: Ran 5 tests, OK
manual rewrite comparison: Ran 6 tests, OK
```

Focused follow-up:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest discover -s novel_agent_workbench\tests -p "test_application_service.py"
```

Result:

```text
Ran 10 tests, OK
```

Full regression:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest discover -s novel_agent_workbench\tests
```

Result:

```text
Ran 252 tests in 34.719s
OK
```

Prepublish:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
ok: true
blocker_count: 0
warning_count: 4
```

The four warnings are the existing local Chutes runtime-project disabled-adapter/missing-secret warnings. They are not publication blockers and no plaintext secret was present.

Diff check:

```powershell
git -C novel_agent_workbench -c safe.directory=I:/AI-NOVEL/novel_agent_workbench diff --check
```

Result: no whitespace errors; Git reported line-ending conversion warnings only.

## Known Limits

- A handoff does not create a review by itself.
- The next explicit action is still a separate review command or future guarded review route.
