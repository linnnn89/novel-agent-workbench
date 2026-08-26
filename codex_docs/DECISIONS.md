# Decisions

## 2026-05-17: Reference Project Is Read-Only

Decision: `I:\AI-NOVEL\Tonade_DSv4-flash_100w_novel_agent-main` is reference-only.

Reason: The old project is a model to learn from, not a canvas to overwrite. New code must be built in a separate folder.

Impact: All implementation work targets `I:\AI-NOVEL\novel_agent_workbench`.

## 2026-05-17: Active Implementation Folder

Decision: Use `novel_agent_workbench` as the active construction directory.

Reason: The name is clear, neutral, and separate from the old downloaded source.

Impact: New source, tests, docs, and logs start under this folder.

## 2026-05-17: Construction Strategy

Decision: Use clean skeleton first.

Reason: Avoid inheriting hidden coupling, historical baggage, and the reference project's current generate-and-commit architecture risk. Reuse from the reference project must be selective, reviewed, and documented.

Impact: New modules should be designed around the target architecture first. Reference code may inform behavior, prompts, tests, and small helper implementations, but large blind copying is not the default path.

## 2026-05-17: MVP-0 First Engineering Slice

Decision: Start MVP-0 with the local storage kernel.

Reason: Public agentic-coding guidance emphasizes verification, scoped plans, checkpoints, and persistent context. Python and SQLite documentation also support the conclusion that local data integrity should be built on atomic write/commit behavior. This project's highest early risk is data corruption or state pollution, so storage safety should precede UI, LLM providers, and generation workflows.

Impact: The first code implementation should create `ProjectStore` plus tests for project initialization, atomic JSON writes, backup behavior, file locking, and secrets/config separation.

## 2026-05-17: Local Git Repository

Decision: Initialize a local Git repository in `novel_agent_workbench`.

Reason: Local version control gives clear change snapshots, diffs, and rollback points during AI-led development. This is local only and does not imply GitHub or any network push.

Impact: All future implementation changes should be reviewable through Git status/diff. Secrets and generated runtime outputs are excluded by `.gitignore`.

## 2026-05-17: MVP-0 Verification Mode

Decision: MVP-0 may be backend/test-only with no UI.

Reason: The first phase is about storage safety, project locking, backup behavior, and secrets isolation. These are best verified with deterministic unit tests and small command-line checks before adding a frontend surface.

Impact: Do not build UI for MVP-0. Use tests and minimal commands to verify the storage kernel first.

## 2026-05-17: Runtime Project Data Directory

Decision: Store real runtime project data under `workspace_projects/` inside `novel_agent_workbench`.

Reason: This keeps new project data isolated from the reference project and makes it easy to exclude real user/runtime data from Git.

Impact: `workspace_projects/` is ignored by Git. Unit tests should use temporary directories unless explicitly testing default path behavior.

## 2026-05-17: No Real File Deletion In Early MVP

Decision: Do not support or perform real file deletion during early MVP work.

Reason: The user wants maximum recoverability. Files that appear unnecessary should remain restorable.

Impact: When a file must be retired, rename it with the `.trash` suffix instead of deleting it. Actual deletion requires a later explicit user decision and a documented recovery/backup policy.

## 2026-05-17: Trash Suffix

Decision: Use `.trash` as the single retirement suffix.

Reason: `.trash` is short, clear, easy to search, and less likely than `.ontodelete` to imply that an automated later hard-delete is expected.

Impact: Do not create alternative retirement suffixes unless the user changes this rule.

## 2026-05-17: Test Temporary Directory Cleanup

Decision: Unit tests may create and automatically clean test-only temporary files/directories.

Reason: Storage safety tests need isolated files to verify writes, backups, and locks. Temporary test cleanup is safe when isolated from real runtime data.

Impact: Cleanup is allowed only for system temp directories or test-owned temp directories. Real project files under `workspace_projects/` still follow the no-hard-delete policy and must be retired with `.trash`.

## 2026-05-17: MVP-0 Checkpoint Format

Decision: ProjectStore checkpoints use ZIP archives with an embedded `checkpoint_manifest.json`.

Reason: A ZIP archive is portable, inspectable, and easy to restore locally. The manifest gives future tools a deterministic file list, size, and hash inventory.

Impact: Checkpoints exclude secrets by default and restore without hard deletion. Existing files overwritten during restore are first retired with `.trash`.

## 2026-05-17: MVP-0 Project Registry

Decision: Add a backend-only `ProjectRegistry` to route and index multiple local projects under `workspace_projects/`.

Reason: Multi-project isolation requires a single safe entrypoint for creating, opening, and listing projects before any UI or generation workflow exists.

Impact: `ProjectRegistry` manages root-level `registry.json`, returns `ProjectStore` instances, and exposes no hard delete API.

## 2026-05-17: MVP-0 Config And Migration Boundary

Decision: Add default config structures and migration helpers as backend-only MVP-0 infrastructure.

Reason: MVP-1 Provider work and MVP-2 context work need stable project-level configuration files before any UI or LLM integration is attempted.

Impact: `config.py` owns default structures and schema version. `ProjectStore` owns safe migration orchestration, checkpoint-before-migration, placeholder data file creation, secrets isolation, and public state masking.

## 2026-05-17: MVP-1 Provider Config Stub

Decision: Start MVP-1 with provider configuration objects and fake connection tests only.

Reason: writer/scorer/reviser roles and secret references should be validated before any real Provider or network call is introduced.

Impact: `providers.py` may parse and validate role config, update project config, and fake-test connection readiness. It must not perform HTTP requests or call external APIs.

## 2026-05-17: MVP-1 Mock-Only Provider Interface

Decision: Add a Provider interface and deterministic `mock` provider before any real LLM integration.

Reason: Request/response contracts, role routing, error taxonomy, usage placeholders, and audit logs should be testable without network side effects or API keys.

Impact: `ProviderRequest`, `ProviderResponse`, `ProviderClient`, and `MockProviderClient` are backend-only. `create_provider_client(...)` only enables `provider="mock"`; other provider ids fail with `unsupported_provider`. Provider call logs record metadata such as `call_id`, role, provider, model, status, error type, and usage, but never prompt text or plaintext secrets.

## 2026-05-17: MVP-1 Draft Generation Writes Drafts Only

Decision: Add a backend-only Draft Generation Service that writes mock writer output to draft artifacts only.

Reason: Generation must be separated from confirmation. A draft can be inspected, revised, or discarded later, but it must not update formal context, Memory Bank, RAG, confirmed chapters, or export state.

Impact: `DraftGenerationService` writes `data/drafts/*.json` and `data/drafts_index.json`. Draft artifacts store generated text and request summaries, but not prompt text or plaintext secrets. Confirmed chapter commit logic remains unimplemented.

## 2026-05-17: MVP-1 Explicit Draft Commit Boundary

Decision: Add an explicit commit path from draft artifact to confirmed chapter artifact.

Reason: Confirmed chapters must only be created after an explicit backend operation. This prevents generation from silently mutating formal context.

Impact: `DraftGenerationService.commit_draft(...)` creates a pre-commit checkpoint, writes `data/confirmed_chapters/<chapter_id>.json`, updates `data/confirmed_chapters.json`, marks the source draft as `committed`, and appends metadata to `data/commit_log.json`. Commit does not update Memory Bank, RAG, export settings, or export files.

## 2026-05-17: MVP-1 Safe Project State Summary

Decision: Add `public_project_state(...)` as the backend state surface for future UI work.

Reason: UI-facing state should be available without exposing prompt text, generated chapter content, or plaintext secrets.

Impact: The state summary reports counts, latest draft metadata, latest confirmed chapter metadata, role configuration summaries, and masked secrets only.

## 2026-05-17: MVP-1 Backend Application Service Facade

Decision: Add `WorkbenchApplicationService` as the stable backend facade for future CLI, HTTP, or UI layers.

Reason: The UI should not directly orchestrate registry, provider config, draft generation, commit, and state modules. A thin facade keeps workflows discoverable and testable without adding a frontend yet.

Impact: The facade exposes project creation/listing, safe state, mock writer configuration, draft generation/list/read, explicit commit, and confirmed chapter read/list. It does not implement network APIs, UI routing, real Provider calls, Memory Bank/RAG/export updates, or DOCX.

