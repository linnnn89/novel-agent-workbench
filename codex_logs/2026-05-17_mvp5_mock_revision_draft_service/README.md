# MVP-5 Mock Revision Draft Service

Date: 2026-05-17, Asia/Shanghai.

## Goal

Create a mock-only Revision Draft Service that turns one `requested` revision request into a new draft candidate.

## Modified Files

- `src/novel_agent_workbench/revisions.py`
- `src/novel_agent_workbench/chapters.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/cli.py`
- `src/novel_agent_workbench/project_state.py`
- `src/novel_agent_workbench/README.md`
- `tests/test_revision_requests.py`
- Documentation files in `README.md`, `codex_docs/`, `tests/README.md`, and `codex_logs/README.md`.

## Behavior

`RevisionRequestService.generate_revision_draft(...)`:

1. Requires `revision_request.status == requested`.
2. Reads the source draft only for metadata and length.
3. Calls the configured `reviser` role through the local `mock` Provider.
4. Writes a new draft artifact under `data/drafts/`.
5. Appends `data/drafts_index.json`.
6. Updates the revision request to `draft_created` with `generated_draft_id`.
7. Marks chapter workflow as `revision_draft_ready`.

## Safety Boundary

- Source draft is not overwritten or mutated.
- No automatic commit.
- No confirmed chapter creation.
- No Memory Bank, RAG, export settings, export files, UI, or DOCX side effects.
- No real Provider is called.
- CLI/facade/index/log/public-state/audit surfaces do not expose prompt text, source draft content, candidate draft content, raw Provider response, request body, or plaintext secrets.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> generate-revision-draft <project_id> <revision_request_id>
```

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 141 tests in 8.598s
OK
```

## Known Unimplemented Items

- No real revision Provider.
- No automatic merge or overwrite.
- No review-decision commit gate.
- No UI, DOCX export, Memory Bank update, RAG update, or export generation.

## Next Step

MVP-5.5 can add a revision-candidate comparison/read model that lists source draft, review, revision request, and candidate draft metadata side by side without exposing content in public state.
