# Source Code

This folder will contain the new application source code.

Current package modules include:

```text
novel_agent_workbench.storage
novel_agent_workbench.providers
novel_agent_workbench.drafts
novel_agent_workbench.reviews
novel_agent_workbench.revisions
novel_agent_workbench.chapters
novel_agent_workbench.audit
novel_agent_workbench.application_service
novel_agent_workbench.cli
```

Current safety hardening:

- `secrets.local.json` writes are atomic but intentionally do not create plaintext `.bak` backups.
- revision draft generation is explicitly mock-only in this phase.
- audit checks confirmed chapter consistency and revision request/generated draft consistency.

Do not copy large chunks from the reference project blindly. If reference code is reused, copy only reviewed modules or patterns and document the reason in `codex_docs/DECISIONS.md` or `codex_logs/`.
