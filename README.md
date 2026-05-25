# Novel Agent Workbench

This is the active implementation folder for the new local long-form novel writing workbench.

## Purpose

Build a stable, recoverable, local personal long-novel writing workbench with project-level isolation, safe local storage, Provider roles, Planning Library, draft revisions separated from confirmed chapters, optional scoring/revision workflows, and confirmed-only export.

## Provider Call Boundary

The product may call configured model providers when the user explicitly starts an action such as connection testing, draft generation, review, revision, or a future Memory Bank update. Those calls must use project-local provider settings, safe secret references, visible action labels, and audit metadata.

Codex development/QA runs are different: during implementation, tests, packaging, and documentation updates, Codex must not spend API credits or hit real LLM/API providers unless the user explicitly authorizes that specific run. Documentation that says "no real Provider call" for an implementation slice records what happened during that slice; it is not a product requirement that the software can never call models.

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
- Provider adapter registry with `mock`, OpenAI-compatible HTTP providers, local OpenAI-compatible endpoints, DeepSeek, and Chutes.
- Project secret resolver contract for `project_secret.<name>` references stored only in `data/secrets.local.json`.
- Backend-only `provider-status` / `list-provider-adapters` CLI checks with no network calls.
- Provider-aware audit checks for raw keys, disabled adapters, missing secret refs, and missing local secrets.
- Safe Provider config preflight commands for writing disabled adapter configs and project-local secrets without printing plaintext keys.
- No-network Provider dry-run command for HTTP providers, returning safe request summaries only.
- Chutes OpenAI-compatible adapter id `chutes_openai` for explicit user-triggered connection tests and draft generation.
- Explicit `provider-real-test` command for one approved Chutes connection test, separate from draft generation and without returning response text.
- Chutes real draft generation now depends on the selected writer Provider config, project secret or local endpoint config, and audit leak checks; there is no separate network enable gate.
- One-command Chutes runbook `chutes-generate-once` that performs audit precheck, safe secret/config setup, real draft generation, optional secret cleanup, and audit postcheck with metadata-only output.
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
- MVP-10 Manual Memory Bank Text Fill/Edit that lets the operator explicitly fill placeholder text, creates a `pre_memory_text_update` checkpoint, rejects empty/secret-like text, stores a visible target token value as prompt guidance, and keeps default list/read/state output metadata-only.
- MVP-10.5 Memory Bank Item Lifecycle Controls that allow explicit enable/disable with checkpointing and make Context Assembler dry-run skip disabled memory items.
- MVP-11 Context Package Preview that assembles enabled manual Memory Bank text into a local preview, remains read-only, calls no Provider, and defaults to metadata-only output unless `include_text` is explicit.
- MVP-11.5 Prompt Render Dry-Run that combines an operator prompt with the context package in a no-write envelope, defaulting to redacted prompt/context output unless explicit include flags are used.
- MVP-12 Mock-Only Context-Aware Draft Generation that uses the prompt render envelope to create a draft through the local mock writer only, with no real Provider, no auto-commit, and no Memory Bank/RAG/export side effects.
- MVP-12.5 Audit checks for context-aware draft metadata consistency and prompt/context/secret leakage before real Providers are allowed to use assembled context.
- MVP-13 Corpus Profiler that reads an external `.txt` novel corpus in metadata-only mode, reports encoding/structure/chapter-length/dialogue/name-candidate statistics, and never copies source text into project files.
- MVP-13.5 Corpus Profile Artifacts that explicitly save conservative project-local profile metadata while excluding source text, external source paths, and candidate-name text by default.
- MVP-14 Corpus Boundary Indexes that explicitly save no-text chapter line/character offsets for future manual import planning while excluding heading text, excerpts, and source paths.
- MVP-15 Corpus Sample Quarantine that can explicitly save bounded real-text samples for local testing only, marks them as `publish_blocker`, and keeps default reads/state/list output text-free.
- MVP-15.5 Prepublish Readiness Check that scans the publishable source tree plus runtime projects for secrets, environment files, corpus samples, and audit blockers before GitHub publication.
- MVP-16 Self Style Baseline that creates local metadata-only style statistics from the project's own confirmed chapters, with no external corpus, no Provider call, and no stored chapter text.
- MVP-16.5 Draft vs Self Style Check that compares one draft to a self-style baseline using local statistics only, without storing draft text or triggering revision/commit.
- MVP-16.6 Style Check Calibration that treats draft style checks as scene-mode-aware hints rather than strict pass/fail grading.
- MVP-16.7 Style Check Policy Toggles that make style checks, calibration, and hint display configurable, with future UI placement recorded as the draft review side panel.
- MVP-16.8 Style Suggestion Artifact that converts a style check into metadata-only manual suggestions, without modifying drafts or creating revision requests.
- MVP-16.9 Manual Suggestion Decision that records explicit operator decisions on style suggestions without applying edits automatically.
- MVP-17 Manual Rewrite Workspace Skeleton that turns `needs_manual_rewrite` style suggestions into metadata-only human rewrite tasks, without editing drafts or generating candidates.
- MVP-17.5 Manual Rewrite Draft Submission that lets a human rewrite task explicitly create a new draft candidate without overwriting old drafts or auto-committing.
- MVP-18 Manual Rewrite Candidate Comparison / Selection Gate that compares source vs submitted manual draft candidates with metadata-only structural metrics and explicit `selected_for_review` / `rejected` / `needs_more_manual_work` decisions.
- MVP-18.5 Review Handoff From Selected Manual Rewrite Candidate that creates a metadata-only pending-review handoff only after `selected_for_review`, without auto-review, Provider calls, auto-commit, or Memory Bank/RAG/export side effects.
- MVP-19 Planning Library and final prompt assembly safety that stores manual planning references, tracks active ids, injects only active/enabled planning sections into context package and prompt render dry-runs, and keeps default list/read/state/package outputs metadata-only.
- MVP-19.5 Review-Draft Guard for Manual Rewrite Candidates that requires `selected_for_review` comparison or `pending_review` handoff before a submitted manual rewrite draft can be reviewed.
- MVP-20 Final Provider Assembly Gate that stores metadata-only prompt/context/provider hashes, requires explicit approval before any future real context-aware Provider path, and still keeps real context-aware generation disabled in this phase.
- MVP-20.5 Review Handoff Consumption Metadata that marks a `pending_review` handoff as `review_created` after its selected draft is successfully reviewed, without changing draft bodies or triggering commit/context side effects.
- MVP-21 Accepted Review Commit Gate that requires an `accepted` review for the same draft before confirmed-chapter promotion, while failed gate checks do not block the chapter or mutate workflow state.
- MVP-22 Final Provider Runbook Plan that derives a metadata-only operator runbook from an approved final assembly gate, records provider/model/digest/token checklist metadata, and stops at `pending_operator_authorization` without calling a real LLM, writing drafts, or updating Memory Bank/RAG/export.
- MVP-23 Final Provider Authorization Checkpoint that records a metadata-only authorization from a pending runbook, creates a no-secrets pre-authorization checkpoint summary, and still does not enable or call a real Provider.
- MVP-24 Final Provider Execution Preflight Verifier that checks the gate/runbook/authorization/current-provider chain and records passed or blocked metadata without enabling/calling a real Provider or writing drafts.
- MVP-25 Final Provider Execution Stub / Abort Gate that created a no-network execution rehearsal after a passed preflight and deliberately fail-closed with `aborted_real_llm_disabled`, without enabling/calling Providers or writing drafts.
- MVP-26 Final Provider Real Execution Readiness that checks the aborted attempt against current Chutes writer config, project-secret presence, and manual authorization requirements, while still not reading secret values, enabling Providers, calling LLMs, or writing drafts.
- MVP-27 Final Provider Real Execution Path that can, after gate digest match, call the writer Provider and write one new draft. Tests patch the Chutes client; no real network call was made during implementation.
- MVP-27.1 Real Execution Hardening that strips shell newlines from `--prompt-stdin` before gate digest comparison and adds a read-only `postcheck-final-provider-real-execution` verifier for draft creation, no confirmed chapter, and metadata-only safety flags.
- MVP-27.2 Reasoning Leak Review Guard that detects `<think>` reasoning markup during `review-draft`, skips scorer calls, creates a metadata-only local-guard review, and automatically marks the draft as `needs_revision`.
- MVP-27.3 Provider Response Sanitizer that removes `<think>...</think>` reasoning blocks from Provider output before draft content is saved, while recording only sanitizer metadata.
- MVP-27.4 Sample-Only Commit Blocker that rejects `accepted` reviews with `reason_code=smoke_test_only` at commit time, so live smoke-test drafts can be retained as evidence without becoming confirmed chapters.
- MVP-28 Provider Live Smoke Test Harness that persists metadata-only Provider connectivity checks when the user starts them, never writes drafts or confirmed chapters, and classifies all smoke outputs as sample-only/non-committable.
- MVP-29 Provider Smoke Test Audit Gate that makes `audit-project` and `prepublish-check` validate smoke-test metadata, safety flags, no prompt/response/secret text storage, and no draft/confirmed-chapter linkage.
- MVP-30 Provider Config Snapshot / Drift Audit that records safe Provider config snapshots in new smoke-test artifacts and warns when the latest passed smoke-test config drifts from current role config.
- MVP-31 Runtime Project Health Summary and Upload Ignore Guard that exposes metadata-only project health, wraps audit/prepublish upload readiness, and expands `.gitignore`/prepublish coverage for build and coverage artifacts.
- MVP-32 Desktop Launcher and Windows EXE Packaging that adds a Tkinter desktop shell, Win11-compatible multi-size manuscript-paper-and-pen icon assets, and a PyInstaller build script for `NovelAgentWorkbench.exe`.
- Unit tests.

