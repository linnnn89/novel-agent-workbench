# 2026-05-22 MVP-28 Provider Live Smoke Test Harness

Scope:

- Added `ProviderSmokeTestService` for persistent metadata-only Provider connectivity checks.
- Added CLI commands `run-provider-smoke-test`, `list-provider-smoke-tests`, and `read-provider-smoke-test`.
- Added application-service facade methods and public project-state summaries.
- Added tests for default blocked no-network behavior, mocked authorized pass behavior, CLI metadata-only output, and no draft creation.
- Updated README, decision log, CLI quickstart, project charter, application-service contract, and tests README.

Boundaries:

- Does not call Providers unless `allow_network=True`.
- Does not write drafts.
- Does not create confirmed chapters.
- Does not auto-commit.
- Does not update Memory Bank/RAG/export.
- Does not create DOCX or UI.
- Does not store prompt text, response text, raw request bodies, or plaintext secrets.
- Does not delete real files.

Verification:

```powershell
py -3.13 -m unittest tests.test_provider_smoke_tests
py -3.13 -m unittest tests.test_provider_config
py -3.13 -m unittest discover -s tests
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
Ran 3 tests in tests.test_provider_smoke_tests: OK
Ran 31 tests in tests.test_provider_config: OK
Ran 301 tests: OK
prepublish-check: ok=true, blocker_count=0, warning_count=6
```
