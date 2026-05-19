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
- Controlled Chutes real draft generation gate: `chutes_openai` can generate a writer draft only after `enable-real-provider` sets `settings.real_generation_enabled=true`, the project secret exists, and audit leak checks pass.
- One-command Chutes runbook `chutes-generate-once` that performs audit precheck, safe secret/config setup, explicit gate enable, real draft generation, gate disable, optional secret cleanup, and audit postcheck with metadata-only output.
- Minimal chapter workflow state at `data/chapters_workflow.json`, tracking planned/drafting/draft_ready/committed/blocked without prompt text, chapter content, or plaintext secrets.
- Draft Review / Quality Check skeleton using mock scorer output to create metadata-only review artifacts at `data/reviews/*.json` plus `data/reviews_index.json`.
- Chapter workflow can now move to `review_ready` with `latest_review_id`; review does not auto-commit, update Memory Bank/RAG/export, or store draft content/prompt/API keys.
- Manual review decision skeleton for `accepted`, `needs_revision`, and `blocked` decisions. Decisions update review/chapter metadata only and still do not commit or revise drafts automatically.
- Revision Request skeleton that can create metadata-only `requested` artifacts from `needs_revision` decisions only; it does not call LLMs, mutate drafts, create confirmed chapters, or update Memory Bank/RAG/export.
- Mock Revision Draft Service that creates a new draft candidate from a revision request using only the local mock reviser; it never overwrites the source draft and never auto-commits.
- MVP-5 quality hardening: secret writes no longer create plaintext `.bak` backups, revision draft generation now has an explicit mock-only reviser gate, and `audit-project` checks revision request/generated draft consistency.
- MVP-5.5 Revision Candidate Comparison read-model for listing and comparing source draft vs revision draft candidate metadata without returning content or making workflow decisions.
- MVP-6 Confirmed Context Update Queue that explicitly queues confirmed chapters for future manual Memory Bank/RAG/export work without updating those systems automatically.
- MVP-6.5 Context Update Preview artifacts that turn queue items into metadata-only plans for future formal context work without copying chapter text.
- MVP-7 Formal Context Policy schema with priority order: world building, character relationships, chapter summary, style memory, foreshadowing.
- MVP-7.5 Formal Context Extraction Plan artifacts that turn context previews into metadata-only category work plans without extracting text or writing Memory Bank/RAG/export.
- World-book overlap policy for world building context: when `world_book_enabled=true`, formal context plans reduce world-building Memory Bank weight by default to avoid duplicate tokens.
- MVP-8 Context Assembler dry-run that previews local context selection, estimated token budget, and selected/skipped metadata before any Provider call.
- MVP-8.5 Formal Context Task Queue that turns formal context plans into metadata-only manual tasks without applying Memory Bank/RAG/export updates.
- MVP-9 Memory Apply Preview that shows future Memory Bank candidate writes as metadata only, without changing `memory_bank.json`.
- MVP-9.5 Memory Bank Apply Commit Gate that explicitly commits preview metadata into placeholder Memory Bank entries with a pre-write checkpoint.
- MVP-10 Manual Memory Bank Text Fill/Edit that lets the operator explicitly fill placeholder text, creates a `pre_memory_text_update` checkpoint, rejects empty/oversized/secret-like text, and keeps default list/read/state output metadata-only.
- MVP-10.5 Memory Bank Item Lifecycle Controls that allow explicit enable/disable with checkpointing and make Context Assembler dry-run skip disabled memory items.
- MVP-11 Context Package Preview that assembles enabled manual Memory Bank text into a local preview, remains read-only, calls no Provider, and defaults to metadata-only output unless `include_text` is explicit.
- MVP-11.5 Prompt Render Dry-Run that combines an operator prompt with the context package in a no-write envelope, defaulting to redacted prompt/context output unless explicit include flags are used.
- MVP-12 Mock-Only Context-Aware Draft Generation that uses the prompt render envelope to create a draft through the local mock writer only, with no real Provider, no auto-commit, and no Memory Bank/RAG/export side effects.
- MVP-12.5 Audit checks for context-aware draft metadata consistency and prompt/context/secret leakage before real Providers are allowed to use assembled context.
- MVP-13 Corpus Profiler that reads an external `.txt` novel corpus in metadata-only mode, reports encoding/structure/chapter-length/dialogue/name-candidate statistics, and never copies source text into project files.
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
codex_docs\IMPORTANT_OPEN_ISSUES.md
```

Current重点难题:

```text
Memory Bank priority must be implemented by local Context Assembler logic before Provider calls; LLM APIs will not enforce it natively.
```
