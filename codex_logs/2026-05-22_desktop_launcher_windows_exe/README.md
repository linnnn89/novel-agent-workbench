# Desktop Launcher And Windows EXE

Date: 2026-05-22, Asia/Shanghai.

## Operation

Added a local desktop launcher UI, generated a Windows icon, and built a Windows executable.

## Files Changed

- `src/novel_agent_workbench/desktop_app.py`
- `src/novel_agent_workbench/assets/novel_agent_workbench_icon_1024.png`
- `src/novel_agent_workbench/assets/novel_agent_workbench.ico`
- `packaging/desktop_launcher.py`
- `scripts/generate_windows_icon.py`
- `scripts/build_windows_exe.ps1`
- `tests/test_desktop_app.py`
- `pyproject.toml`
- `.gitignore`
- `src/novel_agent_workbench/publication.py`
- `tests/test_publication.py`
- project documentation and logs

## Behavior

- The launcher lists local projects and can switch the projects root.
- It shows metadata-only project health, Provider safety state, smoke-test metadata, and upload readiness.
- It can create projects, configure Mock Writer, run prepublish checks, and open local folders.
- It does not call real Providers on startup and does not expose automatic real-LLM execution.
- The final real Provider safety-disabled state remains a manual production-use decision.

## Icon

Generated a blank manuscript-paper-and-pen icon.

The `.ico` includes:

```text
16, 20, 24, 32, 40, 48, 64, 128, 256 px
```

## Executable

Built:

```text
dist/NovelAgentWorkbench/NovelAgentWorkbench.exe
```

Launch smoke:

```text
EXE launch smoke: process started and closed
```

## Verification

```text
Ran 312 tests
OK
```

## Boundary

No old reference project was modified. No Provider or LLM was called. No key was cleared or rotated. No draft was created, overwritten, committed, or promoted. No Memory Bank, RAG, export, DOCX, auto-commit, or real file deletion was performed.
