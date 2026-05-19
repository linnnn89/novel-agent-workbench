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
novel_agent_workbench.corpus_boundaries
novel_agent_workbench.corpus_profiler
novel_agent_workbench.corpus_profiles
novel_agent_workbench.corpus_samples
novel_agent_workbench.publication
novel_agent_workbench.audit
novel_agent_workbench.application_service
novel_agent_workbench.cli
```

Current safety hardening:

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
- manual Memory Bank text fill/edit is explicit, checkpointed, bounded to 1200 characters, rejects secret-like values, and does not call Providers or auto-update RAG/export.
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

Do not copy large chunks from the reference project blindly. If reference code is reused, copy only reviewed modules or patterns and document the reason in `codex_docs/DECISIONS.md` or `codex_logs/`.
