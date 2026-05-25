# 2026-05-19 MVP-27.4 Sample-Only Commit Blocker

Scope:

- Recorded the latest clean Chutes draft as a smoke-test sample only by setting its review decision to `needs_revision` with `reason_code=smoke_test_only`.
- Added a commit-gate blocker for `accepted` reviews whose `reason_code` is `smoke_test_only`.
- Added regression coverage that such drafts remain unconfirmed and keep draft status.
- Updated project README and decision log.

Boundaries:

- Does not overwrite drafts.
- Does not call Providers.
- Does not auto-commit.
- Does not create confirmed chapters.
- Does not update Memory Bank/RAG/export.
- Does not create DOCX or UI.
- Does not delete real files.

Verification:

```powershell
py -3.13 -m unittest tests.test_chapter_workflow
py -3.13 -m unittest tests.test_reviews
py -3.13 -m unittest discover -s tests
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

Result:

```text
Ran 6 tests in tests.test_chapter_workflow: OK
Ran 18 tests in tests.test_reviews: OK
Ran 298 tests: OK
prepublish-check: ok=true, blocker_count=0, warning_count=6
```
