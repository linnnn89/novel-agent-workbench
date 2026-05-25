# 2026-05-22 MVP-29 Provider Smoke Test Audit Gate

Scope:

- Added `audit-project` checks for `data/provider_smoke_tests_index.json` and `data/provider_smoke_tests/*.json`.
- Validates metadata-only storage, valid smoke status, authorization-state consistency, sample-only/non-committable classification, safety flags, and no draft/confirmed-chapter linkage.
- Added prepublish blocker handling for invalid Provider smoke-test artifacts.
- Added regression tests for valid smoke metadata, invalid smoke metadata, and prepublish blocking.
- Updated README, decision log, CLI quickstart, project charter, application-service contract, and tests README.

Boundaries:

- Does not call Providers.
- Does not write drafts.
- Does not create confirmed chapters.
- Does not auto-commit.
- Does not update Memory Bank/RAG/export.
- Does not create DOCX or UI.
- Does not delete smoke records or other real files.

Verification:

```powershell
py -3.13 -m unittest tests.test_audit tests.test_publication tests.test_provider_smoke_tests
py -3.13 -m unittest discover -s tests
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects audit-project chutes_live_20260519_2
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
Focused audit/publication/smoke tests: OK
Ran 304 tests: OK
current chutes_live_20260519_2 smoke audit findings: 0
prepublish-check: ok=true, blocker_count=0, warning_count=6, smoke_findings=0
```
