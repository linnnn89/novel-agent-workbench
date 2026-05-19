# Project Charter

Date: 2026-05-17, Asia/Shanghai.

## Identity

`novel_agent_workbench` is a new implementation project. It uses the downloaded Tonade source only as reference material.

## Primary Goal

Build a local, personal, recoverable long-form novel writing workbench that can help finish a full-length novel without uncontrolled context pollution, project contamination, or brittle automation.

## Non-Negotiable Rules

1. Do not modify `I:\AI-NOVEL\Tonade_DSv4-flash_100w_novel_agent-main` in place.
2. Do not delete user data or generated work silently.
3. During early MVP work, do not perform real file deletion. Retire files by renaming with the `.trash` suffix.
4. Write Markdown after every meaningful change.
5. Keep business logic in backend modules, not frontend JavaScript.
6. Keep draft revisions separate from confirmed chapters.
7. Only confirmed chapters may update formal context, Memory Bank, RAG, game state, and export.
8. API keys must not be logged, exported, returned in app state, or stored in general config.
9. Cross-project import means copy with new ids, never runtime dynamic reference.
10. MVP work should be phased; do not jump into advanced World Book, Prompt Inspector, or browser automation before safety and context foundations are stable.

## Reference Project Usage

Allowed:

- read architecture,
- inspect behavior,
- run reference tests when useful,
- copy small code ideas after review,
- compare UI flow and data files.

Not allowed:

- edit files in the reference project,
- run destructive cleanup in it,
- migrate it in place,
- treat its `app_projects` as the active data store for the new build.

## First MVP Direction

MVP-0 should establish safe JSON storage, backup/checkpoint conventions, project lock, local secrets boundary, basic app/project layout, and tests proving safety behavior.

First engineering slice:

```text
ProjectStore + atomic JSON persistence + backup + project lock + secrets/config separation + unit tests
```

Second engineering slice:

```text
ProjectStore checkpoint ZIP + manifest + reversible restore
```

Third engineering slice:

```text
ProjectRegistry + default workspace_projects routing + registry.json + unit tests
```

Foundation completion slice:

```text
config schema/migration + default project structures + secrets public-state boundary + unit tests
```

MVP-1 first slice:

```text
Provider role config objects + project_secret.* validation + fake connection tests only
```

MVP-1 provider interface slice:

```text
ProviderRequest/ProviderResponse + ProviderClient + deterministic Mock Provider + safe provider call log
```

Do not add real Provider HTTP calls until the mock-only interface and audit boundary are stable.

MVP-1 draft generation service slice:

```text
Mock writer output -> draft artifact only; no confirmed chapters, Memory Bank, RAG, or export side effects.
```

MVP-1 draft commit boundary slice:

```text
Draft review/status + explicit draft commit -> confirmed chapter artifact/index + safe project state summary.
```

Confirmed chapters are now the only stored candidate for future formal context. Memory Bank, RAG, and export auto-updates remain intentionally unimplemented.

MVP-1 application service facade slice:

```text
Stable backend facade for project creation, safe state, mock draft generation, draft read/list, explicit commit, and confirmed chapter read/list.
```

This is an application boundary for future CLI/HTTP/UI. It must stay thin and delegate to storage, provider, draft, and state modules.

MVP-1 CLI smoke runner slice:

```text
Backend-only command runner for project creation, mock writer configuration, draft generation, state inspection, and explicit commit.
```

This is not a frontend and not an HTTP API. It is a local verification and operator convenience layer over `WorkbenchApplicationService`.

MVP-1 operable backend workbench slice:

```text
CLI Quickstart + Application Service contract + read-only safety audit + provider preflight boundary.
```

Real Provider integration must not start until the mock project path and `audit-project` pass.

MVP-1 quality hardening slice:

```text
safe ASCII chapter_id validation + read-only audit + half-commit consistency checks.
```

Audit must not write project files. It should detect obvious confirmed chapter inconsistencies before later UI or real Provider work.

MVP-2 provider adapter skeleton slice:

```text
Provider adapter registry + project_secret resolver + disabled real-provider placeholders + provider-status CLI + Provider-aware audit.
```

`mock` remains the only enabled adapter. `openai_compatible` and `deepseek` are reserved but disabled and must not send network requests. Real Provider work requires a passing `audit-project` gate and an explicit later decision.

