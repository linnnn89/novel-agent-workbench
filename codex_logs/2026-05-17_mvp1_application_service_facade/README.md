# MVP-1 Application Service Facade Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Add a minimal backend application service facade for future CLI, HTTP, or UI integration.

## Scope

Allowed:

```text
project creation
project listing
safe project state
mock writer configuration
draft generation
draft list/read
explicit draft commit
confirmed chapter list/read
unit tests
documentation updates
```

Not allowed:

```text
frontend
HTTP server
real LLM provider calls
automatic Memory Bank updates
automatic RAG updates
automatic export updates
DOCX export
reference project edits
```

## Design

Added `application_service.py` with:

- `WorkbenchApplicationService.default()`
- `WorkbenchApplicationService.open(projects_root)`
- `create_project(...)`
- `list_projects()`
- `project_state(project_id)`
- `configure_mock_writer(project_id, ...)`
- `generate_draft(...)`
- `list_drafts(project_id)`
- `read_draft(project_id, draft_id)`
- `commit_draft(project_id, draft_id)`
- `list_confirmed_chapters(project_id)`
- `read_confirmed_chapter(project_id, chapter_id)`

The facade is intentionally thin. It delegates to:

```text
ProjectRegistry
DraftGenerationService
public_project_state
set_model_role_config
```

## Safety Boundary

The facade does not return prompt text or plaintext secrets through `project_state(...)`.

`read_draft(...)` returns generated draft content for review, but draft artifacts still do not store original prompt text or secrets.

`commit_draft(...)` remains explicit. No facade method auto-commits after generation.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 58 tests
OK
```

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_application_service_facade\README.md
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_application_service.py
```

## Known Not Implemented

- No frontend.
- No HTTP server.
- No real Provider API.
- No Memory Bank/RAG/export automatic update.
- No DOCX.

## Next Step

Add a minimal command-line smoke script or local API adapter around `WorkbenchApplicationService`, still backend-only, so a human can run the full project -> draft -> commit loop without writing Python code.
