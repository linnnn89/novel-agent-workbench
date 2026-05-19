# MVP-16.7 Style Check Policy Toggles

Date: 2026-05-19, Asia/Shanghai.

## Goal

Make Draft vs Self Style Check optional and record future UI placement.

The operator should be able to:

- disable style checks entirely,
- disable scene-mode calibration,
- hide ordinary hints and keep warnings only,
- choose scene mode per draft,
- keep auto revision request creation disabled.

## Files Changed

```text
src/novel_agent_workbench/config.py
src/novel_agent_workbench/self_style.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
tests/test_project_foundation.py
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

## Config

Stored at:

```text
config.context_policy.style_check_policy
```

Default:

```text
enabled=true
calibration_enabled=true
show_hints=true
default_scene_mode=general
severity_mode=hint_first
auto_create_revision_request=false
ui_placement.primary_surface=draft_review_side_panel
ui_placement.settings_surface=project_settings_writing_quality
ui_placement.modal_recommended=false
```

## CLI Overrides

```powershell
check-draft-style <project_id> <draft_id> --hide-hints
check-draft-style <project_id> <draft_id> --disable-calibration
check-draft-style <project_id> <draft_id> --disable-style-check
```

If disabled, no style check artifact is written.

## UI Decision

Future UI placement:

```text
Draft Review side panel
```

Project-level defaults:

```text
Project Settings > Writing Quality
```

Do not implement it as a blocking pop-up window. Style check is a review aid, not the main workflow.

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_self_style_baseline tests.test_project_foundation tests.test_application_service
```

Result:

```text
Ran 34 tests in 4.273s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 224 tests in 23.971s
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

The four warnings are the existing local runtime Chutes warnings. They are not blockers and this stage did not add new publication blockers.

## Next

When UI begins, expose style check controls in the draft review side panel and expose project defaults in Writing Quality settings.
