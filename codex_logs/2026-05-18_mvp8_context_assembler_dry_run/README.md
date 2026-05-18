# MVP-8 Context Assembler Dry-Run

Date: 2026-05-18, Asia/Shanghai.

## Trigger

User asked to mark Memory Bank priority as an important hard problem, then continue the next step.

## Important Issue Logged

Created:

```text
codex_docs/IMPORTANT_OPEN_ISSUES.md
```

Issue:

```text
OI-001 Memory Bank Priority Is Local Logic, Not LLM API Logic
```

## Implementation

Added a metadata-only Context Assembler dry-run.

New module:

```text
src/novel_agent_workbench/context_assembler.py
```

New CLI:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> context-assembly-dry-run <project_id> --max-context-tokens 4096
```

The dry-run returns:

```text
token_budget
provider_api_boundary
candidates
selected
skipped
warnings
```

## Safety Boundary

- No Provider call.
- No artifact write.
- No prompt text returned.
- No chapter text returned.
- No Memory Bank text returned.
- No plaintext secrets returned.
- No Memory Bank/RAG/export mutation.
- No draft or confirmed chapter mutation.

## Files Changed

```text
src/novel_agent_workbench/context_assembler.py
src/novel_agent_workbench/application_service.py
src/novel_agent_workbench/cli.py
src/novel_agent_workbench/__init__.py
tests/test_context_assembler.py
README.md
codex_docs/README.md
codex_docs/IMPORTANT_OPEN_ISSUES.md
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
py -3.13 -m unittest tests.test_context_assembler tests.test_context_queue tests.test_application_service
```

Result:

```text
Ran 26 tests in 3.006s
OK
```

Full regression:

```powershell
py -3.13 -m unittest discover -s tests
```

Result: pending.

```text
Ran 164 tests in 11.751s
OK
```

Secret fragment scan:

```powershell
rg <known Chutes key fragments> I:\AI-NOVEL\novel_agent_workbench I:\AI-NOVEL\PROJECT_INDEX.md
```

Result: no matches.

## Next Step

Commit this slice. Next likely phase: MVP-8.5 manual formal context apply queue.
