# MVP-16.9 Manual Suggestion Decision

Date: 2026-05-19, Asia/Shanghai.

## Goal

Record explicit operator decisions on style suggestion artifacts.

Supported decisions:

```text
accepted
ignored
needs_manual_rewrite
```

This is workflow metadata only. It does not apply edits, create revision requests, call Providers, auto-revise, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## Files Changed

```text
src/novel_agent_workbench/self_style.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/project_state.py
src/novel_agent_workbench/__init__.py
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

## Storage

Manual decisions update only:

```text
data/style_suggestions/*.json
data/style_suggestions_index.json
```

Decision shape:

```json
{
  "status": "ignored",
  "reason_code": "scene_intentional",
  "decided_at": "timestamp"
}
```

`reason_code` is a short ASCII code, not free-form prose. This avoids storing prompt text, generated content, or private notes.

## CLI

```powershell
decide-style-suggestion <project_id> <suggestion_id> --decision ignored --reason-code scene_intentional
```

## Safety Boundary

Manual style suggestion decisions must not:

- call Providers,
- modify draft artifacts,
- create revision requests,
- auto-revise,
- auto-commit,
- create confirmed chapters,
- update Memory Bank,
- update RAG,
- create exports.

Duplicate decisions are rejected.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline
```

Result:

```text
Ran 23 tests in 5.269s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 231 tests in 23.728s
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

Patch check:

```powershell
git -c safe.directory=I:/AI-NOVEL/novel_agent_workbench diff --check
```

Result:

```text
OK. Git reported line-ending conversion warnings only.
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

## Next

Future UI can expose style suggestion decisions as explicit buttons inside the draft review side panel. `needs_manual_rewrite` should remain a human marker until a later explicit rewrite workflow is designed.