## 2026-05-17: MVP-1 Backend-Only CLI Smoke Runner

Decision: Add `novel_agent_workbench.cli` as a backend-only command runner.

Reason: The user needs a way to run the local backend loop without writing Python code, while still avoiding UI and HTTP complexity.

Impact: The CLI delegates to `WorkbenchApplicationService`, outputs JSON, and supports `smoke`, project creation/listing, safe state, mock writer config, draft generation/list/read, explicit commit, and confirmed chapter list/read. It does not call real Providers or start a server.

## 2026-05-17: MVP-1 Read-Only Safety Audit

Decision: Add `audit_project(...)` and the `audit-project` CLI command before real Provider integration.

Reason: Before any real API key or Provider is introduced, the project needs a repeatable local check for obvious key, prompt, content, log, checkpoint, and public-state leaks.

Impact: Audit is read-only and returns JSON with `ok`, `findings`, and `checked_paths`. Real Provider integration must pass `audit-project` first.

## 2026-05-17: MVP-2 Provider Preflight Boundary

Decision: Document Provider request/response and error contracts before implementing real Provider calls.

Reason: Real Provider integration is a higher-risk step because it introduces network side effects, API keys, and cost. The contract must require `project_secret.*` references, `secrets.local.json` storage, no plaintext keys in config, and no prompt/secrets in logs.

Impact: `codex_docs\APPLICATION_SERVICE_CONTRACT.md` records current Provider fields and error types. No real Provider has been added.

## 2026-05-17: MVP-1 Chapter ID Safety

Decision: Restrict `chapter_id` to ASCII letters, numbers, `_`, and `-`.

Reason: Confirmed chapter artifacts are stored by chapter id. Allowing spaces, path separators, colons, Unicode ids, or values that require filename cleaning can create path ambiguity or file collisions.

Impact: Human-readable chapter names should use title fields. Storage ids remain simple and stable.

## 2026-05-17: MVP-1 Audit Consistency Checks

Decision: Extend `audit-project` to check confirmed chapter consistency and keep audit read-only.

Reason: Explicit commit writes multiple files. Per-file atomic writes plus pre-commit checkpoint are useful, but a crash or future bug can still leave an artifact/index/status mismatch.

Impact: Audit now checks orphan confirmed artifacts, missing confirmed artifacts, source draft commit status, missing commit log entries, unsafe confirmed artifact paths, default checkpoint secret inclusion, and public-state leaks. Audit uses a no-initialize public state path so uninitialized projects are not modified during audit.

## 2026-05-17: MVP-2 Provider Adapter Registry

Decision: Introduce a Provider adapter registry before enabling any real Provider.

Reason: Real Provider access introduces network, API key, and cost risks. The system needs a single source of truth for which adapters are enabled and whether network is allowed.

Impact: `mock` is the only enabled adapter. `openai_compatible` and `deepseek` are registered as disabled placeholders with `network_allowed=false`. Generation with a disabled adapter returns `adapter_disabled` and does not attempt HTTP.

## 2026-05-17: MVP-2 Project Secret Resolver Contract

Decision: Provider API keys may only be resolved from `data/secrets.local.json` through `project_secret.<name>` references.

Reason: This keeps plaintext keys out of `config.json`, public state, logs, checkpoints, and audit output. Environment variables are intentionally not a secret source for project Provider config.

Impact: `resolve_project_secret(...)` rejects missing, empty, and invalid refs with stable error types. Provider status checks may mask key presence but never return plaintext.

## 2026-05-17: MVP-2 Provider Preflight CLI And Audit

Decision: Add backend-only Provider preflight commands and Provider-aware audit rules.

Reason: The user needs a local way to inspect Provider readiness before any UI or real HTTP integration exists.

Impact: `provider-status` and `list-provider-adapters` return JSON and do not send network requests. `audit-project` now flags raw Provider keys in config, disabled adapters, missing secret refs, and missing local secrets. Passing `audit-project` remains required before real Provider enablement.

## 2026-05-17: MVP-2 Provider Config Preflight Write Path

Decision: Add safe write paths for disabled Provider role config and project-local secrets.

Reason: Before enabling a real Provider, the system needs to rehearse configuration, secret storage, status checks, and audit without network side effects.

Impact: `configure-provider-role` writes registered adapter config and `project_secret.<name>` refs only. `set-project-secret` writes `data/secrets.local.json` and returns masked metadata only. Disabled adapters still return `adapter_disabled` and cannot generate drafts.

## 2026-05-17: MVP-2 Provider Dry-Run Adapter

Decision: Add disabled dry-run adapter behavior for `deepseek` and `openai_compatible`.

Reason: Before enabling real HTTP calls, Provider request translation must be testable without exposing prompt text, request bodies, or API keys.

Impact: `provider-dry-run` returns a safe OpenAI-compatible summary containing provider, model, base_url_host, message_count, prompt/system prompt character counts, temperature, max_tokens, and metadata key names. It sends no network requests, writes no preflight log by default, and keeps real adapters disabled.

## 2026-05-17: MVP-2 Chutes Provider Preflight

Decision: Register `chutes_openai` as a disabled OpenAI-compatible Provider adapter.

Reason: The user supplied Chutes endpoint/model details. The workbench can capture the public Provider shape now while keeping real network calls behind a later explicit approval gate.

Impact: `chutes_openai` supports config and dry-run summaries with `base_url=https://llm.chutes.ai/v1` and model examples such as `Qwen/Qwen3-32B-TEE`. It remains disabled, no-network, and cannot generate drafts.

## 2026-05-17: MVP-2 Chutes Explicit Real Test

Decision: Add and run a single explicit `provider-real-test` path for `chutes_openai`.

Reason: The user explicitly allowed a network test. The test must validate real connectivity without turning real Providers into normal generation adapters.

Impact: `provider-real-test` sends one non-streaming Chutes request and returns only metadata: status code, finish reason, token usage, response text length, and host. It does not return generated text, write provider logs, create drafts, or update confirmed chapters, Memory Bank, RAG, or exports. The first real test returned HTTP 200 with 28 total tokens.

## 2026-05-17: MVP-2 Chutes Controlled Real Draft Path

Decision: Allow `chutes_openai` to generate writer drafts through explicit user-triggered commands.

Reason: The workbench needs one real Provider path for end-to-end draft testing, but it must stay auditable and limited to configured writer generation.

Impact: `generate-draft` reaches Chutes when the role is writer, the Provider is `chutes_openai`, the secret resolves from `secrets.local.json`, and audit has no key/prompt/content leak finding. Generated content is stored only in draft artifacts; provider logs, CLI output, and audit output remain metadata-only. No automatic commit, Memory Bank, RAG, export, UI, DOCX, or scoring work was added.

## 2026-05-17: MVP-2.5 Chutes Real Provider Runbook

Decision: Add `chutes-generate-once` as the preferred operator command for controlled real Chutes draft tests.

Reason: Manual real-provider testing required several separate commands, which increased the chance of forgetting to clear the runtime secret or run post-audit. A single runbook command makes the sequence auditable and easier to recover.

Impact: The runbook performs audit precheck, optional no-backup secret write, provider config write, draft generation, optional no-backup secret cleanup, and audit postcheck. It returns only metadata. Draft content stays in `data/drafts/*.json`; no confirmed chapter, Memory Bank, RAG, export, UI, DOCX, or scoring/revision behavior was added.

## 2026-05-17: MVP-3 Chapter Workflow State

Decision: Add `data/chapters_workflow.json` as the metadata-only chapter workflow index.

Reason: Drafts and confirmed chapters are artifacts, but future UI and scoring/revision flows need a stable chapter-level state boundary before any complex workflow is added.

Impact: Chapters can move through `planned`, `drafting`, `draft_ready`, `committed`, and `blocked`. Draft generation marks `drafting` then `draft_ready` on success or `blocked` on provider/config failure. Explicit commit marks `committed`; duplicate or failed commit records metadata-only error without downgrading an already committed chapter. CLI commands `mark-chapter-planned`, `chapter-status`, and `list-chapters` expose the state. Workflow state stores only metadata and error summaries, never prompt text, generated content, or plaintext secrets.