MVP-2 provider config preflight slice:

```text
safe Provider config write path + project-local secret write path + masked CLI/status output.
```

This allows rehearsal of real Provider setup while adapters remain disabled. It must not turn on HTTP calls or allow generation through real Provider ids.

MVP-2 provider dry-run adapter slice:

```text
disabled real-provider dry-run adapter + OpenAI-compatible safe request summary + provider-dry-run CLI.
```

Dry-run may expose only safe counts and config metadata. It must not expose prompt text, request bodies, API keys, or raw responses, and it must not write preflight logs by default.

MVP-2 Chutes provider preflight slice:

```text
reserved chutes_openai adapter + Chutes OpenAI-compatible base URL/model dry-run coverage.
```

Chutes remains disabled and no-network until the user explicitly authorizes a real connection test.

MVP-2 Chutes explicit real test slice:

```text
provider-real-test for chutes_openai + safe metadata-only result + no draft/confirmed/context side effects.
```

This path may send a real request only after explicit user approval. It must remain separate from normal draft generation.

MVP-2 Chutes controlled real generation gate slice:

```text
enable-real-provider / disable-real-provider + chutes_openai writer-only real draft generation + audit leak gate.
```

`chutes_openai` remains disabled in the adapter registry and is not generally enabled. Normal draft generation may use it only when the writer role is configured for Chutes, `settings.real_generation_enabled=true`, the local project secret resolves, and audit has no key/prompt/content leak findings. Real output is written only as a draft artifact and must not auto-commit or update Memory Bank, RAG, or exports.

MVP-2.5 real Provider runbook slice:

```text
chutes-generate-once + audit precheck/postcheck + automatic gate disable + optional secret cleanup.
```

The runbook is the preferred operator path for real Chutes tests. It requires explicit `--allow-network`, returns metadata only, and keeps generated content confined to draft artifacts.

MVP-3 chapter workflow slice:

```text
chapters_workflow.json + planned/drafting/draft_ready/committed/blocked + chapter CLI.
```

Chapter workflow state is metadata-only. It may reference draft ids and confirmed chapter ids, but it must not store prompt text, generated content, raw provider responses, or plaintext secrets.

MVP-3.5 draft review slice:

```text
reviews/*.json + reviews_index.json + mock scorer review + review_ready workflow state.
```

Draft Review / Quality Check is backend-only and metadata-only. It may record scores, issues, recommendation, Provider/model/usage, draft id, and chapter id. It must not store draft content, original prompts, raw Provider responses, or plaintext secrets. It must not auto-commit, auto-revise, update Memory Bank, update RAG, create exports, create DOCX, or enable new real Providers.

MVP-4 manual review decision slice:

```text
decide-review + accepted/needs_revision/blocked metadata + chapter workflow update.
```

Manual review decisions are not commits and not automatic revisions. They may update review/chapter metadata only. Decision inputs are fixed enums plus safe `reason_code`; free-text notes remain intentionally excluded to avoid prompt/content leakage in metadata surfaces.

MVP-4.5 revision request slice:

```text
revision_requests/*.json + revision_requests_index.json + revision_requested workflow state.
```

Revision requests may be created only from `needs_revision` review decisions. They are metadata-only and must not call LLMs, mutate drafts, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or store prompt text, draft content, raw Provider responses, plaintext secrets, or free-text notes.

MVP-5 mock revision draft slice:

```text
generate-revision-draft + mock reviser output -> new draft candidate.
```

Mock revision draft generation may create a new draft artifact and draft index entry only. It must preserve the source draft unchanged, keep explicit commit as the only confirmed-chapter path, use only the local mock Provider, and avoid Memory Bank/RAG/export/DOCX side effects.

MVP-5 quality hardening slice:

```text
secret no-backup writes + explicit mock-only revision gate + revision consistency audit.
```

Secret rotation must not leave old plaintext values in `.bak` files. Revision draft generation remains mock-only even if future real Provider configs are present. Audit should catch missing or mismatched revision request/generated draft artifacts before later UI or automation layers depend on them.

MVP-5.5 revision candidate comparison slice:

```text
list-revision-candidates + compare-revision-candidate metadata read-model.
```

