# MVP-16 Self Style Baseline

Date: 2026-05-19, Asia/Shanghai.

## Goal

Create a local style baseline from the project's own confirmed chapters.

This corrects the earlier conceptual ambiguity:

```text
Primary product path: own confirmed chapters -> local style statistics.
External TXT novels: parser/quarantine testing only unless explicitly authorized separately.
```

## Files Changed

```text
src/novel_agent_workbench/self_style.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/audit.py
src/novel_agent_workbench/__init__.py
tests/test_self_style_baseline.py
tests/test_application_service.py
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

## Storage

```text
data/style_baselines/*.json
data/style_baselines_index.json
```

Artifacts store:

- included confirmed chapter ids and titles,
- chapter length distributions,
- paragraph and sentence statistics,
- dialogue-line ratio,
- punctuation frequency.

Artifacts do not store confirmed chapter text, prompt text, external corpus text, source paths, Provider raw responses, or plaintext secrets.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> create-self-style-baseline <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-self-style-baselines <project_id>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> read-self-style-baseline <project_id> <baseline_id>
```

## Safety Boundary

The service reads confirmed chapter text in memory only to compute metrics. It does not read external corpus files, call Providers, create drafts, create confirmed chapters, update Memory Bank, update RAG, create exports, or write prompt logs.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline tests.test_application_service
```

Result:

```text
Ran 16 tests in 1.664s
OK
```

Full regression is recorded after this log is written.

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 214 tests in 20.982s
OK
```

Leak scan:

```text
Known Chutes key fragments and known real-corpus sample snippets: no matches in novel_agent_workbench or PROJECT_INDEX.md.
```

Prepublish summary:

```text
blocker_count=0
warning_count=4
finding_count=4
```

The four warnings are the existing local Chutes runtime project warnings already documented in MVP-15.5; they are not source publication blockers.

## Next

Build a local draft-vs-self-style check that compares a draft's metadata statistics to the latest baseline without calling Providers.