## 2026-05-17: MVP-3.5 Draft Review Skeleton

Decision: Add a backend-only Draft Review / Quality Check layer using the existing `scorer` role and deterministic `mock` Provider.

Reason: Before adding automatic revision or complex scoring, the workbench needs a safe review artifact boundary that can be inspected by humans and future UI code without mutating confirmed chapters or formal context.

Impact: `DraftReviewService.review_draft(...)` writes `data/reviews/*.json` and `data/reviews_index.json`, then marks chapter workflow state as `review_ready` with `latest_review_id`. Review artifacts contain review metadata, scores, issues, recommendation, Provider/model/usage, and character-count summaries only. They must not store draft content, original prompts, raw Provider responses, or plaintext secrets. CLI commands `review-draft`, `list-reviews`, and `read-review` expose the flow. Review does not auto-commit, auto-revise, update Memory Bank, update RAG, create exports, create DOCX, or call new real Providers.

## 2026-05-17: MVP-4 Manual Review Decision Skeleton

Decision: Add a one-time manual decision layer on top of review artifacts.

Reason: After a review exists, the operator needs to mark whether the draft is acceptable, needs revision, or is blocked without accidentally committing or rewriting content.

Impact: `DraftReviewService.decide_review(...)` accepts only `accepted`, `needs_revision`, or `blocked` plus an optional safe ASCII `reason_code`. It updates the review artifact/index and chapter workflow metadata. Chapter workflow may move to `review_accepted`, `needs_revision`, or `blocked`; `accepted` is not a commit and does not create confirmed chapters. The decision layer stores no free-text notes, draft content, prompt text, raw Provider response, or plaintext secrets. CLI command `decide-review` exposes the operation.

## 2026-05-17: MVP-4.5 Revision Request Skeleton

Decision: Add a metadata-only Revision Request layer after `needs_revision`.

Reason: A draft that needs revision should be represented as a durable request before any future revision generator exists. This keeps the workflow inspectable without mutating drafts or confirmed chapters.

Impact: `RevisionRequestService.create_revision_request(...)` creates `data/revision_requests/*.json` and `data/revision_requests_index.json` only when the source review decision is `needs_revision`. It rejects pending, accepted, blocked, missing, and duplicate requests. Chapter workflow may move to `revision_requested` with `latest_revision_request_id`. The operation does not call Providers, generate text, edit drafts, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or store prompt/content/secrets.

## 2026-05-17: MVP-5 Mock Revision Draft Service

Decision: Add a mock-only revision draft candidate generator from revision requests.

Reason: The workflow now needs a concrete way to create a new candidate draft after `needs_revision`, but still must avoid overwriting source drafts, auto-committing, or introducing real Provider risk.

Impact: `RevisionRequestService.generate_revision_draft(...)` accepts only `requested` revision requests, calls the configured `reviser` role through the local `mock` Provider, writes a new `data/drafts/*.json` artifact, appends `data/drafts_index.json`, and updates the revision request to `draft_created` with `generated_draft_id`. The new draft contains `revision` metadata pointing to the source draft, review, and revision request. The operation does not overwrite source drafts, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, call real Providers, or store source prompt/content/secrets in metadata surfaces.

## 2026-05-18: MVP-5 Quality Hardening After Review

Decision: Close three review findings before starting the next feature layer.

Reason: The project had grown enough that recovery and audit edges mattered more than adding another workflow step. Secret rotation must not leave old plaintext keys in backup files; MVP-5 revision draft generation must remain mock-only even if a future real `reviser` role is configured; and audit should detect broken revision request/generated draft links.

Impact: `ProjectStore.write_secrets(...)` now uses atomic write without `.bak` backup. Normal JSON files still keep backup behavior. `RevisionRequestService.generate_revision_draft(...)` rejects non-`mock` reviser configs before reading source content or creating a candidate. `audit-project` now validates revision request artifacts, request index entries, generated draft existence, and generated draft back-links to the source draft/review/request.

## 2026-05-18: MVP-5.5 Revision Candidate Comparison Read-Model

Decision: Add a read-only revision candidate comparison surface after mock revision draft generation.

Reason: Once a revision candidate exists, the operator and future UI need a stable way to compare the source draft and candidate without opening raw content everywhere or making an automatic choice.

Impact: `RevisionCandidateService` lists candidates for a revision request and compares one candidate to its source using metadata-only summaries: ids, status, provider/model/usage, character count, word count, line count, link checks, and `manual_review_required`. It writes no files, returns no draft content or prompt text, does not choose a winner, does not commit, does not update Memory Bank/RAG/export, and does not call Providers.

## 2026-05-18: MVP-6 Confirmed Context Update Queue

Decision: Add an explicit metadata queue between confirmed chapters and future formal context updates.

Reason: Confirmed chapters are the only valid source for Memory Bank/RAG/export updates, but updating those systems automatically would be too risky before context policies and UI review exist.

Impact: `ContextUpdateQueueService` writes `data/context_update_queue.json` with pending update metadata for confirmed chapters. Queue entries contain ids, status, target placeholders, and text statistics only. The queue can be listed and marked `pending`, `acknowledged`, or `skipped`, but it does not mutate Memory Bank, RAG, exports, confirmed chapters, drafts, or Providers. `public_project_state` now exposes `context_update_count` and `latest_context_update` metadata.

## 2026-05-18: MVP-6.5 Context Update Preview

Decision: Add metadata-only preview artifacts for queued formal context work.

Reason: Before any Memory Bank/RAG/export mutation exists, the operator and future UI need a stable artifact that shows what would be considered for context work without copying chapter text or making irreversible updates.

Impact: `ContextUpdatePreviewService` creates `data/context_update_previews/*.json` plus `data/context_update_previews_index.json` from context queue items. Previews include ids, text statistics, target operation placeholders, and safety flags. They do not store chapter text, prompt text, raw Provider responses, or plaintext secrets, and they do not mutate Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers. `public_project_state` now exposes `context_preview_count` and `latest_context_preview`.

## 2026-05-18: MVP-7 Formal Context Policy Priority

Decision: Formal context work uses this priority order:

```text
world_building
character_relationships
chapter_summary
style_memory
foreshadowing
```

This reflects the user-provided order:

```text
世界观设定 > 人物关系 > 章节摘要 > 文风记忆 > 剧情伏笔
```

Reason: The system needs a stable policy before any Memory Bank/RAG update logic exists. Prioritizing world building and relationships first fits long-form novel continuity better than extracting every possible detail equally.

Impact: `config.py` now includes `formal_context_policy` under `context_policy`, with `mode=manual_preview_first`, category metadata, and `auto_extract=false` for every category. Context preview artifacts include a policy priority snapshot in `target_plan.formal_context.priority_order`. No automatic extraction, Provider call, Memory Bank mutation, RAG mutation, export update, or UI work was added.

## 2026-05-18: MVP-7.5 Formal Context Extraction Plan

Decision: Add a metadata-only formal context extraction plan artifact after context preview.

Reason: The project now has a confirmed-chapter queue, a preview artifact, and a user-approved priority order. Before any Memory Bank or RAG writes exist, the system needs a durable plan that future UI/operator steps can inspect category by category.

Impact: `FormalContextPlanService` creates `data/formal_context_plans/*.json` plus `data/formal_context_plans_index.json` from a context preview. Plans include ids, source metadata, text statistics, priority order, category work items, safety flags, and `manual_extraction_required`. They do not store chapter text, prompt text, raw Provider responses, or plaintext secrets, and they do not mutate Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers. CLI commands `create-formal-context-plan`, `list-formal-context-plans`, and `read-formal-context-plan` expose the operation.

## 2026-05-18: MVP-7.6 World Book Overlap Policy

Decision: World-building formal context has an explicit overlap policy with the future world book.

Reason: `world_building` is high priority, but a future world book will also store stable setting facts. If both Memory Bank and world book include the same facts at full strength, context assembly can waste tokens and increase contradiction risk.

Impact: `formal_context_policy.categories.world_building` now stores `world_book_overlap_policy=reduce_memory_when_world_book_enabled`, `memory_weight=1.0`, and `world_book_enabled_memory_weight=0.35`. Formal context plan category items expose the effective `memory_weight`, `world_book_enabled`, `world_book_overlap_policy`, and a recommendation. When `context_policy.world_book_enabled=true`, world-building Memory Bank weight is reduced by default. This is still metadata only; no Memory Bank, world book, RAG, export, Provider, or UI write was added.

