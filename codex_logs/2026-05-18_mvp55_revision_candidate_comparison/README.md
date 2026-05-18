# MVP-5.5 Revision Candidate Comparison

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add a read-only backend surface for comparing a source draft with a mock revision draft candidate after a revision request has produced a candidate.

## Files Changed

```text
src/novel_agent_workbench/revision_candidates.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
tests/test_revision_requests.py
README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
src/README.md
tests/README.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## New API

Facade:

```text
WorkbenchApplicationService.list_revision_candidates(project_id, revision_request_id)
WorkbenchApplicationService.compare_revision_candidate(project_id, revision_request_id, candidate_draft_id)
```

CLI:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-revision-candidates <project_id> <revision_request_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> compare-revision-candidate <project_id> <revision_request_id> <candidate_draft_id>
```

## Safety Boundary

The comparison read-model returns only metadata:

- draft ids,
- chapter id/title/status,
- provider/model/usage,
- character count,
- word count,
- line count,
- deltas,
- link checks,
- `manual_review_required`.

It does not return source draft content, candidate draft content, original prompt text, raw Provider response, request body, or plaintext secrets.

It writes no files and does not choose a candidate, overwrite drafts, auto-commit, update Memory Bank, update RAG, create exports, create DOCX, call Providers, or enable real Providers.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_revision_requests tests.test_application_service tests.test_cli
```

Result:

```text
Ran 43 tests in 4.815s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 148 tests in 9.220s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Next Step

Commit this slice, then move toward MVP-6 confirmed-context update queue design.
