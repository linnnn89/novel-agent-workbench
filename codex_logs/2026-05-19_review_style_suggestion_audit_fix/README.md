# Review: Style Suggestion Audit Fix

Date: 2026-05-19, Asia/Shanghai.

## Goal

Re-review the latest Style Suggestion Artifact work for bugs.

## Finding

Audit ordering had a boundary bug:

```text
audit_style_suggestions() was only called from audit_self_style_baselines().
```

If a damaged or manually polluted project had `data/style_suggestions/` but no `data/style_baselines/`, `audit_self_style_baselines()` returned early and skipped style suggestion scanning.

Normal product flow was not affected because style suggestions are created from style checks, and style checks require a baseline. The bug mattered for corrupted/orphan runtime data and prepublish hardening.

## Fix

Moved these calls to the top-level `audit_project()` flow:

```text
audit_draft_style_checks()
audit_style_suggestions()
```

They now run independently of whether `data/style_baselines/` exists.

## Tests Added

Added a regression test that creates an orphan `data/style_suggestions/bad.json` with a forbidden prompt field and no style baseline directory.

Expected audit finding:

```text
style_suggestion_text_stored
```

## Verification

Targeted:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline
```

Result:

```text
Ran 20 tests in 4.200s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 228 tests in 24.708s
OK
```

Leak scan:

```powershell
rg -n "<redacted secret and real-corpus sentinel patterns>" I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result:

```text
No matches.
```

Prepublish summary:

```json
{
  "blocker_count": 0,
  "finding_count": 4,
  "warning_count": 4
}
```

The four warnings are existing local Chutes runtime warnings. They are not blockers.

## Remaining Review Notes

No other blocking bug was found in this pass. A future hardening slice can make artifact indexes validate orphan paths across all artifact families, but that is larger than this focused fix.
