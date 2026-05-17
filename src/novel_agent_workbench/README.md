# novel_agent_workbench Package

This package contains the new implementation code.

Current MVP-0 module:

- `storage.py`: safe local project storage kernel, checkpoint ZIP creation, reversible checkpoint restore, and backend-only project registry.
- `config.py`: default project config, schema version, and placeholder data structures.
- `providers.py`: writer/scorer/reviser config parsing, `project_secret.*` validation, fake connection tests, Provider request/response interface, deterministic Mock Provider, and safe provider call logging.
