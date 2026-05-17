# MVP-4.5 Revision Request Skeleton

Date: 2026-05-17, Asia/Shanghai.

## Goal

Create a metadata-only Revision Request layer that can be created only after a `needs_revision` review decision.

## Modified Files

- `src/novel_agent_workbench/revisions.py`
- `src/novel_agent_workbench/chapters.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/cli.py`
- `src/novel_agent_workbench/project_state.py`
- `src/novel_agent_workbench/audit.py`
- `src/novel_agent_workbench/__init__.py`
- `tests/test_revision_requests.py`
- `tests/test_application_service.py`
- Documentation files in `README.md`, `src/novel_agent_workbench/README.md`, `codex_docs/`, `tests/README.md`, and `codex_logs/README.md`.

## Storage Structure

```text
data/revision_requests/<chapter_id>__<revision_request_id>.json
data/revision_requests_index.json
```

Revision request artifact fields include:

```text
revision_request_id
review_id
draft_id
chapter_id
status
created_at
source_decision
revision_policy
request_summary
future_hooks
```

## Safety Boundary

- Source review decision must be `needs_revision`.
- Pending, accepted, blocked, missing, and duplicate requests are rejected.
- The operation does not call Providers or LLMs.
- The operation does not mutate draft artifacts.
- The operation does not create confirmed chapters.
- The operation does not update Memory Bank, RAG, export settings, or exports.
- The operation stores no prompt text, draft content, raw Provider responses, plaintext secrets, or free-text notes.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> create-revision-request <project_id> <review_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-revision-requests <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-revision-request <project_id> <revision_request_id>
```

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 136 tests in 7.923s
OK
```

## Known Unimplemented Items

- No revision generation service.
- No automatic draft mutation.
- No review-to-commit gate.
- No UI, DOCX export, Memory Bank update, RAG update, or export generation.

## Next Step

MVP-5 can add a Mock Revision Draft Service that creates a new draft candidate from a revision request, still with mock provider only and no automatic overwrite or commit.
