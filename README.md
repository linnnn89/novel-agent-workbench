# Novel Agent Workbench

Date: 2026-05-17, Asia/Shanghai.

This is the active implementation folder for the new local long-form novel writing workbench.

## Hard Boundary

```text
Do not edit the old downloaded source project in place.
```

Reference-only source:

```text
I:\AI-NOVEL\Tonade_DSv4-flash_100w_novel_agent-main
```

Active construction target:

```text
I:\AI-NOVEL\novel_agent_workbench
```

## Purpose

Build a stable, recoverable, local personal long-novel writing workbench with project-level isolation, safe local storage, Provider roles, Planning Library, draft revisions separated from confirmed chapters, optional scoring/revision workflows, and confirmed-only export.

## Initial Folder Map

```text
codex_docs/   durable architecture notes and handoff documents
codex_logs/   timestamped operation logs
src/          future application source code
tests/        future tests
```

## Current Status

MVP-0 first storage slice is implemented:

- Python package skeleton.
- `ProjectStore`.
- Atomic JSON write with `.bak` backups.
- Project initialization.
- Basic project lock.
- `config.json` and `secrets.local.json` separation.
- Checkpoint ZIP with embedded manifest.
- Reversible checkpoint restore using `.trash` for overwritten files.
- `ProjectRegistry` for creating, opening, and listing multiple projects.
- Default runtime routing to `workspace_projects/`.
- Unit tests.

Verification command:

```powershell
py -3.13 -m unittest discover -s tests
```
