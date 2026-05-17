# MVP-0 Verification Mode Log

Date: 2026-05-17, Asia/Shanghai.

## Decision

The user accepted MVP-0 as backend/test-only with no UI.

## Scope Consequence

MVP-0 should implement and verify the storage kernel first:

```text
ProjectStore
atomic JSON write
.bak backup
project initialization
project lock
secrets.local.json separated from config.json
unit tests
```

## Deferred

```text
frontend
LLM provider calls
prompt design
chapter generation
scoring and revision UI
DOCX export
```

## Next Step

Create the clean Python package skeleton and implement the first storage tests.
