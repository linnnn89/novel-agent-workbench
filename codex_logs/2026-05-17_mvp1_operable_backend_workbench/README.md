# MVP-1 Operable Backend Workbench Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Complete MVP-1 operable backend workbench preparation: CLI Quickstart, Application Service contract, read-only safety audit, and Provider preflight boundary.

## Scope

Allowed:

```text
operator documentation
application service contract documentation
read-only audit module
audit-project CLI command
contract/audit/CLI tests
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

## CLI Usage

Quickstart:

```text
codex_docs\CLI_QUICKSTART.md
```

One-command smoke:

```powershell
$env:PYTHONPATH="I:\AI-NOVEL\novel_agent_workbench\src"
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test smoke demo_project --prompt "Write a short mock opening." --commit
```

Audit:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test audit-project demo_project
```

## Application Service Contract

Contract:

```text
codex_docs\APPLICATION_SERVICE_CONTRACT.md
```

The contract records `WorkbenchApplicationService` methods, content-returning methods, metadata-only methods, Provider error types, and future real Provider safety rules.

## Audit Rules

`audit_project(...)` checks:

```text
config.json for sk-* or raw api_key key
provider_call_log.json for prompt-like fields or secret patterns
commit_log.json for content-like fields or secret patterns
checkpoint ZIPs for default inclusion of data/secrets.local.json
public_project_state for prompt/content/secrets patterns
```

Audit is read-only. It reports:

```text
ok
project_id
findings
checked_paths
```

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 67 tests
OK
```

Manual audit command:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_cli_smoke_test audit-project cli_demo
```

Manual audit result:

```text
ok: true
findings: []
```

## Files Changed

```text
README.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\CLI_QUICKSTART.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_operable_backend_workbench\README.md
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\audit.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_application_service.py
tests\test_audit.py
tests\test_cli.py
```

## Known Not Implemented

- No frontend.
- No HTTP server.
- No real Provider API.
- No Memory Bank/RAG/export automatic update.
- No DOCX.
- No scoring/revision pipeline.

## Next Step

Prepare MVP-2 real Provider adapter skeleton in mock-only disabled mode: define provider adapter registry, environment-free secret lookup from `secrets.local.json`, and no-network contract tests before any actual HTTP request code is allowed.
