# MVP-25 Final Provider Execution Stub / Abort Gate

Date: 2026-05-19, Asia/Shanghai.

## Operation

Implemented a backend-only final Provider execution entry point that remains fail-closed under the current no-real-LLM policy.

## Files Changed

```text
src/novel_agent_workbench/final_provider_execution_attempts.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/__init__.py
tests/test_final_provider_execution_attempts.py
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

- `attempt-final-provider-execution` requires a final Provider execution preflight with `status=passed_pending_execute_authorization` and `issue_count=0`.
- Duplicate attempts for the same preflight are rejected.
- Attempt artifacts are written under `data/final_provider_execution_attempts/*.json`.
- Attempt index metadata is written to `data/final_provider_execution_attempts_index.json`.
- Current status is always `aborted_real_llm_disabled`.
- Current abort reason is always `real_llm_disabled_by_policy`.
- Artifacts store ids, provider/model metadata, digests, token estimates, execution boundary flags, and safety flags only.
- Artifacts do not store prompt text, context text, chapter text, raw Provider responses, request bodies, plaintext execution tokens, or plaintext secrets.

## Boundaries

This slice does not:

```text
enable real Providers
call real LLMs
write or overwrite drafts
update Memory Bank
update RAG
create exports
create DOCX
add UI
auto-commit
delete files
mutate chapter workflow state
```

## Verification

Targeted verification:

```powershell
py -3.13 -m unittest tests.test_final_provider_execution_attempts tests.test_final_provider_execution_preflights tests.test_final_provider_authorizations tests.test_final_provider_runbooks tests.test_final_assembly_gates tests.test_application_service
```

Result:

```text
Ran 32 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 285 tests
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

The next backend branch is the actual real LLM execution path behind this abort gate. It requires separate explicit operator authorization before any Provider call.
