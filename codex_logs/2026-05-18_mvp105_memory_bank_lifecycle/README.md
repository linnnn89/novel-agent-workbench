# MVP-10.5 Memory Bank Lifecycle

Date: 2026-05-18, Asia/Shanghai.

## Goal

Add reversible lifecycle controls for individual Memory Bank items before final prompt rendering exists.

This phase lets an operator disable or re-enable a Memory Bank item without deleting it or rewriting its text.

## Files Changed

```text
src/novel_agent_workbench/memory_bank.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
src/novel_agent_workbench/context_assembler.py
src/novel_agent_workbench/project_state.py
tests/test_context_assembler.py
README.md
src/README.md
tests/README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
codex_logs/README.md
I:/AI-NOVEL/PROJECT_INDEX.md
```

## Design

`MemoryBankService.set_memory_item_enabled(...)` writes lifecycle metadata:

```text
enabled=true/false
lifecycle_status=active/disabled
lifecycle_reason_code=<safe code>
```

It creates a checkpoint before writing:

```text
pre_memory_lifecycle_update
```

Reason codes are optional and restricted to ASCII letters, numbers, `_`, and `-`.

## CLI

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> disable-memory-item <project_id> <memory_id> --reason-code duplicate_world_book
py -3.13 -m novel_agent_workbench.cli --projects-root <root> enable-memory-item <project_id> <memory_id> --reason-code manual_restore
```

## Context Assembly Boundary

Disabled Memory Bank items remain in `memory_bank.json`, but Context Assembler dry-run skips them:

```text
skip_reason=memory_item_disabled
```

The dry-run remains metadata-only and does not return Memory Bank text.

## Safety Boundary

- No file deletion.
- No Memory Bank text rewrite during lifecycle changes.
- No Provider calls.
- No world book/RAG/export updates.
- No draft or confirmed chapter mutation.
- No prompt rendering.
- Default outputs remain metadata-only.

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_context_assembler
```

Result:

```text
Ran 20 tests
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 180 tests
OK
```

Secret scan for the previously supplied Chutes key fragments:

```text
No matches.
```

## Next Step

MVP-11 should add a still-safe prompt assembly preview that can render a redacted or test-only context package from enabled manual Memory Bank items, without calling Providers and without exposing secrets.