## 2026-05-18: MVP-8 Context Assembler Dry-Run

Decision: Add a metadata-only local Context Assembler dry-run before implementing Memory Bank writes or final Provider prompt rendering.

Reason: Memory priority is not an LLM API-native capability. The project needs a local, testable surface that shows which context candidates would be selected, skipped, or reduced before real Provider calls depend on that behavior.

Impact: `ContextAssemblerService.dry_run(...)` collects formal context plan categories and existing Memory Bank item metadata, estimates token usage with a simple character-based estimator, sorts by category priority and memory weight, and returns selected/skipped metadata. It exposes that LLM APIs do not accept priority fields and that local assembly is required. CLI command `context-assembly-dry-run` exposes the check. The dry-run writes no files, returns no chapter text, Memory Bank text, prompt text, or plaintext secrets, and does not call Providers.

## 2026-05-18: MVP-8.5 Formal Context Task Queue

Decision: Add a metadata-only manual task queue from formal context plans.

Reason: After a plan exists and a dry-run can show priority, the operator and future UI need a stable list of per-category manual tasks before any actual Memory Bank application exists.

Impact: `FormalContextTaskQueueService.enqueue_plan_tasks(...)` writes `data/formal_context_task_queue.json` with one task per formal context category. Tasks include ids, plan/preview/update/chapter references, category, priority, target, memory weight, recommendation, status, timestamps, and safety flags. They do not store chapter text, prompt text, Memory Bank text, raw Provider responses, or plaintext secrets. CLI commands `enqueue-formal-context-tasks`, `list-formal-context-tasks`, and `mark-formal-context-task` expose the flow. The queue does not write Memory Bank, world book, RAG, exports, drafts, confirmed chapters, or Providers.

## 2026-05-18: MVP-9 Memory Apply Preview

Decision: Add a metadata-only preview before any Memory Bank write.

Reason: The task queue identifies what category work should be done, but writing long-term memory is high-risk. A preview layer lets the operator and future UI inspect candidate writes, world-book overlap risk, and safety flags before `memory_bank.json` is changed.

Impact: `MemoryApplyPreviewService.create_memory_apply_preview(...)` writes `data/memory_apply_previews/*.json` plus `data/memory_apply_previews_index.json`. Previews include task ids, categories, priority, target, memory weight, duplicate-risk metadata, safety flags, and `would_write_memory_bank=false`. CLI commands `create-memory-apply-preview`, `list-memory-apply-previews`, and `read-memory-apply-preview` expose the flow. The preview does not store chapter text, prompt text, Memory Bank text, raw Provider responses, or plaintext secrets, and does not write Memory Bank, world book, RAG, exports, drafts, confirmed chapters, or Providers.

## 2026-05-18: MVP-9.5 Memory Bank Apply Commit Gate

Decision: Add an explicit gate for committing Memory Apply Preview metadata into `memory_bank.json`.

Reason: The system needs a reversible, auditable first Memory Bank write path, but it is still unsafe to auto-extract or store chapter text. The first write path should create empty placeholder entries that future manual fill/edit steps can populate.

Impact: `MemoryApplyPreviewService.commit_memory_apply_preview(...)` creates a `pre_memory_apply` checkpoint, then writes only placeholder Memory Bank entries with `entry_type=formal_context_placeholder`, `status=manual_text_required`, and `text=""`. Duplicate source tasks are skipped on repeated commits. CLI command `commit-memory-apply-preview` exposes the explicit gate. The operation does not copy prompt text, chapter text, Memory Bank text, raw Provider responses, or plaintext secrets, and does not write world book, RAG, exports, drafts, confirmed chapters, or Providers.

## 2026-05-18: MVP-10 Manual Memory Bank Text Fill/Edit

Decision: Add an explicit manual text fill/edit workflow for placeholder Memory Bank entries.

Reason: The project now has a safe metadata path from confirmed chapters to manual context tasks and placeholder Memory Bank entries. The next safest step is human-authored Memory Bank text, not automatic extraction. This keeps the difficult context-priority problem visible while avoiding silent prompt/content copying.

Impact: `MemoryBankService.set_memory_text(...)` creates a `pre_memory_text_update` checkpoint, validates nonempty text, rejects text longer than 1200 characters, rejects obvious secret-like values, and writes the text only into the selected `memory_bank.json` item with `status=ready` and `text_status=manual`. Default list/read/project-state surfaces remain metadata-only; the actual Memory Bank text is returned only by an explicit `include_text=true` read. CLI commands `list-memory-items`, `read-memory-item`, and `set-memory-text` expose the flow. The operation does not call Providers, extract chapter text, write world book, update RAG/export, mutate drafts/confirmed chapters, or auto-assemble Provider prompts.

## 2026-05-18: MVP-10.5 Memory Bank Item Lifecycle Controls

Decision: Add explicit enable/disable controls for individual Memory Bank items.

Reason: Manual Memory Bank text can still become stale, duplicated, or temporarily unsafe for context assembly. The system needs a reversible metadata switch before any real prompt rendering exists.

Impact: `MemoryBankService.set_memory_item_enabled(...)` creates a `pre_memory_lifecycle_update` checkpoint and writes `enabled`, `lifecycle_status`, and `lifecycle_reason_code` metadata on the selected item. CLI commands `disable-memory-item` and `enable-memory-item` expose the operation. Disabled items are not deleted and their text is not returned by default outputs. `ContextAssemblerService.dry_run(...)` now reports disabled Memory Bank candidates as skipped with `skip_reason=memory_item_disabled`. The operation does not call Providers, alter Memory Bank text, write world book, update RAG/export, mutate drafts/confirmed chapters, or auto-render prompt context.

## 2026-05-18: MVP-11 Context Package Preview

Decision: Add a read-only local context package preview built from enabled manual Memory Bank text.

Reason: The project needs to verify the practical Memory Bank priority and token-budget behavior before any final Provider prompt rendering or real generation depends on it. The safest next step is an operator-visible preview that can show which manual memory notes would be selected or skipped.

Impact: `ContextAssemblerService.package_preview(...)` returns selected Memory Bank sections, skipped items, estimated token usage, and Provider boundary metadata. Default output remains metadata-only and does not include Memory Bank text. Text is returned only when `include_text=true`, for explicit human review. CLI command `context-package-preview` exposes the flow. The method is read-only; it writes no artifact, calls no Provider, logs no prompt, does not read chapter content, and does not update world book, RAG, exports, drafts, or confirmed chapters.

## 2026-05-18: MVP-11.5 Prompt Render Dry-Run

Decision: Add a no-write prompt render dry-run envelope before final Provider prompt rendering.

Reason: Before connecting context assembly to draft generation, the operator needs to see the shape of the future message payload and token estimates without leaking prompt/context text by default or calling a model.

Impact: `ContextAssemblerService.prompt_render_dry_run(...)` combines an operator prompt, optional system prompt, and the context package preview into a redacted message envelope. Default output reports character counts, selected context metadata, and Provider boundary flags only. Prompt text and context text appear only with explicit include flags. CLI command `prompt-render-dry-run` exposes the flow. The method writes no files, calls no Provider, does not read chapter content, does not create prompt logs, and does not update world book, RAG, exports, drafts, or confirmed chapters.

## 2026-05-18: MVP-12 Mock-Only Context-Aware Draft Generation

Decision: Add context-aware draft generation through the local `mock` writer only.

Reason: The context package and prompt render dry-run now prove the local assembly boundary. The next safe step is to verify the end-to-end draft path without introducing real Provider risk or automatic commit.

Impact: `DraftGenerationService.generate_context_draft(...)` builds a local prompt render dry-run with explicit local text inclusion, renders a combined in-memory prompt, and sends it only to the configured `mock` writer. Draft artifacts may store generated mock content and safe `context_generation` metadata, including context source ids and counts, but not operator prompt text or Memory Bank text. CLI command `generate-context-draft` exposes the flow. It does not allow real Providers, auto-commit, update Memory Bank, update world book, update RAG/export, create DOCX, or write prompt logs.

