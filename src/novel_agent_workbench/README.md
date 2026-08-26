# novel_agent_workbench Package

This package contains the new implementation code.

Current backend modules:

- `application_service.py`: stable backend facade for future CLI, HTTP, or UI layers.
- `audit.py`: read-only safety audit for config, logs, checkpoints, and public state.
- `chapters.py`: metadata-only chapter workflow state for planned/drafting/draft_ready/review_ready/review_accepted/needs_revision/revision_requested/revision_draft_ready/committed/blocked.
- `cli.py`: backend-only command-line runner for smoke testing and scripted local workflows.
- `drafts.py`: backend-only Draft Generation Service that writes mock writer output into draft artifacts without confirmed-state side effects.
- `project_state.py`: UI-safe backend state summary with masked secrets and no prompt/chapter content.
- `reviews.py`: metadata-only Draft Review / Quality Check service and one-shot manual review decision layer without storing draft content, prompts, raw responses, free-text notes, or secrets.
- `revisions.py`: metadata-only Revision Request skeleton created only from `needs_revision` decisions, without LLM calls or draft mutation.
- `revisions.py`: also owns mock revision draft candidate generation from revision requests, using only the local mock reviser, never overwriting source drafts, and never auto-committing.
- `runbooks.py`: safe operator runbooks for controlled real Provider workflows, currently `chutes-generate-once`.
- `storage.py`: safe local project storage kernel, checkpoint ZIP creation, reversible checkpoint restore, and backend-only project registry.
- `config.py`: default project config, schema version, and placeholder data structures.
- `providers.py`: writer/scorer/reviser config parsing, Provider adapter registry, `project_secret.*` resolver, safe config/secret write helpers, fake/no-network status checks, dry-run request summary translation, OpenAI-compatible real request client, Provider request/response interface, deterministic Mock Provider, and safe provider call logging.
