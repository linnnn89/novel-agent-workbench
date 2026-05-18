# MVP-5 Quality Hardening After Review

Date: 2026-05-18, Asia/Shanghai.

## Goal

Close the main findings from the latest self-review before adding another workflow feature:

- prevent plaintext API keys from lingering in `.bak` files after secret rotation,
- keep MVP-5 revision draft generation explicitly mock-only,
- extend audit to detect broken revision request/generated draft links.

## Files Changed

```text
src/novel_agent_workbench/storage.py
src/novel_agent_workbench/revisions.py
src/novel_agent_workbench/audit.py
tests/test_project_store.py
tests/test_revision_requests.py
tests/test_audit.py
README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/CLI_QUICKSTART.md
src/README.md
tests/README.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## Implementation Notes

`ProjectStore.write_secrets(...)` now uses the same atomic JSON file writer but bypasses normal `.bak` creation. This keeps current secrets durable without preserving old plaintext keys in `backups/`.

`RevisionRequestService.generate_revision_draft(...)` now checks the configured `reviser` role before reading source draft content or creating a new candidate. Non-`mock` revisers fail with `RevisionRequestError`.

`audit-project` now checks revision request consistency:

- orphan revision request artifacts,
- missing or unsafe revision request artifact paths,
- request/index id mismatches,
- missing source drafts,
- missing generated drafts,
- generated draft artifact mismatches,
- generated draft back-links to request, source draft, and source review.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_project_store tests.test_revision_requests tests.test_audit
```

Result:

```text
Ran 39 tests in 3.594s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 145 tests in 8.823s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Boundaries

- Old reference project was not modified.
- No UI, DOCX, scoring返修 automation, Memory Bank/RAG/export automation, or new real Provider work was added.
- No real files were deleted.
- No secrets were printed or committed.

## Next Step

Run full regression, scan for key fragments, commit this hardening slice, then continue with MVP-5.5 revision candidate comparison/read-model planning.
