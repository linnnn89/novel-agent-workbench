# MVP-20.5 Review Handoff Consumption

Date: 2026-05-19, Asia/Shanghai.

## Operation

Added metadata consumption for review handoffs after a selected manual rewrite draft is successfully reviewed through the existing guarded review path.

## Files Changed

```text
src/novel_agent_workbench/review_handoffs.py
src/novel_agent_workbench/reviews.py
tests/test_reviews.py
README.md
src/README.md
tests/README.md
codex_docs/*.md
codex_logs/README.md
```

## Behavior

When `review-draft` is allowed by a `pending_review` handoff, successful review creation now updates the handoff artifact and index:

```text
status=review_created
review.created=true
review.review_id=<created review id>
review.created_at=<review timestamp>
```

This removes the handoff from `list-review-handoffs --status pending_review`.

## Safety Boundary

The consumption update is metadata only. It does not edit draft bodies, create new drafts, auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, or call an extra Provider beyond the explicit review action.

## Verification

Targeted tests:

```powershell
py -3.13 .\tests\test_reviews.py
py -3.13 .\tests\test_review_handoffs.py
```

Result:

```text
Ran 17 tests
OK

Ran 5 tests
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
