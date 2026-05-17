# MVP-0 Research Decision Log

Date: 2026-05-17, Asia/Shanghai.

## User Request

The user is not a programmer and asked Codex to search public expert/community experience, then independently decide the first MVP-0 engineering slice.

## Sources Checked

- Anthropic Claude Code best practices: verification, explore-plan-code, context management, checkpoints, and avoiding trust-without-tests.
- Anthropic CLAUDE.md guidance: keep project instructions short, signal-dense, and include hard constraints, commands, gotchas, and architecture.
- Python official documentation: `os.replace()` supports atomic replacement when successful.
- Python official documentation: avoid insecure temporary filename patterns; use secure temp file APIs.
- SQLite atomic commit documentation: robust local systems depend on atomic commit/rollback behavior.

## Decision

MVP-0 should start with the local storage kernel, not UI, LLM provider integration, or chapter generation.

## Recommended First Slice

Build and test:

```text
ProjectStore
atomic JSON write
.bak backup creation
project directory initialization
basic project lock
secrets.local.json separate from normal config
small unit tests for each safety behavior
```

## Rationale

AI coding-agent best practice strongly favors objective verification. Storage safety is easy to verify with deterministic tests. UI quality and LLM writing quality are more subjective and should wait until data loss and state pollution risks are controlled.

The reference project's known risk is direct generation into confirmed state. Therefore the new project should first build a reliable persistence layer that future draft/confirmed separation can depend on.

## Deferred

Not in first slice:

- frontend UI,
- LLM provider calls,
- prompt engineering,
- chapter generation,
- scoring/revision loop,
- DOCX export.

## Sources

```text
https://code.claude.com/docs/en/best-practices
https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts
https://docs.python.org/3.11/library/os.html#os.replace
https://docs.python.org/3/library/tempfile.html
https://www.sqlite.org/atomiccommit.html
```

## Next Step

Create the clean Python package skeleton and tests for `ProjectStore`.
