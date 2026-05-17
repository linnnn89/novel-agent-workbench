# novel_agent_workbench Package

This package contains the new implementation code.

Current backend modules:

- `application_service.py`: stable backend facade for future CLI, HTTP, or UI layers.
- `cli.py`: backend-only command-line runner for smoke testing and scripted local workflows.
- `drafts.py`: backend-only Draft Generation Service that writes mock writer output into draft artifacts without confirmed-state side effects.
- `project_state.py`: UI-safe backend state summary with masked secrets and no prompt/chapter content.
- `storage.py`: safe local project storage kernel, checkpoint ZIP creation, reversible checkpoint restore, and backend-only project registry.
- `config.py`: default project config, schema version, and placeholder data structures.
- `providers.py`: writer/scorer/reviser config parsing, `project_secret.*` validation, fake connection tests, Provider request/response interface, deterministic Mock Provider, and safe provider call logging.