The comparison surface is read-only. It may compute length/count deltas and validate links between source draft, review, revision request, and candidate draft. It must not return draft content, prompt text, or plaintext secrets; it must not choose, overwrite, auto-commit, or mutate Memory Bank/RAG/export.

MVP-6 confirmed context update queue slice:

```text
enqueue-context-updates + context_update_queue.json + manual status marking.
```

Only confirmed chapters may enter this queue. The queue is a metadata handoff layer for future Memory Bank/RAG/export updates; it is not the update itself. It must not store chapter content, prompt text, or plaintext secrets, and it must not automatically mutate Memory Bank, RAG, exports, drafts, or confirmed chapters.

MVP-6.5 context update preview slice:

```text
create-context-preview + context_update_previews/*.json + metadata-only target plan.
```

Preview artifacts may record target placeholders, text statistics, and safety flags. They must not copy chapter text, prompt text, raw Provider responses, or plaintext secrets. They must not mutate Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers.

MVP-7 formal context policy slice:

```text
formal_context_policy priority schema: world_building > character_relationships > chapter_summary > style_memory > foreshadowing.
```

This is a policy schema only. It must guide future context previews and extraction planning, but it must not perform extraction, call Providers, or mutate Memory Bank/RAG/export automatically.

MVP-7.5 formal context plan slice:

```text
create-formal-context-plan + formal_context_plans/*.json + category-level manual extraction plan.
```

Plans are metadata-only artifacts generated from context previews. They may record category ids, priority order, text statistics, and safety flags. They must not copy chapter text, prompt text, raw Provider responses, or plaintext secrets. They must not mutate Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers.

World-book overlap policy:

```text
world_building memory_weight=1.0 normally, reduced to 0.35 when world_book_enabled=true.
```

This prevents future world book and Memory Bank context from duplicating stable setting facts at full token weight. It is an option and recommendation surface only in this phase.

Important open issue:

```text
Memory Bank priority is not an LLM API-native feature. It must be implemented in a local Context Assembler before ProviderRequest construction.
```

Track details in:

```text
codex_docs/IMPORTANT_OPEN_ISSUES.md
```

MVP-8 context assembler dry-run slice:

```text
context-assembly-dry-run + local candidate ranking preview + metadata-only token budget estimate.
```

This is a diagnostic surface for future Provider prompt assembly. It may read formal context plans and Memory Bank item metadata, but it must not return prompt text, chapter text, Memory Bank text, or plaintext secrets. It must not call Providers or write project data.

MVP-8.5 formal context task queue slice:

```text
enqueue-formal-context-tasks + formal_context_task_queue.json + manual status marking.
```

This queue turns formal context plans into per-category manual tasks. It must not extract text, write Memory Bank, write world book, update RAG/export, mutate drafts/confirmed chapters, or call Providers.

MVP-9 memory apply preview slice:

```text
create-memory-apply-preview + memory_apply_previews/*.json + candidate metadata only.
```

This preview shows what might later be written to Memory Bank. It must not write `memory_bank.json`, copy chapter text, copy prompt text, copy Memory Bank text, write world book, update RAG/export, mutate drafts/confirmed chapters, or call Providers.

MVP-9.5 Memory Bank apply commit gate slice:

```text
commit-memory-apply-preview + pre_memory_apply checkpoint + placeholder Memory Bank entries.
```

This is the first allowed Memory Bank write path. It must be explicit and reversible. It may write only structured placeholder entries with empty `text` and `manual_text_required` status. It must not extract chapter text, copy prompt text, copy existing Memory Bank text, write world book, update RAG/export, mutate drafts/confirmed chapters, or call Providers.

MVP-10 manual Memory Bank text fill/edit slice:

```text
set-memory-text + pre_memory_text_update checkpoint + explicit include-text read.
```

This is the first allowed Memory Bank text write path. Text must be manually supplied, bounded, secret-scanned, checkpointed, and returned only through an explicit read flag. It must not auto-extract from chapters, call Providers, write world book, update RAG/export, mutate drafts/confirmed chapters, or auto-assemble prompt context.

MVP-10.5 Memory Bank item lifecycle slice:

```text
disable-memory-item / enable-memory-item + pre_memory_lifecycle_update checkpoint.
```