## 2026-05-18: MVP-12.5 Context Generation Audit

Decision: Extend `audit-project` to validate context-aware draft metadata before real Providers can consume assembled context.

Reason: Draft artifacts may contain generated content, so audit must not blindly scan every draft body as a leak. The safer boundary is to audit the `context_generation` metadata and drafts index consistency.

Impact: `audit-project` now checks context-aware draft index entries, artifact paths, required `context_generation` metadata, approved mock-only mode, text-safety flags, section-count consistency, forbidden metadata keys, and prompt/secret-like strings inside `context_generation`. It does not treat the normal draft `content` field as an audit failure. This preserves the draft review workflow while catching accidental prompt/context leakage in metadata.

## 2026-05-19: MVP-13 Corpus Profiler

Decision: Add a read-only metadata profiler for external `.txt` novel corpora.

Reason: The project needs to learn structural facts from real long-form web-novel files before building any importer, sampler, or style workflow. The safe first step is corpus profiling that reports counts and distributions only.

Impact: `corpus_profiler.py`, `WorkbenchApplicationService.profile_corpus(...)`, and the `profile-corpus` CLI command can inspect an external text file and return encoding, line/chapter structure, chapter-length distribution, dialogue proxy counts, and rough name candidates. The profiler does not create projects, write artifacts, call Providers, copy source/chapter text, create drafts, create confirmed chapters, or update Memory Bank/RAG/export. Name candidates are heuristic and may include false positives; they are not treated as a character database.

## 2026-05-19: MVP-13.5 Corpus Profile Artifacts

Decision: Add explicit project-local corpus profile artifacts, but make persistent output more conservative than transient CLI profiling.

Reason: Later phases need durable corpus-level structure metadata. Storing raw source paths, excerpts, or candidate names now would blur the line between profiling and importing copyrighted source material.

Impact: `CorpusProfileArtifactService`, `save-corpus-profile`, `list-corpus-profiles`, and `read-corpus-profile` write/read `data/corpus_profiles/*.json` plus `data/corpus_profiles_index.json`. Saved artifacts include file name, size, SHA-256, encoding, line/chapter counts, chapter statistics, dialogue proxy counts, and safety flags. Saved artifacts do not store external source paths, source text, chapter heading text, dialogue excerpts, or candidate-name text. They do not call Providers, create drafts, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-14 Corpus Boundary Indexes

Decision: Add explicit no-text chapter boundary artifacts for external corpora.

Reason: Future import/sampling work needs stable chapter offsets, but storing headings or excerpts would require a separate copyright/safety decision. Line and character offsets are enough for planning without copying source text.

Impact: `CorpusBoundaryService`, `save-corpus-boundaries`, `list-corpus-boundaries`, and `read-corpus-boundaries` write/read `data/corpus_boundaries/*.json` plus `data/corpus_boundaries_index.json`. Boundary artifacts store ordinal, heading line number, body line range, body character range, and body character count. They do not store external source paths, chapter heading text, source text, excerpts, candidate names, or plaintext secrets, and they do not call Providers, create drafts, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-15 Corpus Sample Quarantine

Decision: Allow bounded real-text corpus samples only as temporary local testing artifacts.

Reason: The user allowed storing real corpus-derived content during testing, with the requirement that it be removed before GitHub publication. The code must make that status machine-visible instead of relying on memory.

Impact: `CorpusSampleService`, `create-corpus-sample`, `list-corpus-samples`, and `read-corpus-sample` write/read `data/corpus_samples/*.json` plus `data/corpus_samples_index.json`. Samples require a matching source SHA-256 from a boundary artifact, are bounded to 2000 characters, do not store external source paths, and are marked `test_only=true` and `publish_blocker=true`. Default reads/list/state do not return sample text. `audit-project` fails with `non_publishable_corpus_sample_present` while any sample artifact exists. Samples do not call Providers, create drafts, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-15.5 Prepublish Readiness Check

Decision: Add a read-only `prepublish-check` gate before any future GitHub publication.

Reason: The project now has user-authorized real corpus sample quarantine and real Provider test history. Publication readiness must be machine-checkable instead of relying on chat memory.

Impact: `publication.py`, `WorkbenchApplicationService.prepublish_check(...)`, and CLI command `prepublish-check` scan the source tree and runtime projects for missing ignore patterns, publishable secret/env files, corpus sample blockers, and high-risk audit findings. Real corpus samples remain blockers. Disabled Provider adapters or missing local runtime secrets remain visible in `audit-project`; prepublish excludes those Provider readiness warnings when they do not expose secrets, prompts, or content. The check is read-only and does not call Providers, delete files, or print sample text/secrets.

## 2026-05-19: MVP-16 Self Style Baseline

Decision: Build the first style baseline from the user's own confirmed chapters, not from external reference novels.

Reason: The user clarified that the practical product need is Memory Bank / own-work style continuity. External TXT novels are useful for parser and quarantine testing, but they must not become the default style source.

Impact: `SelfStyleBaselineService`, `create-self-style-baseline`, `list-self-style-baselines`, and `read-self-style-baseline` write/read `data/style_baselines/*.json` plus `data/style_baselines_index.json`. Baselines include numeric/statistical metrics for chapter length, paragraph count, sentence length, dialogue-line ratio, and punctuation frequency. They do not store confirmed chapter text, prompt text, external corpus text, source paths, raw Provider responses, or plaintext secrets. They do not call Providers, create drafts, create confirmed chapters, update Memory Bank/RAG/export, or read external corpus files.

## 2026-05-19: MVP-16.5 Draft vs Self Style Check

Decision: Add a local draft-vs-baseline style check before any LLM-based style review.

Reason: The project can already calculate its own style baseline from confirmed chapters. The safest next step is a deterministic local comparison of one draft against that baseline, producing actionable metadata without model cost or content leakage.

Impact: `SelfStyleBaselineService.check_draft_against_baseline(...)`, `check-draft-style`, `list-draft-style-checks`, and `read-draft-style-check` write/read `data/style_checks/*.json` plus `data/style_checks_index.json`. Checks compare draft statistics against baseline ranges for length, paragraph/sentence structure, dialogue ratio, and selected punctuation frequency. They do not store draft text, prompt text, generated content, raw Provider responses, external corpus text, or plaintext secrets. They do not call Providers, create revision requests, auto-revise drafts, auto-commit drafts, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-16.6 Style Check Calibration

Decision: Treat draft style checks as scene-mode-aware hints, not strict pass/fail grading.

Reason: Long-form chapters naturally vary. Daily, romance, battle, climax, exposition, and transition chapters should not be forced to match the global average for dialogue ratio, sentence length, punctuation, or chapter length.

Impact: `check-draft-style` accepts `scene_mode` / `--scene-mode` with `general`, `daily`, `romance`, `battle`, `climax`, `exposition`, `transition`, and `custom`. P25-P75 deviations become `hint`; only calibrated extreme deviations become `warning`. Mode policies widen tolerance for intentional differences, such as low-dialogue exposition chapters or high-intensity battle/climax punctuation. The check remains local-only and still does not store draft text, call Providers, create revision requests, auto-revise, auto-commit, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-16.7 Style Check Policy Toggles

Decision: Make style checks, calibration, and hint display configurable, with future UI placement recorded in project config.

Reason: Style checks should help the operator while reviewing a draft, but they must not become intrusive or mandatory. The user explicitly wanted the option to turn this feature off and asked where it belongs in the UI.

Impact: `context_policy.style_check_policy` now stores `enabled`, `calibration_enabled`, `show_hints`, `default_scene_mode`, `severity_mode`, `auto_create_revision_request=false`, and `ui_placement`. `check-draft-style` supports `--disable-style-check`, `--disable-calibration`, `--enable-calibration`, `--hide-hints`, and `--show-hints` call-level overrides. If disabled, no style check artifact is written. Future UI placement is `draft_review_side_panel` with defaults in `project_settings_writing_quality`; modal pop-ups are not recommended. No UI was implemented.

## 2026-05-19: MVP-16.8 Style Suggestion Artifact

Decision: Convert style-check findings into manual suggestion artifacts before any automatic rewrite or revision workflow.

