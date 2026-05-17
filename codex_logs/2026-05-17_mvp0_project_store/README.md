# MVP-0 ProjectStore Implementation Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Implement the first MVP-0 storage kernel slice.

## Initial Scope

```text
pyproject.toml
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\storage.py
tests\test_project_store.py
```

## Requirements Covered

- Clean Python package skeleton.
- Safe project id validation.
- Project directory initialization.
- `data/config.json`.
- `data/secrets.local.json`.
- Atomic JSON write with same-directory temp file, fsync, and `os.replace`.
- `.bak` backup before overwriting existing JSON.
- Basic project lock using an exclusive lock file.
- Lock release uses `.trash` retirement instead of hard deletion.
- Tests use Python temporary directories.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 6 tests in 0.084s
OK
```

## Notes

The first sandboxed test command hit a Windows sandbox setup error. The same command was rerun with user-approved escalation and passed.
