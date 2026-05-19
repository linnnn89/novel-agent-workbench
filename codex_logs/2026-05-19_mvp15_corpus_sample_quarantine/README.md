# MVP-15 Corpus Sample Quarantine

Date: 2026-05-19, Asia/Shanghai.

## User Decision

The user allowed real corpus-derived content to be stored during testing only, with the explicit requirement that those contents be removed before GitHub publication.

## Goal

Add a test-only quarantine layer for bounded real corpus text samples.

## Files Changed

```text
src/novel_agent_workbench/corpus_samples.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
tests/test_corpus_samples.py
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
data/corpus_samples/*.json
data/corpus_samples_index.json
```

Sample artifacts include bounded real text in `sample_text`, but must also include:

```text
test_only: true
publish_blocker: true
required_cleanup: remove_runtime_project_or_retire_sample_artifact_before_github_publish
```

## Safety Boundary

- `max_chars` must be 1 to 2000.
- Source file SHA-256 must match the boundary artifact.
- External source path is not stored.
- Default reads/list/state do not include `sample_text`.
- `--include-text` is required to inspect sample text locally.
- `audit-project` fails with `non_publishable_corpus_sample_present` while samples exist.
- No Provider, draft, confirmed chapter, Memory Bank, RAG, export, DOCX, or UI work.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> create-corpus-sample <project_id> <boundary_id> <txt-path> --ordinal 1 --max-chars 800
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-corpus-samples <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-corpus-sample <project_id> <sample_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-corpus-sample <project_id> <sample_id> --include-text
```

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_corpus_samples tests.test_corpus_boundaries tests.test_application_service tests.test_audit
py -3.13 -m unittest tests.test_corpus_profile_artifacts tests.test_corpus_profiler
```

Result:

```text
Ran 34 tests in 3.013s
OK

Ran 5 tests in 0.295s
OK
```

Full-suite result should be recorded after final regression.

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 204 tests in 18.424s
OK
```

Leak scans:

```text
Chutes key fragments: no matches
real corpus excerpt phrases: no matches
```

## Real Corpus Smoke

The user-authorized corpus 2 was used in a temporary project only.

Smoke result:

```text
boundary_chapter_count: 400
sample_status: sample_ready
sample_char_count: 80
sample_publish_blocker: true
default_read_contains_text: false
audit_ok: false
audit_codes: non_publishable_corpus_sample_present
```

The smoke confirms:

```text
sample text can exist in a temporary runtime artifact
default read output does not return sample text
audit blocks publication while the sample exists
```

## Publication Rule

Do not publish runtime projects containing `data/corpus_samples/*.json`.

Before GitHub publication, run audit and remove or retire test runtime data containing corpus samples.
