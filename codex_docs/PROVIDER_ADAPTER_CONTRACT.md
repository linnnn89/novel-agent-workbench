# Provider Adapter Contract

Date: 2026-05-17, Asia/Shanghai.

## Scope

This document defines the Provider boundary before real LLM access is allowed.

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

`openai_compatible`, `deepseek`, and `chutes_openai` are registered only as future placeholders. They have `enabled=false` and `network_allowed=false`.

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

Before any real Provider adapter is enabled, the project must pass:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> audit-project <project_id>
```

`audit-project` is read-only. It checks for obvious raw API keys in config, disabled provider adapter usage, missing secret refs, missing local secrets, prompt/key leaks in logs, unsafe checkpoints, and confirmed chapter consistency.

## Current Non-Goals

This contract does not implement:

```text
real LLM HTTP calls
streaming
retry policy
rate limit backoff
cost accounting
provider-specific request translation
UI configuration
```
