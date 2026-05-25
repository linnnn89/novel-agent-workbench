# MVP-19.5 Review-Draft Guard

Date: 2026-05-19, Asia/Shanghai.

## Operation

Added a backend guard so submitted manual rewrite draft candidates cannot enter `review-draft` unless the operator has already selected or handed off that candidate.

## Gate Rule

Allowed gates:

```text
selected_for_review manual rewrite comparison
pending_review review handoff
```

Rejected and `needs_more_manual_work` comparisons are not valid gates.

## Files Changed

- `src/novel_agent_workbench/reviews.py`
- `src/novel_agent_workbench/audit.py`
- `tests/test_reviews.py`
- documentation and tracker files

## Safety Boundaries

- Guard runs before any scorer Provider call.
- Denial writes no review artifact and does not change chapter workflow.
- Ordinary draft review remains unchanged.
- No real LLM call.
- No UI work.
- No draft overwrite or auto-commit.
- No confirmed chapter creation.
- No Memory Bank/RAG/export update.
- No DOCX work.
- No old reference project edits.

## Verification

Targeted:

```powershell
py -3.13 -m unittest discover -s novel_agent_workbench\tests -p "test_reviews.py"
py -3.13 -m unittest discover -s novel_agent_workbench\tests -p "test_review_handoffs.py"
```

Result:

```text
test_reviews.py: Ran 17 tests, OK
test_review_handoffs.py: Ran 5 tests, OK
```

## Next Step

Run full regression and prepublish. If clean, the next backend slice is likely a stricter final-provider assembly gate before any real context-aware Provider path.
