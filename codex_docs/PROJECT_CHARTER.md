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
