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
- Project config schema defaults and migration.
- Placeholder files for Planning Library, Memory Bank, scoring/revision policy, and export settings.
- Public state with masked secrets only.
- Provider role config objects for writer/scorer/reviser.
- Fake provider connection test with no network calls.
- Provider interface objects and a deterministic local Mock Provider.
- Provider call audit log at `data/provider_call_log.json`, with prompt/secrets excluded.
- Draft Generation Service skeleton that writes mock writer output to draft artifacts only.
- Explicit draft commit boundary that promotes drafts to confirmed chapter artifacts only when called.
- Safe project state summary for future UI use, excluding prompt text, chapter content, and plaintext secrets.
- Minimal backend application service facade for project creation, state, drafts, and explicit commit.
- Backend-only CLI smoke runner for the project -> mock draft -> optional commit loop.
- Unit tests.

Verification command:

```powershell
py -3.13 -m unittest discover -s tests
```

Backend-only CLI smoke example:

```powershell
$env:PYTHONPATH="I:\AI-NOVEL\novel_agent_workbench\src"
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
```
