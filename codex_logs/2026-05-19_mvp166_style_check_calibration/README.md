# MVP-16.6 Style Check Calibration

Date: 2026-05-19, Asia/Shanghai.

## Goal

Prevent Draft vs Self Style Check from becoming an over-strict average-forcing grade.

The user pointed out that chapters naturally vary:

- daily chapters may have more dialogue,
- exposition chapters may have less dialogue and longer paragraphs,
- battle and climax chapters may use shorter sentences and stronger punctuation,
- romance chapters may use more pauses or internal texture,
- transition chapters may be intentionally shorter.

## Files Changed

```text
src/novel_agent_workbench/self_style.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
tests/test_self_style_baseline.py
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

## Design

`check-draft-style` now accepts:

```text
general
daily
romance
battle
climax
exposition
transition
custom
```

P25-P75 deviations become `hint`. Only deviations beyond the scene-mode-calibrated wider boundary become `warning`.

Example behavior now covered by tests:

```text
An exposition chapter with low dialogue is a hint, not a warning.
```

## Safety Boundary

This remains local-only. It does not call Providers, store draft text, create revision requests, auto-revise drafts, auto-commit drafts, create confirmed chapters, update Memory Bank/RAG/export, or read external corpus files.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline tests.test_application_service
```

Result:

```text
Ran 23 tests in 3.783s
OK
```

Full regression is recorded after this log is written.

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 221 tests in 21.024s
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

The four warnings are existing local Chutes runtime project warnings. They are not source publication blockers.

## Next

Build a metadata-only style suggestion artifact from calibrated hints and warnings, but keep it separate from actual revision requests until the operator explicitly accepts it.
