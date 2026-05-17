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

## Current Backend Status

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
- Backend-only safety audit for config, logs, checkpoints, and public state.
- Quality hardening for safe ASCII `chapter_id` values and half-commit audit detection.
- Provider adapter registry with `mock` enabled and `openai_compatible` / `deepseek` reserved but disabled.
- Project secret resolver contract for `project_secret.<name>` references stored only in `data/secrets.local.json`.
- Backend-only `provider-status` / `list-provider-adapters` CLI checks with no network calls.
- Provider-aware audit checks for raw keys, disabled adapters, missing secret refs, and missing local secrets.
- Safe Provider config preflight commands for writing disabled adapter configs and project-local secrets without printing plaintext keys.
- No-network Provider dry-run command for disabled `deepseek` / `openai_compatible` adapters, returning safe request summaries only.
- Chutes OpenAI-compatible adapter id `chutes_openai` reserved as disabled/no-network dry-run only.
- Explicit `provider-real-test` command for one approved Chutes connection test, separate from draft generation and without returning response text.
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

Operator docs:

```text
codex_docs\CLI_QUICKSTART.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
```
