# Codex Docs

This folder is the durable project brain for `novel_agent_workbench`.

Current documents:

- `PROJECT_CHARTER.md`: product boundary and non-negotiable engineering rules.
- `DECISIONS.md`: chronological decision log.
- `IMPORTANT_OPEN_ISSUES.md`: high-priority architectural risks that must not be lost.
- `DESKTOP_APP_BUILD.md`: Windows desktop launcher and EXE build notes.

Current high-priority architecture issue:

```text
OI-001 Memory Bank priority is local Context Assembler logic, not an LLM API feature.
OI-002 Final real Provider safety-disable reminder before production use.
```

Every meaningful design decision, file creation, implementation change, test result, or failure recovery must be written here or under `codex_logs/`.
