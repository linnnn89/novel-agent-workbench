# MVP-7 Formal Context Policy

Date: 2026-05-18, Asia/Shanghai.

## User Decision

Formal context priority:

```text
世界观设定 > 人物关系 > 章节摘要 > 文风记忆 > 剧情伏笔
```

Stable internal ids:

```text
world_building
character_relationships
chapter_summary
style_memory
foreshadowing
```

## Implementation

Added `formal_context_policy` to `context_policy` in project config defaults:

```text
mode=manual_preview_first
priority_order=[world_building, character_relationships, chapter_summary, style_memory, foreshadowing]
auto_extract=false for every category
```

Context preview artifacts now include:

```text
target_plan.formal_context.priority_order
```

This is metadata only.

## Files Changed

```text
src/novel_agent_workbench/config.py
src/novel_agent_workbench/context_previews.py
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
py -3.13 -m unittest tests.test_project_foundation tests.test_context_queue tests.test_application_service
```

Result:

```text
Ran 26 tests in 1.864s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 156 tests in 10.541s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Boundaries

- No automatic extraction.
- No Provider call.
- No Memory Bank mutation.
- No RAG mutation.
- No export mutation.
- No UI.
- Old reference project untouched.

## Next Step

Commit this slice, then continue to MVP-7.5 formal context extraction plan schema.
