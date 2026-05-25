# Source Code

This folder will contain the new application source code.

Current package modules include:

```text
novel_agent_workbench.storage
novel_agent_workbench.providers
novel_agent_workbench.drafts
novel_agent_workbench.reviews
novel_agent_workbench.revisions
novel_agent_workbench.revision_candidates
novel_agent_workbench.chapters
novel_agent_workbench.context_queue
novel_agent_workbench.context_previews
novel_agent_workbench.formal_context
novel_agent_workbench.formal_context_tasks
novel_agent_workbench.context_assembler
novel_agent_workbench.memory_apply_preview
novel_agent_workbench.memory_bank
novel_agent_workbench.planning_library
novel_agent_workbench.final_assembly_gates
novel_agent_workbench.final_provider_authorizations
novel_agent_workbench.final_provider_execution_attempts
novel_agent_workbench.final_provider_execution_preflights
novel_agent_workbench.final_provider_real_executions
novel_agent_workbench.final_provider_real_execution_readiness
novel_agent_workbench.final_provider_runbooks
novel_agent_workbench.corpus_boundaries
novel_agent_workbench.corpus_profiler
novel_agent_workbench.corpus_profiles
novel_agent_workbench.corpus_samples
novel_agent_workbench.publication
novel_agent_workbench.self_style
novel_agent_workbench.manual_rewrite_comparison
novel_agent_workbench.audit
novel_agent_workbench.application_service
novel_agent_workbench.cli
novel_agent_workbench.desktop_app
```

Current safety hardening:

- Provider/API boundary: the product can call configured real model providers from explicit user-triggered actions. Codex implementation and automated tests must not call real providers unless the user authorizes that specific run.
- `secrets.local.json` writes are atomic but intentionally do not create plaintext `.bak` backups.
- revision draft generation is explicitly mock-only in this phase.
- revision candidate comparison is read-only and metadata-only.
- context update queue entries are metadata-only and do not mutate Memory Bank/RAG/export.
- context update preview artifacts are metadata-only plans and do not copy chapter text.
- formal context policy priority is stored in config and copied into preview metadata only.
- formal context extraction plans are metadata-only category work plans and do not extract or store chapter text.
- world-building context has a world-book overlap policy that can reduce Memory Bank weight when the future world book is enabled.
- context assembler dry-run is metadata-only and previews local token-budget selection before Provider calls.
- formal context task queue is metadata-only and does not apply Memory Bank/RAG/export updates.
- memory apply previews are metadata-only and do not write `memory_bank.json`.
- memory apply commit gate writes only placeholder Memory Bank entries with empty text and `manual_text_required` status.
- manual Memory Bank text fill/edit is explicit, checkpointed, rejects empty/secret-like values, stores a visible target token value as prompt guidance, and does not auto-update RAG/export.
- Memory Bank item lifecycle controls can explicitly disable/enable one item; disabled items remain on disk but are skipped by Context Assembler dry-run.
- context package preview is read-only, uses enabled manual Memory Bank text only, and defaults to metadata-only output unless text inclusion is explicit.
- prompt render dry-run is read-only and redacts operator prompt/context text by default while reporting the future message envelope shape.
- context-aware draft generation is mock-only in this phase and stores only safe context generation metadata in draft artifacts and indexes.
- audit checks confirmed chapter consistency, revision request/generated draft consistency, and context-aware draft metadata safety.
- corpus profiler is read-only and metadata-only; it may report rough structure statistics and candidate-name frequency, but it does not write project files, call Providers, or copy chapter/source text.
- corpus profile artifacts are explicit project writes, but persist only conservative metadata and exclude external source paths plus candidate-name text by default.
- corpus boundary indexes persist no-text chapter line and character offsets only; they do not store heading text, excerpts, or external source paths.
- corpus samples are temporary testing artifacts only; they may contain bounded real text, are marked `test_only` and `publish_blocker`, are redacted by default reads, and cause `audit-project` to fail until removed from publishable runtime state.
- prepublish checks are read-only and scan the source tree plus runtime projects for publish blockers such as secrets, `.env` files, corpus samples, and high-risk audit findings. Provider disabled/missing-secret runtime findings are warnings, not source publication blockers.
- self style baselines read only confirmed chapters and persist numeric/statistical style metrics. They do not use external corpora, do not call Providers, and do not store chapter text, prompt text, or plaintext secrets.
- draft style checks compare one draft to a self-style baseline with local metrics only. They are scene-mode-aware hints, not strict grades. They store issue metadata, not draft text, and they do not auto-revise, auto-commit, or update Memory Bank/RAG/export.
- style check policy lives in `config.json` under `context_policy.style_check_policy`, so the future UI can disable style checks, disable calibration, hide hints, and keep auto-revision off.
- style suggestions convert a style check into manual advice metadata under `data/style_suggestions/`. They do not call Providers, read external corpora, modify drafts, create revision requests, commit chapters, or update Memory Bank/RAG/export.
- manual style suggestion decisions update only the suggestion artifact/index `decision` metadata. They do not apply edits, create revision requests, mutate drafts, commit chapters, or update Memory Bank/RAG/export.
- manual rewrite tasks live under `data/manual_rewrite_tasks/` and are created only from `needs_manual_rewrite` style suggestion decisions. They are human workspace metadata only; they do not call Providers, create drafts, modify existing drafts, commit chapters, or update Memory Bank/RAG/export.
- manual rewrite draft submission creates a new draft candidate from explicit human text. It marks the source task `done` and records `submitted_draft_id`; it does not overwrite source drafts, call Providers, auto-commit, create revision requests, or update Memory Bank/RAG/export.
- manual rewrite comparisons live under `data/manual_rewrite_comparisons/` and store only ids, structural metrics, deltas, link checks, safety flags, and explicit selection decisions. They do not store source/submitted draft text, call Providers, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.
- review handoffs live under `data/review_handoffs/` and can be created only from manual rewrite comparisons already marked `selected_for_review`. They route the selected draft candidate to a later explicit review step without calling Providers, auto-reviewing, auto-committing, creating confirmed chapters, or updating Memory Bank/RAG/export.
- Planning Library lives in `data/planning_library.json` and stores manual planning references only. Default list/read/state/context outputs are metadata-only; text appears only when explicit include flags are used. Inactive or disabled planning items are skipped by context selection.
- review-draft guard detects `manual_rewrite_draft_candidate` drafts and requires either a `selected_for_review` comparison or a `pending_review` handoff before any scorer Provider call. Ordinary draft review is unaffected.
- reasoning leak guard detects `<think>` markup during `review-draft`, skips scorer Provider calls, writes a metadata-only `local_guard` review, and automatically marks the draft/chapter as `needs_revision`.
- Provider response sanitizer removes `<think>...</think>` reasoning blocks before draft content is saved, so future UI/read/commit flows consume clean draft text while retaining only sanitizer metadata.
- final assembly gates live under `data/final_assembly_gates/` and require explicit approval before any future real context-aware Provider path. Gate artifacts store prompt/context hashes and metadata only, never prompt text, context text, Memory Bank text, Planning Library text, draft content, or secrets.
- final Provider runbooks live under `data/final_provider_runbooks/` and can be created only from approved final assembly gates. They stop at `pending_operator_authorization`, store metadata/digests/checklists only, and do not call real LLMs, write drafts, or update Memory Bank/RAG/export.
- final Provider authorizations live under `data/final_provider_authorizations/` and can be created only from pending runbooks. They create a no-secrets checkpoint summary, stop at `authorized_pending_execution`, and still do not enable/call real Providers or write drafts.
- final Provider execution preflights live under `data/final_provider_execution_preflights/` and verify the gate/runbook/authorization/current-provider chain. They may pass or block, but they remain preflight-only and never enable/call real Providers or write drafts.
- final Provider execution attempts live under `data/final_provider_execution_attempts/` and can be created only from passed zero-issue preflights. The MVP-25 stub path deliberately aborts with `aborted_real_llm_disabled` and records only safety metadata; the separate real execution path performs explicit user-authorized Provider calls.
- final Provider real execution readiness reports live under `data/final_provider_real_execution_readiness/` and can be created only from aborted execution attempts. They check current Chutes config and key presence as metadata, then stop at manual real-LLM authorization without reading secret values, enabling Providers, calling LLMs, or writing drafts.
- final Provider real executions live under `data/final_provider_real_executions/` and require explicit network authorization plus a ready report. They re-check gate digests, temporarily enable Chutes, call the writer Provider, write one new draft, and disable the real Provider gate afterward; they do not auto-commit or update Memory Bank/RAG/export.
- final Provider real execution postchecks are read-only and verify the execution artifact, linked draft, disabled writer real-generation gate, unconfirmed chapter state, and metadata-only safety flags after a real run.
- review handoffs move from `pending_review` to `review_created` after a successful guarded review consumes the handoff. This updates metadata only and does not auto-commit, mutate drafts, or update Memory Bank/RAG/export.
- confirmed chapter promotion now requires an accepted review for the same draft. Commit-gate failures are no-side-effect refusals, so an accidental early commit attempt does not block the chapter or prevent later review.
- desktop_app is a local Tkinter launcher for project selection, project health, upload readiness checks, model configuration, and writer-facing actions. It must not call LLMs on startup or in hidden background flows; explicit user-triggered actions may call configured providers.

Do not copy large chunks from the reference project blindly. If reference code is reused, copy only reviewed modules or patterns and document the reason in `codex_docs/DECISIONS.md` or `codex_logs/`.