Rationale: A style check can identify metric-level drift, but applying changes automatically would be too aggressive because scenes intentionally vary by mode. Suggestions should therefore be review aids that tell the operator what to inspect, not instructions that mutate drafts.

Impact: `SelfStyleBaselineService.create_style_suggestion(...)`, `create-style-suggestion`, `list-style-suggestions`, and `read-style-suggestion` write/read `data/style_suggestions/*.json` plus `data/style_suggestions_index.json`. Suggestions are generated from style-check metadata only. They do not store draft text, prompt text, generated content, raw Provider responses, external corpus text, or plaintext secrets. They do not call Providers, modify drafts, create revision requests, auto-revise, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-16.9 Manual Suggestion Decision

Decision: Add explicit one-time operator decisions for style suggestion artifacts.

Rationale: Style suggestions should support human workflow tracking without silently becoming rewrite instructions. The operator can mark suggestions as accepted, ignored, or needing manual rewrite, while the system still avoids automatic draft mutation.

Impact: `SelfStyleBaselineService.decide_style_suggestion(...)` and `decide-style-suggestion` update only the style suggestion artifact and index `decision` metadata. Supported decisions are `accepted`, `ignored`, and `needs_manual_rewrite`. Duplicate decisions are rejected. Decision reason is a short ASCII `reason_code`, not free-form text. This path does not apply edits, create revision requests, call Providers, auto-revise, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-17 Manual Rewrite Workspace Skeleton

Decision: Add metadata-only manual rewrite tasks for style suggestions marked `needs_manual_rewrite`.

Rationale: `needs_manual_rewrite` should become an actionable human work item without turning into automatic LLM revision, draft mutation, or commit behavior. This preserves the explicit operator boundary.

Impact: `ManualRewriteTaskService`, `create-manual-rewrite-task`, `list-manual-rewrite-tasks`, `read-manual-rewrite-task`, and `mark-manual-rewrite-task` write/read `data/manual_rewrite_tasks/*.json` plus `data/manual_rewrite_tasks_index.json`. Tasks can only be created from `needs_manual_rewrite` style suggestion decisions. `accepted` and `ignored` suggestions are rejected. Duplicate tasks are rejected. Status supports `pending`, `in_progress`, `done`, and `skipped`. This path does not call Providers, generate drafts, modify drafts, create revision requests, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-17.5 Manual Rewrite Draft Submission

Decision: Allow a manual rewrite task to explicitly submit human text as a new draft candidate.

Rationale: Manual rewrite work needs a safe persistence target. The target should be a new draft artifact, not a mutation of the source draft or an automatic commit.

Impact: `ManualRewriteTaskService.submit_manual_rewrite_draft(...)` and `submit-manual-rewrite-draft` write a new `data/drafts/*.json` artifact, append `data/drafts_index.json`, and update the source manual rewrite task with `submitted_draft_id`. The new draft records `manual_rewrite_task_id`, `source_suggestion_id`, `source_check_id`, and `source_draft_id`. Empty text, skipped tasks, and duplicate submissions are rejected. This path does not call Providers, overwrite source drafts, create revision requests, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-18 Manual Rewrite Candidate Comparison / Selection Gate

Decision: Add a metadata-only comparison and selection gate for human-submitted manual rewrite draft candidates.

Rationale: After a human rewrite task creates a new draft candidate, the operator needs a stable decision point before any review or commit workflow. The comparison should help identify structural changes without storing or exposing the source/submitted draft bodies.

Impact: `ManualRewriteComparisonService`, `compare-manual-rewrite-candidate`, `list-manual-rewrite-comparisons`, `read-manual-rewrite-comparison`, and `decide-manual-rewrite-comparison` write/read `data/manual_rewrite_comparisons/*.json` plus `data/manual_rewrite_comparisons_index.json`. Comparisons are created from a manual rewrite task's `draft_id` and `submitted_draft_id`, store only ids, structural metrics, deltas, link checks, safety flags, and one explicit decision: `selected_for_review`, `rejected`, or `needs_more_manual_work`. This path does not store draft text, prompt text, raw Provider responses, or plaintext secrets. It does not call Providers, overwrite drafts, create revision requests, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-18.5 Review Handoff From Selected Manual Rewrite Candidate

Decision: Add a metadata-only handoff queue from selected manual rewrite comparisons to later explicit draft review.

Rationale: `selected_for_review` should become an actionable next-step marker without silently running a scorer, creating a review, committing a draft, or updating formal context. The operator still needs a separate explicit review action.

Impact: `ReviewHandoffService`, `create-review-handoff-from-manual-comparison`, `list-review-handoffs`, and `read-review-handoff` write/read `data/review_handoffs/*.json` plus `data/review_handoffs_index.json`. Handoffs can only be created from comparisons already decided as `selected_for_review`; pending, rejected, and needs-more-work comparisons are rejected. Handoff artifacts store ids, status, decision metadata, and safety flags only. They do not store draft text, prompt text, raw Provider responses, or plaintext secrets. They do not call Providers, auto-review, overwrite drafts, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## 2026-05-19: MVP-19 Planning Library And Final Prompt Assembly Safety

Decision: Implement backend-only Planning Library references as explicit manual context inputs before any UI or real Provider context assembly.

Rationale: Long-form generation needs total outline, arc constraints, beat sheets, and chapter plans to be selectable before prompt assembly. These references are not Memory Bank facts and should not be hidden inside automatic RAG/export flows.

Impact: `PlanningLibraryService`, `create-planning-item`, `list-planning-items`, `read-planning-item`, `activate-planning-item`, `deactivate-planning-item`, `enable-planning-item`, and `disable-planning-item` write/read `data/planning_library.json`. The service keeps `active_reference_ids` synchronized with active/enabled items, exposes metadata-only list/read/state by default, and rejects duplicate ids plus secret-like text. `ContextAssemblerService` now includes active/enabled Planning Library sections in `context-package-preview` and `prompt-render-dry-run`; inactive/disabled items are skipped. Text appears only with explicit include flags. This path does not call Providers, overwrite drafts, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export/UI/DOCX.

## 2026-05-19: MVP-19.5 Review-Draft Guard For Manual Rewrite Candidates

Decision: Require an explicit manual gate before a submitted manual rewrite draft candidate can enter `review-draft`.

Rationale: Manual rewrite candidates are human-submitted alternatives. They should not be scored just because a draft artifact exists; the operator must first choose the candidate via a `selected_for_review` comparison or route it through a `pending_review` handoff.

Impact: `DraftReviewService.review_draft(...)` now detects `manual_rewrite.mode=manual_rewrite_draft_candidate`. Those drafts are rejected before any scorer Provider call unless a matching `selected_for_review` manual rewrite comparison or `pending_review` handoff exists. Ordinary draft review is unchanged. Successful guarded reviews record a metadata-only `manual_rewrite_review_gate` summary in `request_summary`, and audit flags manual rewrite reviews whose gate metadata is missing or invalid. This path does not overwrite drafts, auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, or add UI.

## 2026-05-19: MVP-20 Final Provider Assembly Gate

Decision: Add a metadata-only approval gate before any future real context-aware Provider generation.

Rationale: Context-aware generation combines operator prompt, Planning Library, and Memory Bank context before a Provider request. That assembled request must have an explicit reviewable approval boundary before real Providers can ever consume it.

Impact: `FinalAssemblyGateService`, `create-final-assembly-gate`, `approve-final-assembly-gate`, `list-final-assembly-gates`, and `read-final-assembly-gate` write/read `data/final_assembly_gates/*.json` plus `data/final_assembly_gates_index.json`. Gate artifacts store only prompt/system/context digests, writer provider/model metadata, section summaries, token estimates, approval metadata, and safety flags. They do not store prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, or plaintext secrets. `generate_context_draft(...)` now requires a matching approved gate before any non-mock context-aware Provider path, then still fails because real context-aware Provider generation remains disabled in this phase.

## 2026-05-19: MVP-20.5 Review Handoff Consumption Metadata

Decision: Consume a `pending_review` handoff after its selected manual rewrite draft successfully creates a review.

Rationale: Review handoffs are actionable pending-review markers. Once the explicit review is created through the guarded path, leaving the handoff permanently pending would make queue state misleading.

