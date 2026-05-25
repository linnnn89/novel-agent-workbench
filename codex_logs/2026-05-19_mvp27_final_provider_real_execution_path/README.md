# MVP-27 Final Provider Real Execution Path

Date: 2026-05-19, Asia/Shanghai.

## Operation

Implemented the explicit Chutes-backed final Provider real execution path, with tests using a patched Chutes client and no real network call.

## Files Changed

```text
src/novel_agent_workbench/final_provider_real_executions.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/__init__.py
tests/test_final_provider_real_executions.py
tests/test_application_service.py
README.md
src/README.md
tests/README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_logs/README.md
```

Workspace index/tracker updates:

```text
I:\AI-NOVEL\PROJECT_INDEX.md
I:\AI-NOVEL\codex_docs\MVP_TRACKER.md
```

## Behavior

- `execute-final-provider-real` requires `--allow-network`.
- The readiness report must be `ready_for_manual_real_llm_authorization` with zero issues.
- The current writer config must remain Chutes.
- The approved gate digest must match the provided prompt/system/context before execution.
- The service temporarily enables Chutes real generation, calls the writer Provider, writes one new draft, and disables the real Provider gate afterward.
- Execution artifacts are metadata-only and link to the draft id without storing prompt, context, generated text, raw response, request body, or secret values.

## Boundaries

This slice does not:

```text
auto-commit
create confirmed chapters
update Memory Bank
update RAG
create exports
create DOCX
add UI
delete files
store generated draft text in execution metadata
```

## Verification

Targeted verification:

```powershell
py -3.13 -m unittest tests.test_final_provider_real_executions tests.test_final_provider_real_execution_readiness tests.test_application_service
```

Result:

```text
Ran 18 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 293 tests
OK
```

Prepublish:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
ok: true
blocker_count: 0
warning_count: 4
```

The warnings are existing runtime Chutes disabled-adapter/missing-secret warnings.

## Next Step

The remaining manual step is an actual Chutes run using the provided project secret and an explicit live-network confirmation.