Memory Bank items may be disabled without deleting or rewriting their text. Disabled items remain recoverable on disk and must be skipped by Context Assembler dry-run. This is metadata-only lifecycle control; it must not call Providers, update world book, update RAG/export, mutate drafts/confirmed chapters, or render final prompts.

MVP-11 context package preview slice:

```text
context-package-preview + enabled manual Memory Bank text selection + explicit include-text review.
```

This is a read-only preview layer before final prompt rendering. It may select enabled, ready, manual Memory Bank items and estimate token usage. Default output must be metadata-only; manual text may appear only with an explicit include-text option. It must not write artifacts, call Providers, read chapter content, write prompt logs, update world book, update RAG/export, mutate drafts/confirmed chapters, or generate text.

MVP-11.5 prompt render dry-run slice:

```text
prompt-render-dry-run + redacted message envelope + explicit prompt/context text flags.
```

This is a no-write envelope preview before Provider calls. It may combine an operator prompt, optional system prompt, and selected context package metadata. Default output must redact prompt text and context text. Text may appear only with explicit include flags. It must not write prompt logs, call Providers, create drafts, read chapter content, update world book, update RAG/export, or mutate confirmed chapters.

MVP-12 mock-only context-aware draft slice:

```text
generate-context-draft + prompt render envelope + local mock writer only.
```

This is the first draft generation path that consumes assembled manual Memory Bank context. It must remain mock-only, metadata-safe, and explicit. It may create a draft artifact with generated mock content and safe context-generation summary. It must not call real Providers, auto-commit, write prompt logs, store operator prompt or Memory Bank text in metadata, update world book, update RAG/export, create DOCX, or mutate confirmed chapters.

MVP-12.5 context generation audit slice:

```text
audit-project + context_generation metadata checks + draft index consistency.
```

Audit must validate context-aware draft metadata before any real Provider uses assembled context. It should check metadata, indexes, and leak-prone fields without treating normal draft body content as an error. It must remain read-only.

MVP-13 corpus profiler slice:

```text
profile-corpus + read-only metadata statistics for external txt corpora.
```

Corpus profiling may inspect external `.txt` files and return encoding, structure, chapter-length, dialogue proxy, and rough name-candidate statistics. It must not copy source text into the project, write corpus artifacts, call Providers, generate drafts, update Memory Bank/RAG/export, or create confirmed chapters. Name candidates are heuristic only and require later human or algorithmic validation before any character database is built.

MVP-13.5 corpus profile artifact slice:

```text
save-corpus-profile + data/corpus_profiles/*.json + conservative metadata persistence.
```

Saving a corpus profile must be explicit. Persistent artifacts may store file name, size, SHA-256, encoding, and statistics, but not external source paths, source text, chapter heading text, dialogue excerpts, or candidate-name text. This is still not a corpus importer and must not call Providers or update drafts/confirmed chapters/Memory Bank/RAG/export.

MVP-14 corpus boundary index slice:

```text
save-corpus-boundaries + data/corpus_boundaries/*.json + no-text line/character offsets.
```

Boundary indexes may store chapter ordinals, heading line numbers, body line ranges, body character ranges, and body character counts. They must not store source text, heading text, excerpts, candidate names, or external source paths. This is still not import and must not call Providers or update drafts/confirmed chapters/Memory Bank/RAG/export.

MVP-15 corpus sample quarantine slice:

```text
create-corpus-sample + data/corpus_samples/*.json + publish_blocker test-only text.
```

Samples may contain bounded real text only during local testing. They must be explicit, bounded, linked to a matching source hash, marked `test_only` and `publish_blocker`, hidden from default state/list/read outputs, and flagged by audit until removed from publishable runtime state. They must not call Providers or update drafts/confirmed chapters/Memory Bank/RAG/export.

MVP-15.5 prepublish readiness slice:

```text
prepublish-check + source tree scan + runtime project audit blocker scan.
```

Before any GitHub publication, the operator must be able to run one read-only check that catches publishable secrets, `.env` files, missing required ignore patterns, corpus sample artifacts, and high-risk audit leaks. Runtime Provider disabled/missing-secret findings can be warnings when they do not leak sensitive content. The check must not delete files, mutate runtime projects, call Providers, read external corpus text, or print sample text/secrets.

MVP-16 self style baseline slice:

```text
create-self-style-baseline + data/style_baselines/*.json + own confirmed chapter statistics.
```

