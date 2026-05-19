# MVP-15.5 Prepublish Readiness Check

Date: 2026-05-19, Asia/Shanghai.

## Goal

Add a read-only backend and CLI check that can be run before any future GitHub publication.

The check must catch:

- missing required `.gitignore` patterns,
- publishable `secrets.local.json` and `.env*` files,
- real-corpus sample artifacts,
- high-risk audit findings involving secrets, prompt text, generated content, or corpus sample blockers.

## Files Changed

```text
src/novel_agent_workbench/publication.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
tests/test_publication.py
README.md
src/README.md
tests/README.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## CLI

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

## Safety Boundary

`prepublish-check` is read-only. It does not delete files, mutate runtime projects, call Providers, read external corpus text, create drafts, create confirmed chapters, update Memory Bank/RAG/export, or print corpus sample text/secrets.

Real-corpus samples are blockers. Runtime Provider findings such as disabled adapters or missing local Provider secrets are warnings when they do not leak secrets, prompt text, or content.

## Verification

Targeted tests before documentation:

```powershell
py -3.13 -m unittest tests.test_publication tests.test_corpus_samples tests.test_application_service
```

Result:

```text
Ran 17 tests in 0.992s
OK
```

Current repository smoke:

```text
prepublish-check ok=true
blocker_count=0
warning_count=4
```

Warnings are from old local Chutes runtime projects with disabled adapter / missing local secret references. They did not expose keys, prompt text, generated content, or corpus samples.

Full regression is recorded after this log is written.

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 208 tests in 19.025s
OK
```

Leak scan:

```text
Known Chutes key fragments and known real-corpus sample snippets: no matches in novel_agent_workbench or PROJECT_INDEX.md.
```

Final prepublish summary after documentation updates:

```text
blocker_count=0
warning_count=4
finding_count=4
```

## Next

Continue corpus-derived testing with publish blockers visible. Before any GitHub publication, run `prepublish-check` and resolve every blocker.
