# MVP-26 Final Provider Real Execution Readiness

Date: 2026-05-19, Asia/Shanghai.

## Operation

Implemented a backend-only, no-network real execution readiness report after the MVP-25 fail-closed execution attempt.

## Files Changed

```text
src/novel_agent_workbench/final_provider_real_execution_readiness.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/__init__.py
tests/test_final_provider_real_execution_readiness.py
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

- `create-final-provider-real-execution-readiness` requires a fail-closed final Provider execution attempt.
- Duplicate readiness reports for the same attempt are rejected.
- Readiness artifacts are written under `data/final_provider_real_execution_readiness/*.json`.
- Readiness index metadata is written to `data/final_provider_real_execution_readiness_index.json`.
- Status is `ready_for_manual_real_llm_authorization` when no-network checks pass, otherwise `blocked`.
- Checks cover source attempt status, source preflight status, no prior Provider/LLM call, current provider/model match, Chutes provider selection, api_key_ref presence, project-secret presence, disabled real generation, and valid secret ref syntax.
- Artifacts store ids, safe provider config metadata, key presence boolean, digests, token estimates, manual action ids, execution boundary flags, and safety flags.
- Artifacts do not store prompt text, context text, chapter text, raw Provider responses, request bodies, plaintext execution tokens, generated text, or plaintext secrets.

## Boundaries

This slice does not:

```text
read secret values for use
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
py -3.13 -m unittest tests.test_final_provider_real_execution_readiness tests.test_final_provider_execution_attempts tests.test_final_provider_execution_preflights tests.test_application_service
```

Result:

```text
Ran 22 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 289 tests
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

The next backend branch is the actual Chutes real LLM execution path. It requires the user to provide or confirm a Chutes key and explicitly authorize a real network call before any Provider request is sent.
