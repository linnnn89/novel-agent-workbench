# MVP-22 Final Provider Runbook Plan

Date: 2026-05-19, Asia/Shanghai.

## Operation

Implemented a backend-only, metadata-only final Provider runbook stage after MVP-20 final assembly gates.

## Files Changed

```text
src/novel_agent_workbench/final_provider_runbooks.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/__init__.py
tests/test_final_provider_runbooks.py
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

- `create-final-provider-runbook` requires an approved final assembly gate.
- Runbook artifacts are written under `data/final_provider_runbooks/*.json`.
- Runbook index metadata is written to `data/final_provider_runbooks_index.json`.
- Status is `pending_operator_authorization`.
- Artifacts store provider/model metadata, digests, token estimates, selected context section summaries, operator checklist flags, and safety flags.
- Artifacts do not store prompt text, context text, chapter text, raw Provider responses, request bodies, or plaintext secrets.

## Boundaries

This slice does not:

```text
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
py -3.13 -m unittest tests.test_final_provider_runbooks tests.test_final_assembly_gates
```

Result:

```text
Ran 10 tests
OK
```

Full regression and prepublish checks are expected after doc synchronization.

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 273 tests
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

The next backend branch now needs an operator/product choice: confirmed-chapter export-readiness manifest without producing export files, or a real Provider authorization-token layer after the runbook stop point without calling real LLMs unless explicitly authorized.
