# Provider Adapter Contract

Date: 2026-05-17, Asia/Shanghai.

## Scope

This document defines the Provider boundary for mock, dry-run, explicit real test, and the controlled Chutes draft-generation gate.

Current enabled adapter:

```text
mock
```

Reserved but disabled adapters:

```text
openai_compatible
deepseek
chutes_openai
```

Disabled adapters must never send HTTP requests, create drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

## Adapter Registry

Provider adapter metadata lives in:

```text
src\novel_agent_workbench\providers.py
```

Each adapter records:

```text
adapter_id
enabled
network_allowed
requires_secret
description
```

`mock` is enabled and has `network_allowed=false`.

`openai_compatible`, `local_openai_compatible`, `deepseek`, and `chutes_openai` are registered HTTP adapters. They use the network only when the user starts a connection test or generation command.

`chutes_openai` may generate a writer draft when the writer role is configured for Chutes, the local secret resolves, and audit leak checks pass. There is no separate network-enable gate.

## Secret Lookup

Secret references must use:

```text
project_secret.<name>
```

Plain API keys are forbidden in:

```text
data\config.json
provider logs
commit logs
public project state
audit results
```

The resolver reads only:

```text
data\secrets.local.json
```

It must not read environment variables, general config fields, logs, public state, or checkpoint data.

Stable secret error types:

```text
missing_secret_ref
invalid_secret_ref
missing_secret
empty_secret
```

## Config And Status Checks

`provider-status` is a local configuration check only. It may report whether a role is configured, whether the adapter is enabled, and whether the referenced local secret exists.

It must not:

- send network requests,
- clear or reset a project,
- create drafts,
- create confirmed chapters,
- update Memory Bank,
- update RAG,
- create exports,
- return plaintext secrets.

`configure-provider-role` may write Provider role config for registered adapters.

For secret-requiring adapters, it must require:

```text
--api-key-ref project_secret.<name>
```

It must not accept or write plaintext API keys.

`set-project-secret` may write a value into `data\secrets.local.json`.

It must return only masked metadata and should prefer `--value-stdin` for manual use.

## Dry-Run Request Translation

`provider-dry-run` builds a future request summary without sending it.

Allowed summary fields:

```text
provider
model
base_url_host
message_count
prompt_chars
system_prompt_chars
temperature
max_tokens
metadata_keys
```

Forbidden dry-run output:

```text
prompt text
system prompt text
full request body
Authorization header
API key
secrets.local.json content
raw response content
```

`deepseek` uses the same OpenAI-compatible summary shape while preserving `provider=deepseek`.

`chutes_openai` uses the same OpenAI-compatible summary shape while preserving `provider=chutes_openai`.

Known Chutes base URL shape:

```text
https://llm.chutes.ai/v1
```

Known Chutes model example:

```text
Qwen/Qwen3-32B-TEE
```

Dry-run does not write preflight logs by default. If a later phase adds preflight logs, they must follow the same no prompt, no body, no key rule.

## Explicit Real Test

`provider-real-test` is the only current command allowed to send a real Provider HTTP request.

Current supported adapter:

```text
chutes_openai
```

Real test output may include:

```text
status_code
finish_reason
usage
response_text_chars
base_url_host
```

Real test output must not include:

```text
prompt text
system prompt text
full request body
Authorization header
API key
raw response text
```

Real test must not create drafts, confirmed chapters, Memory Bank updates, RAG updates, exports, or provider call logs.

## Controlled Chutes Real Draft Generation

`generate-draft` may send a real Chutes request only when all conditions are true:

```text
role: writer
provider: chutes_openai
api_key_ref: project_secret.<name>
local secret: present and non-empty in data/secrets.local.json
audit leak gate: no key/prompt/content leak findings
```

Stable blocking errors include:

```text
unsupported_real_provider
missing_secret
empty_secret
audit_gate_failed
```

The Chutes client sends a non-streaming OpenAI-compatible request to `/chat/completions` with:

```text
model
messages
temperature
max_tokens
stream=false
```

It extracts only assistant content, usage, and finish reason. It must not write raw response JSON, request bodies, prompts, system prompts, or API keys into logs or draft metadata.

Real generated content is allowed only in:

```text
data/drafts/*.json
```

because `read-draft` is the human review surface. It must not be copied into provider logs, CLI `generate-draft` output, audit output, `data/drafts_index.json`, confirmed chapters, Memory Bank, RAG, or exports unless a later explicit commit/update feature is implemented.

## Chutes Generate Once Runbook

`chutes-generate-once` is the preferred CLI path for real Chutes draft trials.

It must run:

```text
audit precheck
secret/config setup
enable gate
generate draft
disable gate
optional secret cleanup
audit postcheck
```

It returns a metadata-only summary and must not include prompt text, generated content, raw response, request body, or plaintext key. Temporary secret setup/cleanup uses no-backup writes so clearing a key does not leave a new `secrets.local.json` backup containing the old key.

## Logs

Provider call logs may record:

```text
call_id
timestamp
role
provider
model
status
error_type
usage
prompt length
system prompt length
metadata key names
```

Provider call logs must not record:

```text
prompt text
system prompt text
request body
response raw content
plaintext API keys
secrets.local.json content
```

## Audit Gate

Before any real Provider adapter is generally enabled, the project must pass:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> audit-project <project_id>
```

`audit-project` is read-only. It checks for obvious raw API keys in config, disabled provider adapter usage, missing secret refs, missing local secrets, prompt/key leaks in logs, unsafe checkpoints, and confirmed chapter consistency.

For the controlled Chutes draft gate, `provider_adapter_disabled` is an expected non-blocking finding because the registry remains disabled. The gate blocks only key/prompt/content leak findings and missing or empty secrets.

## Current Non-Goals

This contract does not implement:

```text
streaming
retry policy
rate limit backoff
cost accounting
UI configuration
automatic real Provider enablement
automatic commit of real drafts
```
