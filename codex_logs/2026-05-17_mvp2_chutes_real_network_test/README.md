# MVP-2 Chutes Real Network Test

Date: 2026-05-17, Asia/Shanghai.

## Goal

Run one explicitly authorized real Chutes Provider connection test through the backend CLI.

## Safety Boundary

The user explicitly allowed a network test.

The real API key was not written to Git, docs, tests, or logs. It was stored only in the ignored runtime test project:

```text
workspace_projects\chutes_realtest_20260517\data\secrets.local.json
```

The test command did not create drafts, confirmed chapters, Memory Bank updates, RAG updates, exports, or provider call logs.

The CLI result did not return prompt text, response text, request body, or plaintext key.

## Test Project

```text
project_id: chutes_realtest_20260517
provider: chutes_openai
base_url: https://llm.chutes.ai/v1
model: Qwen/Qwen3-32B-TEE
```

## Real Test Result

Command shape:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects provider-real-test chutes_realtest_20260517 writer --prompt "Return exactly OK." --temperature 0 --max-tokens 16
```

Result:

```text
ok: true
status_code: 200
finish_reason: length
response_text_chars: 62
prompt_tokens: 12
completion_tokens: 16
total_tokens: 28
```

## Audit Result

`audit-project` was run after the real test.

Expected finding:

```text
provider_adapter_disabled
```

Reason: `chutes_openai` remains disabled in the adapter registry even though a single explicit real-test command is allowed.

No prompt/key leak finding was reported.

## Verification

Before the real network test, full tests passed:

```text
Ran 99 tests in 3.218s
OK
```

After documentation updates, full tests passed again:

```text
Ran 99 tests in 3.301s
OK
```

Tracked-file secret search found no committed key material.

## Next Step

Keep normal generation blocked for `chutes_openai`. The next phase should decide whether to add a user-approved `enable_real_provider_for_tests` setting or keep real calls limited to `provider-real-test`.

## Secret Removal

After the successful network test, the user asked to temporarily delete the key.

Action taken:

```text
Removed chutes_key from workspace_projects\chutes_realtest_20260517\data\secrets.local.json.
```

Verification:

```text
secrets_file_exists: true
contains_chutes_key: false
secret_count: 0
```

No plaintext key was written to this log.
