# MVP-0 ProjectRegistry Implementation Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Add project registry and default `workspace_projects` routing for multiple local projects.

## Design Decision

Add a backend-only `ProjectRegistry` in `storage.py`.

Responsibilities:

- resolve default runtime projects root,
- create project,
- open project,
- list projects,
- maintain root-level `registry.json`,
- use existing atomic JSON write helper pattern,
- never delete projects.

## Default Routing

Default real runtime root:

```text
I:\AI-NOVEL\novel_agent_workbench\workspace_projects
```

Tests may still use isolated temporary roots.

## Planned API

```python
ProjectRegistry.default()
ProjectRegistry.open(projects_root)
registry.create_project(project_id, title="")
registry.open_project(project_id)
registry.list_projects()
```

## Verification Plan

- Default registry root resolves to `workspace_projects`.
- Creating projects initializes project layout.
- Listing projects returns stable registry entries sorted by update time/name.
- Opening existing project returns `ProjectStore`.
- Unsafe project ids are rejected.
- No hard delete API exists.

## Verification Result

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 18 tests in 0.218s
OK
```

## Files Changed

```text
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\storage.py
tests\test_project_registry.py
README.md
src\novel_agent_workbench\README.md
tests\README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp0_project_registry\README.md
```

## Notes

No UI, LLM, chapter-generation, scoring, or DOCX work was added. The old reference project was not modified.