Impact: `ReviewHandoffService.mark_review_created_unlocked(...)` updates the handoff artifact and index to `status=review_created` and records the created `review_id`. `DraftReviewService.review_draft(...)` calls it only after a successful review when the review gate came from a `pending_review` handoff. This path does not edit draft bodies, create drafts, auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, or call an extra Provider beyond the explicit review.

## 2026-05-19: MVP-21 Accepted Review Commit Gate

Decision: Require an accepted review for the same draft before `commit_draft(...)` can promote it to a confirmed chapter.

Rationale: `accepted` review decisions were already explicit human approvals, but commit still accepted any draft artifact. Confirmed chapters are the source for future context queues, style baselines, and exports, so promotion needs a hard review acceptance gate.

Impact: `DraftGenerationService.commit_draft(...)` now checks for an accepted review before creating a pre-commit checkpoint or writing confirmed files. Gate failures raise `DraftCommitGateError` and do not mutate chapter workflow state, so accidental early commit attempts do not block later review. Successful commit records metadata-only `commit_gate` fields in the confirmed artifact and commit log. The path still does not auto-review, auto-accept, auto-commit, overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, delete files, or call real LLMs.

## 2026-05-19: MVP-22 Final Provider Runbook Plan

Decision: Add a metadata-only final Provider runbook stage after an approved final assembly gate and before any future real context-aware Provider authorization.

Rationale: The final assembly gate proves a prompt/context/provider snapshot was approved, but the next step needs a separate operator-facing stop point that can summarize the planned run without sending anything to a real LLM or writing a draft.

Impact: `FinalProviderRunbookService`, `create-final-provider-runbook`, `list-final-provider-runbooks`, and `read-final-provider-runbook` write/read `data/final_provider_runbooks/*.json` plus `data/final_provider_runbooks_index.json`. Runbooks can only be created from approved final assembly gates and remain at `pending_operator_authorization`. They store provider/model snapshots, digests, prompt/context counts, token estimates, selected context section counts/types, operator checklist metadata, and safety flags only. They do not store prompt text, context text, Memory Bank text, Planning Library text, draft content, Provider raw responses, request bodies, or plaintext secrets. They do not call real LLMs, write or overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or mutate chapter workflow state.

## 2026-05-19: MVP-23 Final Provider Authorization Checkpoint

Decision: Add a metadata-only authorization checkpoint stage after a final Provider runbook and before any future execute command or real Provider call.

Rationale: A runbook says a final Provider call is ready for operator review. Before any execution path exists, the project needs a durable authorization record and checkpoint boundary that can be audited without enabling real generation or storing sensitive request material.

Impact: `FinalProviderAuthorizationService`, `authorize-final-provider-runbook`, `list-final-provider-authorizations`, and `read-final-provider-authorization` write/read `data/final_provider_authorizations/*.json` plus `data/final_provider_authorizations_index.json`, and create a no-secrets `pre_final_provider_authorization` checkpoint. Authorizations can only be created from `pending_operator_authorization` runbooks and are one-time per runbook. Artifacts store provider/model snapshots, digests, prompt/context counts, token estimates, selected context section counts/types, checkpoint summary metadata, execution-boundary flags, and safety flags only. They do not store prompt text, context text, Memory Bank text, Planning Library text, draft content, Provider raw responses, request bodies, plaintext execution tokens, or plaintext secrets. They do not call real LLMs, enable real Providers, write or overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or mutate chapter workflow state.

## 2026-05-19: MVP-24 Final Provider Execution Preflight Verifier

Decision: Add a metadata-only execution preflight verifier after final Provider authorization and before any future execute command.

Rationale: An authorization can become stale if the runbook, gate, or provider config changes. Before any real Provider path is considered, the system needs a reproducible verifier that records whether the chain still matches while remaining strictly no-execution.

Impact: `FinalProviderExecutionPreflightService`, `create-final-provider-execution-preflight`, `list-final-provider-execution-preflights`, and `read-final-provider-execution-preflight` write/read `data/final_provider_execution_preflights/*.json` plus `data/final_provider_execution_preflights_index.json`. Preflights verify authorization status, runbook status, gate approval, id/chapter consistency, runbook/gate/prompt/system/context digests, provider/model consistency, current writer config, checkpoint metadata, and execution boundary flags. They record either `passed_pending_execute_authorization` or `blocked` with issue codes. They do not store prompt text, context text, Memory Bank text, Planning Library text, draft content, Provider raw responses, request bodies, plaintext execution tokens, or plaintext secrets. They do not call real LLMs, write or overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or mutate chapter workflow state.

## 2026-05-19: MVP-25 Final Provider Execution Stub / Abort Gate

Decision: Add a final Provider execution stub that always fail-closes as a no-network rehearsal.

Rationale: The project ultimately needs to connect to an LLM, but the execution boundary must exist before the real execution path. A stub/abort gate proves the post-preflight path, duplicate-attempt handling, audit surface, and safety metadata without sending prompt/context to any Provider.

Impact: `FinalProviderExecutionAttemptService`, `attempt-final-provider-execution`, `list-final-provider-execution-attempts`, and `read-final-provider-execution-attempt` write/read `data/final_provider_execution_attempts/*.json` plus `data/final_provider_execution_attempts_index.json`. Attempts can only be created from `passed_pending_execute_authorization` preflights with zero issues, and each preflight can have only one attempt. The stub attempt records `status=aborted_real_llm_disabled` and `abort_reason_code=real_llm_disabled_by_policy`. Artifacts store ids, provider/model snapshots, digests, prompt/context counts, token estimates, execution boundary flags, and safety flags only. They do not store prompt text, context text, Memory Bank text, Planning Library text, draft content, Provider raw responses, request bodies, plaintext execution tokens, or plaintext secrets. The stub does not call real LLMs, enable real Providers, write or overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or mutate chapter workflow state; real Provider calls are handled by the later explicit real execution path.

## 2026-05-19: MVP-26 Final Provider Real Execution Readiness

Decision: Add a readiness report after the fail-closed execution attempt and before any actual Chutes call.

Rationale: The next real execution step needs a Chutes key. Before asking for that, the system should machine-check everything that does not require a real connection: source attempt provenance, current writer provider/model match, Chutes provider selection, api_key_ref presence, and project-secret presence.

Impact: `FinalProviderRealExecutionReadinessService`, `create-final-provider-real-execution-readiness`, `list-final-provider-real-execution-readiness`, and `read-final-provider-real-execution-readiness` write/read `data/final_provider_real_execution_readiness/*.json` plus `data/final_provider_real_execution_readiness_index.json`. Reports can only be created from aborted execution attempts and are one-time per attempt. They record `ready_for_manual_real_llm_authorization` when all metadata checks pass, otherwise `blocked` with issue codes. Artifacts store ids, provider/model snapshots, safe config metadata, project-secret presence, digests, prompt/context counts, token estimates, manual required action ids, execution boundary flags, and safety flags only. They do not store prompt text, context text, Memory Bank text, Planning Library text, draft content, Provider raw responses, request bodies, plaintext execution tokens, plaintext secrets, secret values, or generated text. They do not call real LLMs, write or overwrite drafts, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or mutate chapter workflow state.

## 2026-05-19: MVP-27 Final Provider Real Execution Path

Decision: Add the explicit Chutes-backed real final Provider execution path behind readiness and gate digest matching.

Rationale: The project goal is to connect a real LLM, but that path must remain auditable and impossible to trigger accidentally. The execution function should require a fresh operator prompt for digest matching and a ready execution report.

Impact: `FinalProviderRealExecutionService`, `execute-final-provider-real`, `list-final-provider-real-executions`, and `read-final-provider-real-execution` write/read `data/final_provider_real_executions/*.json` plus `data/final_provider_real_executions_index.json`. On success, the path writes one new draft artifact through the existing draft service and records metadata-only execution provenance. The path requires a ready zero-issue readiness report, current Chutes writer config, approved gate digest match against the provided prompt/system/context, and a project secret. It calls the writer Provider and writes the draft. Execution metadata does not store prompt text, context text, Memory Bank text, Planning Library text, generated draft text, Provider raw responses, request bodies, plaintext execution tokens, plaintext secrets, or secret values. It does not auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, or delete files. Tests patch the Chutes client and do not make a real network call.

