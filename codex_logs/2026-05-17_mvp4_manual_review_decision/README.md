# MVP-4 Manual Review Decision Skeleton

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add a safe backend-only manual decision layer after Draft Review / Quality Check.

## Modified Files

- `src/novel_agent_workbench/reviews.py`
- `src/novel_agent_workbench/chapters.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/cli.py`
- `src/novel_agent_workbench/project_state.py`
- `src/novel_agent_workbench/__init__.py`
- `tests/test_reviews.py`
- `tests/test_application_service.py`
- Documentation files in `README.md`, `src/novel_agent_workbench/README.md`, `codex_docs/`, `tests/README.md`, and `codex_logs/README.md`.

## Decision Model

Allowed decisions:

```text
accepted
needs_revision
blocked
```

Input is fixed enum plus optional safe `reason_code`.

No free-text notes are stored in this phase.

## Storage Boundary

Decision metadata is written into:

```text
data/reviews/*.json
data/reviews_index.json
data/chapters_workflow.json
```

Decision does not create:

```text
data/confirmed_chapters.json
data/confirmed_chapters/
rag/
exports/
```

Decision does not update Memory Bank, RAG, export settings, or export artifacts.

## Safety Boundary

- `accepted` is not a commit.
- `needs_revision` does not generate a revision.
- `blocked` records metadata-only error summary.
- Decision output excludes draft content, original prompts, raw Provider responses, request bodies, plaintext secrets, and free-text notes.
- Only one decision may be recorded for one review in this phase.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 130 tests in 6.985s
OK
```

## Known Unimplemented Items

- No revision generation service.
- No review-decision commit gate.
- No UI, DOCX export, Memory Bank update, RAG update, or export generation.

## Next Step

MVP-4.5 can add a Revision Request skeleton that creates a metadata-only request artifact from a `needs_revision` decision without invoking real LLMs or changing confirmed chapters.
