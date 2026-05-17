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

## 2026-05-17: MVP-2 Chutes Controlled Real Draft Gate

Decision: Allow `chutes_openai` to generate writer drafts only through an explicit project-level gate.

Reason: The workbench needs one real Provider path for end-to-end draft testing, but it must stay auditable, reversible, and unable to silently become normal generation for every role or Provider.

Impact: `enable-real-provider <project_id> writer --provider chutes_openai` writes `settings.real_generation_enabled=true`; `disable-real-provider` turns it off. `generate-draft` only reaches Chutes when the role is writer, the Provider is `chutes_openai`, the secret resolves from `secrets.local.json`, and audit has no key/prompt/content leak finding. Generated content is stored only in draft artifacts; provider logs, CLI output, and audit output remain metadata-only. No automatic commit, Memory Bank, RAG, export, UI, DOCX, or scoring work was added.
