# Environment Setup BAT

Date: 2026-05-25, Asia/Shanghai.

## Change

Added root `SETUP_ENV.bat` as the reproducible Windows environment bootstrap script for fresh clones.

## Boundary

The script creates a local `.venv`, installs the project in editable mode, and installs desktop build tools (`pyinstaller`, `pillow`). It does not upload or restore runtime projects, local secrets, draft text, reference novels, `.venv`, `dist`, or `workspace_projects`.

## Verification

```powershell
cmd /c SETUP_ENV.bat --no-pause
```

Result: passed. Existing `.venv` was reused; `pip`, `setuptools`, and `wheel` were available/installed; the project installed in editable mode; `pyinstaller` and `pillow` were present.
