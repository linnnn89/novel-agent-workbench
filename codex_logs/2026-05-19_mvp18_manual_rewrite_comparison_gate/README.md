# 2026-05-19 MVP-18 Manual Rewrite Comparison Gate

## Goal

Build a metadata-only comparison and selection gate for human-submitted manual rewrite draft candidates.

## Scope

- Added `ManualRewriteComparisonService`.
- Added comparison storage:
  - `data/manual_rewrite_comparisons/*.json`
  - `data/manual_rewrite_comparisons_index.json`
- Added CLI:
  - `compare-manual-rewrite-candidate`
  - `list-manual-rewrite-comparisons`
  - `read-manual-rewrite-comparison`
  - `decide-manual-rewrite-comparison`
- Added facade methods on `WorkbenchApplicationService`.
- Added public state fields:
  - `manual_rewrite_comparison_count`
  - `latest_manual_rewrite_comparison`
- Added audit checks for comparison artifacts.

## Storage Contract

Comparison artifacts store only:

- source/submitted draft ids,
- chapter/task/suggestion/check ids,
- character and paragraph deltas,
- simple structural metrics,
- link checks,
- safety flags,
- explicit selection decision metadata.

They must not store source draft text, submitted draft text, prompt text, raw Provider output, or plaintext secrets.

## Safety Boundary

This slice does not:

- call Providers or LLMs,
- overwrite drafts,
- auto-commit drafts,
- create confirmed chapters,
- create revision requests,
- update Memory Bank,
- update RAG,
- create exports,
- modify the old reference project.

## Tests

Targeted command run:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest tests.test_manual_rewrite_comparison tests.test_manual_rewrite tests.test_application_service
```

Result:

```text
Ran 26 tests in 8.074s
OK
```

MVP-18 focused command run:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest tests.test_manual_rewrite_comparison
```

Result:

```text
Ran 6 tests in 4.066s
OK
```

Full regression command run:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 247 tests in 32.417s
OK
```

Diff check:

```powershell
git -c safe.directory=I:/AI-NOVEL/novel_agent_workbench diff --check
```

Result: no whitespace errors; Git only reported CRLF conversion warnings.

Sensitive-string scan:

```powershell
rg -n "<real-key-or-corpus-sentinel-patterns>" I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

Prepublish check:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
ok: true
blocker_count: 0
finding_count: 4
warning_count: 4
```

The four warnings are the existing local Chutes runtime-project disabled-adapter/missing-secret warnings. They are not publication blockers and no plaintext secret was present.

## Known Limits

- Selection decisions are metadata only. `selected_for_review` does not automatically create a review.
- Comparisons are one per manual rewrite task in this phase.
- Structural metrics are intentionally simple local counts, not semantic analysis.

## Next Suggested Phase

MVP-18.5 can connect `selected_for_review` to an explicit review handoff, still without auto-commit or automatic Memory Bank/RAG/export updates.
