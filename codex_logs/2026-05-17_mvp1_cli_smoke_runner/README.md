# MVP-1 CLI Smoke Runner Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Add a backend-only command-line runner around `WorkbenchApplicationService`.

## Scope

Allowed:

```text
local CLI parser
JSON command output
project creation/listing
safe state query
mock writer configuration
draft generation/list/read
explicit draft commit
confirmed chapter list/read
one-command smoke flow
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

Added `cli.py`.

Primary local run shape:

```powershell
$env:PYTHONPATH="I:\AI-NOVEL\novel_agent_workbench\src"
py -3.13 -m novel_agent_workbench.cli --projects-root <projects-root> smoke <project-id> --prompt "..." --commit
```

The CLI exposes:

```text
create-project
list-projects
state
configure-mock-writer
generate-draft
list-drafts
read-draft
commit-draft
list-confirmed
read-confirmed
smoke
```

`pyproject.toml` also declares a future installable script:

```text
novel-agent-workbench = novel_agent_workbench.cli:main
```

## Safety Boundary

The CLI delegates to `WorkbenchApplicationService`. It does not implement its own storage or generation logic.

The `smoke` command returns draft metadata, commit metadata, and safe project state. It does not return the original prompt text or plaintext secrets.

`read-draft` and `read-confirmed` are review commands and may return generated content, but generated artifacts still do not store original prompt text or secrets.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 61 tests
OK
```

Manual smoke command:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_cli_smoke_test smoke cli_demo --title "CLI Demo" --chapter-id chapter_001 --chapter-title Opening --prompt "private manual smoke prompt" --commit
```

Manual smoke result:

```text
ok: true
committed_chapter_count: 1
prompt text absent from JSON output
```

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_cli_smoke_runner\README.md
pyproject.toml
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_cli.py
```

## Known Not Implemented

- No frontend.
- No HTTP server.
- No real Provider API.
- No Memory Bank/RAG/export automatic update.
- No DOCX.

## Next Step

Add a small `docs/CLI_QUICKSTART.md` or batch/PowerShell wrapper only after deciding the preferred operator workflow. The backend CLI itself is now enough for smoke testing.
