# MVP-13.5 Corpus Profile Artifacts

Date: 2026-05-19, Asia/Shanghai.

## Goal

Add an explicit project-local artifact layer for saving conservative corpus profile metadata.

This is still not corpus import. It stores structure metadata only.

## Files Changed

```text
src/novel_agent_workbench/corpus_profiles.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
tests/test_corpus_profile_artifacts.py
tests/test_application_service.py
README.md
src/README.md
tests/README.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_logs/README.md
```

## Storage

```text
data/corpus_profiles/*.json
data/corpus_profiles_index.json
```

Persistent artifact includes:

```text
file name
source size
source SHA-256
encoding
line/chapter statistics
dialogue proxy statistics
safety flags
```

Persistent artifact excludes:

```text
external source path
source text
chapter heading text
dialogue excerpts
candidate-name text
plaintext secrets
```

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> save-corpus-profile <project_id> <txt-path>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-corpus-profiles <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-corpus-profile <project_id> <profile_id>
```

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_corpus_profile_artifacts tests.test_application_service
py -3.13 -m unittest tests.test_corpus_profiler
py -3.13 -m unittest tests.test_corpus_profile_artifacts tests.test_application_service tests.test_audit
```

Result:

```text
Ran 12 tests in 0.795s
OK

Ran 2 tests in 0.009s
OK

Ran 31 tests in 2.032s
OK
```

Full-suite result should be recorded after final regression.

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 198 tests in 16.985s
OK
```

Leak scans:

```text
Chutes key fragments: no matches
real corpus excerpt phrases: no matches
```

## Known Limits

- Persistent profile artifacts intentionally do not store candidate names.
- This layer does not import chapters, create samples, or build a style/character/world database.
- A later user decision is needed before storing excerpts, summaries, or derived style memory from real corpus text.
- `audit-project` now rejects persistent corpus profile artifacts that store external source paths or candidate-name text.
