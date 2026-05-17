# MVP-0 Checkpoint Implementation Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Add recoverable checkpoint support around `ProjectStore`.

## Design Decision

Use checkpoint ZIP files with an embedded `checkpoint_manifest.json`.

Default behavior:

- Include project metadata and ordinary data files.
- Exclude `data/secrets.local.json` unless explicitly requested.
- Exclude lock files, backups, existing checkpoints, and `.trash` files.
- Restore by retiring overwritten files with `.trash` before writing restored files.
- Do not hard delete files during restore.

## Planned API

```python
create_checkpoint(label: str = "", include_secrets: bool = False) -> dict
restore_checkpoint(checkpoint_path: str | Path) -> dict
```

## Verification Plan

- Checkpoint zip is created with manifest.
- Manifest records file hashes and excludes secrets by default.
- Restore returns config to the checkpoint state.
- Restore retires overwritten file with `.trash`.
- Checkpoint path traversal entries are rejected.

## Verification Result

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 11 tests in 0.168s
OK
```

## Files Changed

```text
src\novel_agent_workbench\storage.py
tests\test_project_store.py
README.md
src\novel_agent_workbench\README.md
tests\README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp0_checkpoint\README.md
```

## Notes

No reference project files were modified. No UI or LLM code was added.
