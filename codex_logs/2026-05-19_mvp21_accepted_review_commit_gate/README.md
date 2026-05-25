# MVP-21 Accepted Review Commit Gate

Date: 2026-05-19, Asia/Shanghai.

## Operation

Hardened confirmed-chapter promotion so `commit_draft` requires an accepted review for the same draft before writing confirmed chapter files.

## Files Changed

```text
src/novel_agent_workbench/drafts.py
src/novel_agent_workbench/__init__.py
src/novel_agent_workbench/cli.py
tests/*.py
README.md
src/README.md
tests/README.md
codex_docs/*.md
codex_logs/README.md
```

## Behavior

- unreviewed, pending-review, `needs_revision`, or `blocked` drafts cannot be committed.
- commit gate failures raise `DraftCommitGateError` without changing chapter workflow state.
- accepted reviews for the same draft allow explicit commit.
- confirmed chapter artifacts and commit logs record metadata-only `commit_gate` information.
- manual rewrite draft candidates still require their guarded review metadata before commit can pass.

## Safety Boundary

This gate does not auto-review, auto-accept, auto-commit, overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, delete files, or call any real LLM.

## Verification

Targeted and full regression:

```powershell
py -3.13 .\tests\test_draft_generation.py
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 16 tests
OK

Ran 269 tests
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
