# MVP-14 Corpus Boundary Indexes

Date: 2026-05-19, Asia/Shanghai.

## Goal

Add explicit no-text chapter boundary artifacts for external `.txt` corpora.

This is not import and not sampling. It only stores offsets for future manual planning.

## Files Changed

```text
src/novel_agent_workbench/corpus_boundaries.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
tests/test_corpus_boundaries.py
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
data/corpus_boundaries/*.json
data/corpus_boundaries_index.json
```

Boundary entries include:

```text
ordinal
heading_line_number
body_start_line
body_end_line
body_start_char
body_end_char
body_char_count
```

Boundary artifacts exclude:

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
py -3.13 -m novel_agent_workbench.cli --projects-root <root> save-corpus-boundaries <project_id> <txt-path>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-corpus-boundaries <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-corpus-boundaries <project_id> <boundary_id>
```

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_corpus_boundaries tests.test_application_service tests.test_audit
py -3.13 -m unittest tests.test_corpus_profile_artifacts tests.test_corpus_profiler
```

Result:

```text
Ran 31 tests in 2.110s
OK

Ran 5 tests in 0.217s
OK
```

Full-suite result should be recorded after final regression.

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 201 tests in 17.634s
OK
```

Leak scans:

```text
Chutes key fragments: no matches
real corpus excerpt phrases: no matches
```

## Known Limits

- Boundary detection is based on strict `第...章/节/卷/回/幕` heading regex.
- Boundary artifacts cannot restore or extract text by themselves because they intentionally do not store source paths or source text.
- Moving from offsets to excerpts/summaries/style memory requires a user decision.
