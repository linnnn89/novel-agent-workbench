# 2026-05-22 MVP-30 Provider Config Snapshot / Drift Audit

Scope:

- Added safe `config_snapshot` metadata to new Provider smoke-test artifacts.
- Snapshot records role, provider, model, base URL host, `api_key_ref`, secret name, api-key-reference presence, and `real_generation_enabled`.
- Added audit drift detection against the latest passed smoke test with a snapshot.
- Added prepublish behavior that reports config drift as a warning, not a blocker.
- Added regression tests for snapshot storage, audit drift finding, and prepublish warning severity.
- Updated README, decision log, CLI quickstart, project charter, application-service contract, and tests README.

Boundaries:

- Does not store secret values.
- Does not clear or rotate keys.
- Does not call Providers.
- Does not write drafts.
- Does not create confirmed chapters.
- Does not auto-commit.
- Does not update Memory Bank/RAG/export.
- Does not create DOCX or UI.
- Does not delete files.

Verification:

```powershell
py -3.13 -m unittest tests.test_provider_smoke_tests tests.test_audit tests.test_publication
py -3.13 -m unittest tests.test_application_service tests.test_cli
py -3.13 -m unittest discover -s tests
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
Focused tests: OK
Ran 306 tests: OK
current chutes_live_20260519_2 audit: finding_codes=provider_adapter_disabled, smoke_drift_findings=0
prepublish-check: ok=true, blocker_count=0, warning_count=6, smoke_drift_warnings=0
```