Verification command:

```powershell
py -3.13 -m unittest discover -s tests
```

Latest recorded result:

```text
Ran 312 tests
OK
```

Windows desktop launcher:

```powershell
I:\AI-NOVEL\novel_agent_workbench\dist\NovelAgentWorkbench\NovelAgentWorkbench.exe
```

Build command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File I:\AI-NOVEL\novel_agent_workbench\scripts\build_windows_exe.ps1
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

## Fresh Machine Environment Setup

The repository does not upload `.venv/`, runtime projects, local secrets, or build output. On a new Windows machine, run:

```cmd
SETUP_ENV.bat
```

The script creates `.venv` with Python 3.13, installs this project in editable mode, and installs desktop build tools (`pyinstaller`, `pillow`). It does not create API keys and does not copy any runtime writing projects.

For non-interactive verification:

```cmd
SETUP_ENV.bat --no-pause
```

Current重点难题:

```text
The final-provider path now has gate -> runbook -> authorization -> preflight -> fail-closed execution stub -> real execution readiness -> explicit real execution -> read-only postcheck coverage. Live Chutes runs have proven the execution and sanitizer chain. Smoke-test drafts are retained as evidence only and must not be promoted to confirmed chapters. Upload readiness is guarded by `.gitignore`, `prepublish-check`, and `project-health`. The desktop launcher is intentionally local-first: it must not call models on startup or in hidden background flows, but it may expose clear user-triggered model actions.
```
