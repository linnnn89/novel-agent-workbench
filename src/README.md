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
- audit checks confirmed chapter consistency and revision request/generated draft consistency.

Do not copy large chunks from the reference project blindly. If reference code is reused, copy only reviewed modules or patterns and document the reason in `codex_docs/DECISIONS.md` or `codex_logs/`.
