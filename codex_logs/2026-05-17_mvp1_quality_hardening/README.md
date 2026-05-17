# MVP-1 Quality Hardening Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Harden the MVP-1 backend foundation after project review.

## Scope

Implemented:

```text
safe ASCII chapter_id validation
audit half-commit consistency checks
audit read-only public state path
Windows path normalization in audit
unit tests
documentation updates
```

Not implemented:

```text
frontend
real LLM provider
HTTP server
DOCX
Memory Bank/RAG/export automatic update
hard delete
```

## Safety Changes

`chapter_id` now only allows:

```text
A-Z
a-z
0-9
_
-
```

Human-readable titles remain separate and can contain normal prose.

`audit-project` now checks:

```text
orphan confirmed artifacts
missing confirmed artifacts
confirmed artifact/index chapter_id mismatch
confirmed source draft missing
confirmed source draft not committed
confirmed chapter without commit log entry
unsafe confirmed artifact paths
default checkpoint including secrets
public state prompt/content/secrets patterns
```

Audit does not initialize or write project files.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 70 tests
OK
```

Manual audit check:

```powershell
$env:PYTHONPATH='I:\AI-NOVEL\novel_agent_workbench\src'; py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_cli_smoke_test audit-project cli_demo
```

Result:

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
codex_logs\2026-05-17_mvp1_quality_hardening\README.md
src\novel_agent_workbench\audit.py
src\novel_agent_workbench\drafts.py
src\novel_agent_workbench\project_state.py
tests\README.md
tests\test_audit.py
tests\test_draft_generation.py
```

## Next Step

Proceed to MVP-2 Provider adapter skeleton only after another full test run and `audit-project` on a smoke project. Keep it no-network until adapter registry and secret lookup contracts are proven.
