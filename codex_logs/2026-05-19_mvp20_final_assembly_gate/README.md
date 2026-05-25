# MVP-20 Final Assembly Gate

Date: 2026-05-19, Asia/Shanghai.

## Operation

Implemented a backend-only final Provider assembly approval gate before any future real context-aware Provider path.

## Files Changed

```text
src/novel_agent_workbench/final_assembly_gates.py
src/novel_agent_workbench/drafts.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/__init__.py
tests/test_final_assembly_gates.py
tests/test_application_service.py
README.md
src/README.md
tests/README.md
codex_docs/*.md
```

## Safety Boundary

The gate writes `data/final_assembly_gates/*.json` and `data/final_assembly_gates_index.json`.

Artifacts store only:

```text
chapter id
writer provider/model metadata
prompt/system/context digests
context section summaries
token estimates
approval metadata
safety flags
```

They must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, or plaintext secrets.

## Behavior

- `create-final-assembly-gate` creates a pending approval artifact from a redacted prompt render dry-run.
- `approve-final-assembly-gate` marks one gate as approved with an optional safe `reason_code`.
- real context-aware generation attempts now require an approved matching gate before any Provider/workflow side effect.
- even after a gate passes, real context-aware Provider generation remains disabled in this phase.

## Verification

Targeted test:

```powershell
py -3.13 .\tests\test_final_assembly_gates.py
```

Result:

```text
Ran 6 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 268 tests
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

The warnings are the existing local Chutes runtime-project disabled-adapter/missing-secret warnings.

## Risks / Next Step

Next backend candidate: consume `pending_review` handoffs after guarded review creation, still without auto-commit, draft overwrite, Memory Bank/RAG/export update, UI, DOCX, or real LLM calls.
