# MVP-0 Foundation Completion Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Complete the remaining MVP-0 backend foundation so the local project system can support MVP-1.

## Planned Scope

```text
config schema and migration
default project config structures
placeholder data files
secrets update/public-state safety boundary
storage/recovery edge checks
unit tests
documentation
```

## Design Decision

Use a small `config.py` module for schema version and default structures. Keep `storage.py` responsible for safe persistence, project initialization, migration orchestration, checkpoints, and public state assembly.

## Non-Scope

```text
frontend
LLM Provider calls
chapter generation
scoring/revision execution
DOCX export
reference project edits
```

## Verification

First verification command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 23 tests in 0.504s
OK
```

After tightening checkpoint-before-migration behavior:

```text
Ran 24 tests in 0.474s
OK
```

After recovery-boundary checks:

```text
Ran 26 tests in 0.521s
OK
```

## Implemented So Far

- `config.py` with schema version and default project structures.
- Default `config.json` with model role placeholders, workflow presets, and context policy.
- Default placeholder data files:
  - `planning_library.json`
  - `memory_bank.json`
  - `scoring_profile.json`
  - `revision_policy.json`
  - `export_settings.json`
- `ProjectStore.migrate_config()`.
- Migration checkpoint before writing migrated config/default files.
- `ProjectStore.update_secrets()`.
- `ProjectStore.public_state()` with masked secret output.
- Tests for migration idempotence, checkpoint behavior, and secret non-leakage.
- Tests for missing project metadata repair.
- Tests that checkpoint packages exclude backups and `.trash` files.

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp0_foundation_completion\README.md
src\novel_agent_workbench\config.py
src\novel_agent_workbench\storage.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_project_foundation.py
tests\test_project_store.py
```
