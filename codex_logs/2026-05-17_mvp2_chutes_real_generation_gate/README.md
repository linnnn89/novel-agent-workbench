# MVP-2 Chutes Real Generation Gate

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add a controlled real Provider path so `chutes_openai` can generate one writer draft only after an explicit project switch is enabled.

This stage still excludes UI, DOCX, scoring/revision loops, automatic commit, Memory Bank updates, RAG updates, and exports.

## Modified Files

Code:

```text
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\audit.py
src\novel_agent_workbench\project_state.py
src\novel_agent_workbench\__init__.py
```

Tests:

```text
tests\test_provider_config.py
tests\test_cli.py
tests\test_audit.py
tests\test_application_service.py
```

Docs:

```text
README.md
codex_docs\PROJECT_CHARTER.md
codex_docs\DECISIONS.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\CLI_QUICKSTART.md
src\novel_agent_workbench\README.md
tests\README.md
```

## Gate Design

Real draft generation is allowed only when all conditions are true:

```text
role = writer
provider = chutes_openai
settings.real_generation_enabled = true
api_key_ref = project_secret.<name>
secret exists in data\secrets.local.json
audit leak gate has no key/prompt/content finding
```

Stable blocking errors include:

```text
real_generation_disabled
unsupported_real_provider
missing_secret
empty_secret
audit_gate_failed
```

`provider_adapter_disabled` remains an expected audit finding for Chutes because the adapter registry still marks Chutes disabled. The real-generation gate ignores that finding and blocks only leak findings plus secret resolution failures.

2026-05-17 review correction: disabling the gate is lenient. It can turn `settings.real_generation_enabled` back to `false` even if model, base URL, or secret reference is incomplete. Enabling remains strict.

## Chutes Client Boundary

The Chutes client sends a non-streaming OpenAI-compatible `/chat/completions` request with a finite timeout.

It extracts:

```text
assistant content
usage
finish_reason
```

It does not store raw response JSON, prompt text, system prompt text, request body, Authorization header, API key, or `secrets.local.json` content.

Generated content may appear only in draft artifacts under:

```text
data\drafts\*.json
```

`data\drafts_index.json`, `data\provider_call_log.json`, CLI output, audit output, and docs remain metadata-only.

## CLI Commands

Enable the gate:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> enable-real-provider <project_id> writer --provider chutes_openai
```

Disable the gate:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> disable-real-provider <project_id> writer
```

Generate a gated real draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> generate-draft <project_id> --chapter-id chapter_001 --prompt "short approved prompt" --max-tokens 128
```

The generate command returns draft metadata only. Use `read-draft` to inspect generated content.

## Test Result

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 107 tests in 3.844s
OK
```

## Real Trial

Executed once with explicit user permission.

Runtime project:

```text
workspace_projects\chutes_realdraft_20260517_gate
```

Result metadata:

```text
provider: chutes_openai
model: Qwen/Qwen3-32B-TEE
draft_id: 20260517T115816835194Z_815e97a0a7e8
total_tokens: 117
```

Post-run cleanup:

```text
disable-real-provider was run
data\secrets.local.json was reset to {}
exact key file scan found 0 hits
```

Post-cleanup audit findings:

```text
provider_adapter_disabled
provider_missing_secret
```

These findings are expected after key cleanup. No prompt/key/content leak finding was reported.

## Known Non-Goals

```text
automatic real Provider enablement
streaming
retry or backoff policy
cost accounting
automatic commit
Memory Bank update
RAG update
export creation
DOCX
UI
scoring/revision workflow
```

## Next Stage Suggestion

After one clean real draft trial, add a small operator-runbook command or script that performs: configure Chutes, enable gate, generate draft, audit, disable gate, and verify no secrets remain in runtime state.
