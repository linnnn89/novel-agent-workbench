# novel_agent_workbench Package

This package contains the new implementation code.

Current backend modules:

- `application_service.py`: stable backend facade for future CLI, HTTP, or UI layers.
- `audit.py`: read-only safety audit for config, logs, checkpoints, and public state.
- `cli.py`: backend-only command-line runner for smoke testing and scripted local workflows.
- `drafts.py`: backend-only Draft Generation Service that writes mock writer output into draft artifacts without confirmed-state side effects.
- `project_state.py`: UI-safe backend state summary with masked secrets and no prompt/chapter content.
- `runbooks.py`: safe operator runbooks for controlled real Provider workflows, currently `chutes-generate-once`.
- `storage.py`: safe local project storage kernel, checkpoint ZIP creation, reversible checkpoint restore, and backend-only project registry.
- `config.py`: default project config, schema version, and placeholder data structures.
- `providers.py`: writer/scorer/reviser config parsing, Provider adapter registry, `project_secret.*` resolver, safe config/secret write helpers, fake/no-network status checks, dry-run request summary translation, explicit Chutes real-test metadata path, controlled Chutes writer-only real draft generation gate, Provider request/response interface, deterministic Mock Provider, disabled real-provider placeholders including Chutes, and safe provider call logging.
