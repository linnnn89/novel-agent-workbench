# MVP-3.5 Draft Review / Quality Check

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add a backend-only Draft Review / Quality Check skeleton that can create metadata-only review artifacts for drafts using the existing mock scorer role.

## Modified Files

- `src/novel_agent_workbench/reviews.py`
- `src/novel_agent_workbench/chapters.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/cli.py`
- `src/novel_agent_workbench/project_state.py`
- `src/novel_agent_workbench/audit.py`
- `src/novel_agent_workbench/__init__.py`
- `tests/test_reviews.py`
- `tests/test_application_service.py`
- Documentation files in `README.md`, `src/novel_agent_workbench/README.md`, `codex_docs/`, `tests/README.md`, and `codex_logs/README.md`.

## Storage Structure

```text
data/reviews/<chapter_id>__<review_id>.json
data/reviews_index.json
```

Review artifact fields include:

```text
review_id
draft_id
chapter_id
status
scores
issues
recommendation
provider/model/usage
created_at
request_summary
```

## Safety Boundary

- Review uses the configured `scorer` role, currently expected to be `provider=mock`.
- Review artifacts do not store draft content, original prompt text, raw Provider responses, request bodies, or plaintext secrets.
- Review does not auto-commit, auto-revise, update Memory Bank, update RAG, create exports, create DOCX, or enable new real Providers.
- Chapter workflow adds `review_ready` and `latest_review_id`.
- Audit now scans review index/artifacts for prompt, content, and secret leak patterns.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 124 tests in 5.477s
OK
```

## Known Unimplemented Items

- No real scoring Provider is enabled.
- No automatic revision workflow.
- No review-based commit gate.
- No UI, DOCX export, Memory Bank update, RAG update, or export generation.

## Next Step

MVP-4 should add a minimal revision request skeleton or a manual review decision layer, still keeping confirmed chapters as the only formal-context boundary.