Self style baselines must use only the project's confirmed chapters. They may read confirmed chapter text in memory to calculate statistics, but persistent artifacts must contain only numeric/statistical metadata. They must not store chapter text, prompt text, external corpus text, source paths, raw Provider responses, or plaintext secrets. They must not call Providers or update drafts/confirmed chapters/Memory Bank/RAG/export.

MVP-16.5 draft vs self style check slice:

```text
check-draft-style + data/style_checks/*.json + local baseline comparison.
```

Draft style checks must compare one draft to a self-style baseline using local statistics only. They may read draft text in memory to calculate metrics, but persistent artifacts must contain only numeric checks and issue metadata. They must not store draft text, prompt text, generated content, confirmed chapter text, external corpus text, raw Provider responses, or plaintext secrets. They must not call Providers, create revision requests, auto-revise, auto-commit, or update Memory Bank/RAG/export.

MVP-16.6 style check calibration slice:

```text
scene_mode + hint/warning calibration + no strict average forcing.
```

Draft style checks must support chapter modes so daily, romance, battle, climax, exposition, and transition chapters can intentionally deviate from the global average. Ordinary deviations should become hints. Only calibrated extreme deviations should become warnings. This calibration must not call Providers, mutate drafts, create revision requests, auto-commit, or update Memory Bank/RAG/export.

MVP-16.7 style check policy toggle slice:

```text
context_policy.style_check_policy + optional style checks + draft review side panel placement.
```

Style checks, calibration, and hint display must be configurable. If style checks are disabled, checking a draft must fail without writing an artifact. Future UI should place the per-draft check inside the draft review side panel, with defaults in Project Settings > Writing Quality. It should not be a blocking pop-up. Auto creation of revision requests must remain disabled unless explicitly implemented later.

MVP-16.8 style suggestion artifact slice:

```text
create-style-suggestion + data/style_suggestions/*.json + manual metric-level suggestions.
```

Style suggestions must be generated from existing style-check metadata only. They may contain metric IDs, severity, direction, and generic manual advice, but must not contain draft text, prompt text, generated content, confirmed chapter text, external corpus text, raw Provider responses, or plaintext secrets. They must not call Providers, modify drafts, create revision requests, auto-revise, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

MVP-16.9 manual style suggestion decision slice:

```text
decide-style-suggestion + one-time decision metadata.
```

Manual style suggestion decisions must support `accepted`, `ignored`, and `needs_manual_rewrite`. They must update only the style suggestion artifact and index metadata. They must not apply edits, mutate drafts, create revision requests, call Providers, auto-revise, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

MVP-17 manual rewrite workspace slice:

```text
create-manual-rewrite-task + data/manual_rewrite_tasks/*.json + human rewrite task metadata.
```

Manual rewrite tasks must only be created from style suggestions with `needs_manual_rewrite` decisions. They must reject `accepted` or `ignored` suggestions and duplicate tasks. They may track `pending`, `in_progress`, `done`, and `skipped`, but must not call Providers, generate drafts, modify drafts, create revision requests, auto-revise, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

Do not start MVP-0 with frontend, LLM calls, prompt design, or chapter generation.

MVP-0 verification mode:

```text
unit tests and minimal commands only; no frontend required
```

Runtime project data default:

```text
I:\AI-NOVEL\novel_agent_workbench\workspace_projects
```

This directory is for real local project data and must not be tracked by Git.

Deletion policy:

```text
No real deletion in early MVP. Use .trash for reversible retirement.
```

Testing exception:

```text
Unit tests may create and clean isolated temporary files/directories. This exception does not apply to real runtime project data.
```

Checkpoint policy:

```text
Checkpoints exclude secrets by default. Restore must not hard delete; overwritten files are retired with .trash.
```

## Construction Strategy

Start from a clean skeleton. Use the reference project as a design and behavior sample only.

If code is copied from the reference project, the copied scope must be small, reviewed, and logged with:

```text
source file
target file
reason for reuse
risk checked
test added or reused
```

## Version Control

The active implementation folder uses local Git for snapshots and diffs.

Rules:

- local repository only unless the user explicitly asks for remote publishing,
- do not track secrets or local environment files,
- do not track generated runtime projects, exports, backups, or logs,
- check `git status` before and after meaningful code edits.
