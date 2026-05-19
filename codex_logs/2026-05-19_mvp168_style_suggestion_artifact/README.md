# MVP-16.8 Style Suggestion Artifact

Date: 2026-05-19, Asia/Shanghai.

## Goal

Convert a draft style check into a manual suggestion artifact.

This is a review aid only. It does not rewrite drafts, create revision requests, commit chapters, call Providers, or update Memory Bank/RAG/export.

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
data/style_suggestions/*.json
data/style_suggestions_index.json
```

Artifacts include:

```text
suggestion_id
check_id
draft metadata
style_check metadata
metric-level suggestions
safety flags
```

Artifacts must not include draft text, prompt text, generated content, confirmed chapter text, external corpus text, raw Provider responses, or plaintext secrets.

## CLI

```powershell
create-style-suggestion <project_id> <check_id>
list-style-suggestions <project_id>
read-style-suggestion <project_id> <suggestion_id>
```

## Safety Boundary

Style suggestions are generated from existing style-check metadata only.

They must not:

- call Providers,
- modify draft artifacts,
- create revision requests,
- auto-revise,
- auto-commit,
- create confirmed chapters,
- update Memory Bank,
- update RAG,
- create exports.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline tests.test_application_service
```

Result:

```text
Ran 29 tests in 5.635s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 227 tests in 23.496s
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

During this stage, the previous MVP-16.7 log was also redacted because it had stored the literal sentinel scan command. This was documentation-only cleanup and did not touch runtime project data.

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

Future UI can show style suggestions under the draft review side panel as a collapsible suggestion list. Applying any suggestion should remain a separate explicit operator action.
