# MVP-7.6 World Book Overlap Policy

Date: 2026-05-18, Asia/Shanghai.

## Trigger

User asked whether `世界观设定` would duplicate the future world book and waste context tokens.

## Decision

Yes, there is a real overlap risk.

Separation:

```text
world book = stable canonical setting facts
Memory Bank world_building = compact continuity cues from confirmed chapters
```

Default option:

```text
world_building memory_weight=1.0
world_book_overlap_policy=reduce_memory_when_world_book_enabled
world_book_enabled_memory_weight=0.35
```

When `context_policy.world_book_enabled=true`, formal context plans set:

```text
world_building memory_weight=0.35
recommendation=reduce_memory_weight_world_book_enabled
```

## Files Changed

```text
src/novel_agent_workbench/config.py
src/novel_agent_workbench/formal_context.py
tests/test_project_foundation.py
tests/test_context_queue.py
README.md
codex_docs/DECISIONS.md
codex_docs/PROJECT_CHARTER.md
codex_docs/APPLICATION_SERVICE_CONTRACT.md
codex_docs/CLI_QUICKSTART.md
src/README.md
tests/README.md
codex_logs/README.md
I:\AI-NOVEL\PROJECT_INDEX.md
```

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_project_foundation tests.test_context_queue
```

Result:

```text
Ran 20 tests in 2.016s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result: pending.

```text
Ran 160 tests in 11.967s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Boundaries

- No world book implementation.
- No Memory Bank write.
- No automatic extraction.
- No Provider call.
- No UI.
- Old reference project untouched.