## 2026-05-19: MVP-27.1 Real Execution Hardening

Decision: Harden the real execution CLI prompt path and add a read-only postcheck after real execution.

Rationale: The first live run showed that shell-fed prompts can include a trailing newline and fail the exact gate digest check before any network request. After a real run, operators also need a machine-readable read-only postcheck that confirms the draft stayed uncommitted.

Impact: `execute-final-provider-real --prompt-stdin` now strips shell newline characters before exact gate comparison. `postcheck-final-provider-real-execution` and `postcheck_final_provider_real_execution` verify an existing execution artifact, linked draft, no confirmed chapter, no auto-commit boundary, and metadata-only safety flags. The postcheck is read-only: it does not call Providers, read secret values, return draft content, mutate drafts, update Memory Bank/RAG/export, create DOCX, add UI, delete files, or auto-commit.

## 2026-05-19: MVP-27.2 Reasoning Leak Review Guard

Decision: Add a `review-draft` guard that detects reasoning markup in draft content before any scorer Provider call.

Rationale: The first real Chutes draft contained `<think>...</think>` reasoning text. This must be treated as a blocking quality/safety defect so such drafts cannot move toward acceptance or commit by accident.

Impact: `DraftReviewService.review_draft` now checks draft content for `<think` or `</think>` before calling the scorer. When detected, it writes a metadata-only `local_guard` review, records issue code `reasoning_leak_detected`, sets decision `needs_revision` with reason code `reasoning_leak`, and updates chapter workflow to `needs_revision`. The guard does not call Providers, does not store leaked reasoning text in review artifacts/indexes, does not overwrite drafts, does not auto-create revision drafts, does not auto-commit, and does not update Memory Bank/RAG/export.

## 2026-05-19: MVP-27.3 Provider Response Sanitizer

Decision: Sanitize Provider output before draft content is saved.

Rationale: Repeated Chutes/Qwen tests showed that the model may emit `<think></think>` even when the prompt forbids it. The stable backend solution is to filter reasoning markup at the acceptance boundary before UI/read/commit flows see saved draft content.

Impact: `DraftGenerationService.generate_draft` now removes `<think>...</think>` reasoning blocks and standalone `<think>` tags from Provider response text before writing `data/drafts/*.json`. The draft artifact records only sanitizer metadata under `request_summary.response_sanitizer`, including whether reasoning markup was detected and how many blocks/tags/chars were removed. It does not store the removed reasoning text, overwrite existing drafts, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, or delete files.

## 2026-05-19: MVP-27.4 Sample-Only Commit Blocker

Decision: Treat smoke-test draft reviews as explicitly non-committable even if their review status is accidentally marked `accepted`.

Rationale: Live Provider smoke tests are useful evidence for the execution and sanitizer chain, but they are not chapter-ready story material. The commit gate should preserve that operator intent as a hard backend rule, not rely only on the current review status.

Impact: `accepted_review_commit_gate(...)` now rejects accepted reviews whose `reason_code` is `smoke_test_only` before writing confirmed chapters, checkpoints, commit logs, or draft status changes. The latest live Chutes sample was marked `needs_revision` with `reason_code=smoke_test_only` and remains a test sample only. This path does not overwrite drafts, auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, call Providers, or delete files.

## 2026-05-22: MVP-28 Provider Live Smoke Test Harness

Decision: Add a persistent metadata-only Provider connectivity smoke-test harness separate from novel draft generation.

Rationale: After the Chutes integration was proven, future checks should test infrastructure rather than generate story material. A dedicated smoke-test artifact makes Provider connectivity repeatable and auditable while preventing test responses from entering draft, review, commit, Memory Bank, RAG, export, DOCX, or UI flows.

Impact: `ProviderSmokeTestService`, `run-provider-smoke-test`, `list-provider-smoke-tests`, and `read-provider-smoke-test` write/read `data/provider_smoke_tests/*.json` plus `data/provider_smoke_tests_index.json`. The command calls the existing safe `provider_real_test` path when the user starts it and stores only metadata such as status code, finish reason, usage, response character count, provider/model, host, and safety flags. Artifacts classify every smoke test as `sample_only` and `non_committable`, create no drafts or confirmed chapters, store no prompt text, system prompt text, response text, raw request bodies, or plaintext secrets, and do not update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, or delete files.

## 2026-05-22: MVP-29 Provider Smoke Test Audit Gate

Decision: Extend `audit-project` and `prepublish-check` to validate Provider smoke-test artifacts.

Rationale: Smoke-test artifacts are now durable project state. They need the same safety envelope as other backend gates so connectivity checks cannot quietly accumulate prompt text, response text, secrets, draft links, or commit-like metadata.

Impact: `audit-project` now scans `data/provider_smoke_tests_index.json` and `data/provider_smoke_tests/*.json` for prompt/secret/content-like strings, forbidden text-bearing keys, invalid statuses, invalid passed/network-attempted state, invalid sample-only/non-committable classification, and invalid safety flags. `prepublish-check` treats smoke-test text leaks, invalid status, invalid passed state, invalid classification, and invalid safety flags as blockers. The audit remains read-only and does not call Providers, delete files, write drafts, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, or add UI.

## 2026-05-22: MVP-30 Provider Config Snapshot / Drift Audit

Decision: Record safe Provider config snapshots in new smoke-test artifacts and warn when current config drifts from the latest passed smoke test.

Rationale: A Provider smoke test proves connectivity for a specific provider/model/host/key reference. If those change later, operators need a visible warning before interpreting an old smoke result as evidence for the current config.

Impact: New Provider smoke-test artifacts include `config_snapshot` with role, provider, model, base URL host, `api_key_ref`, secret name, and api-key-reference presence; they do not store secret values. `audit-project` compares the latest passed smoke test that has a snapshot against current role config and emits `provider_smoke_test_config_drift` when provider/model/host/api-key reference differs. `prepublish-check` treats this drift as a warning, not a blocker. This path does not call Providers, clear or rotate keys, write drafts, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, or delete files.

## 2026-05-22: MVP-31 Runtime Project Health Summary And Upload Ignore Guard

Decision: Add a metadata-only `project-health` read model and extend upload ignore/prepublish coverage for build and coverage artifacts.

Rationale: Before any future upload or publication, operators need one concise backend health report that joins public project state, project audit, and repository prepublish readiness without exposing draft text, prompt text, Provider responses, or secrets. `.gitignore` should also block ordinary Python build/coverage artifacts so accidental upload risk is reduced before the final prepublish gate runs.

Impact: `project_health(project_id, repo_root=None)` and CLI `project-health` summarize Provider config, draft/review/commit counts, latest smoke-test metadata, audit findings, and upload readiness. `prepublish-check` now requires ignore coverage for `build/`, `dist/`, `*.egg-info/`, `*.spec`, `.coverage`, and `htmlcov/`, skips generated build/coverage directories while scanning the source tree, and excludes non-publishing Provider readiness warnings such as disabled adapters or missing local Provider secrets. The health report is read-only and metadata-only. It does not call Providers, read secret values, clear or rotate keys, write drafts, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or modify runtime project state.

## 2026-05-22: MVP-32 Desktop Launcher And Windows EXE Packaging

Decision: Add a local desktop launcher and package it as a Windows executable.

Rationale: The backend MVP needs a normal application entry point for day-to-day use. A lightweight desktop shell can expose project selection, metadata-only health checks, upload readiness, and safe local actions while preserving the real-LLM authorization boundary.

Impact: `desktop_app.py` adds a Tkinter launcher with project-root selection, project list, project-health summary, Provider safety summary, prepublish check, model configuration, explicit writer-facing Provider actions, and local folder opening. `packaging/desktop_launcher.py` is the PyInstaller entry point. `scripts/generate_windows_icon.py` creates a blank manuscript-paper-and-pen icon as a 1024 PNG and a multi-size Windows `.ico` with 16/20/24/32/40/48/64/128/256 px entries. The desktop launcher does not expose hidden automatic real Provider execution, does not call LLMs on startup, and does not change real Provider safety state without explicit operator action. Product UI may expose explicit user-triggered calls to configured providers; Codex implementation/QA must not run those calls without user authorization.
