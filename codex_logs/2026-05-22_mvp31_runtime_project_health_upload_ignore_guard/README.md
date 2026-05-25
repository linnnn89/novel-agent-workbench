# MVP-31 Runtime Project Health Summary And Upload Ignore Guard

Date: 2026-05-22, Asia/Shanghai.

## Operation

Added a read-only, metadata-only project health summary and strengthened upload ignore/prepublish coverage.

## Files Changed

- `.gitignore`
- `src/novel_agent_workbench/project_health.py`
- `src/novel_agent_workbench/application_service.py`
- `src/novel_agent_workbench/cli.py`
- `src/novel_agent_workbench/publication.py`
- `src/novel_agent_workbench/__init__.py`
- `tests/test_application_service.py`
- `tests/test_cli.py`
- `tests/test_publication.py`
- `README.md`
- `codex_docs/APPLICATION_SERVICE_CONTRACT.md`
- `codex_docs/CLI_QUICKSTART.md`
- `codex_docs/DECISIONS.md`
- `codex_docs/PROJECT_CHARTER.md`
- `tests/README.md`
- `codex_logs/README.md`

## Behavior

- `project-health` joins public project state, project audit, Provider role metadata, latest smoke-test metadata, and optional upload readiness.
- Default health output excludes prompt text, draft/chapter content, Provider response text, raw request bodies, plaintext secrets, secret values, and corpus sample text.
- `.gitignore` now covers Python build and coverage artifacts: `build/`, `dist/`, `*.egg-info/`, `*.spec`, `.coverage`, and `htmlcov/`.
- `prepublish-check` requires those ignore patterns and skips generated build/coverage directories while scanning source files.
- `prepublish-check` now excludes non-publishing Provider readiness warnings such as disabled adapters or missing local Provider secrets, while `audit-project` still reports them for operational review.

## Verification

```powershell
py -3.13 -m unittest discover -s I:\AI-NOVEL\novel_agent_workbench\tests
```

Result:

```text
Ran 312 tests
OK
```

Current project health smoke:

```text
project_id: chutes_live_20260519_2
status: warning
audit blocker_count: 0
upload prepublish_ok: true
upload blocker_count: 0
upload warning_count: 0
```

Repository prepublish check:

```text
ok: true
blocker_count: 0
warning_count: 0
```

The remaining single-project audit warning for `chutes_live_20260519_2` is the intentional disabled Chutes adapter readiness signal; it is not an upload-readiness warning.

## Boundary

No network call was made. No Provider was called. No draft was created, overwritten, committed, or promoted. No Memory Bank, RAG, export, DOCX, UI, git commit, key cleanup, file deletion, or old reference project modification was performed.
