# MVP-2 Chutes Provider Preflight

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add Chutes as a reserved OpenAI-compatible Provider adapter without enabling real network calls.

## User-Provided Provider Shape

Public endpoint shape:

```text
https://llm.chutes.ai/v1/chat/completions
```

Configured base URL for the workbench:

```text
https://llm.chutes.ai/v1
```

Model example:

```text
Qwen/Qwen3-32B-TEE
```

The user pasted a real key in chat. It was not written to code, docs, tests, Git, or runtime files by this step.

## Modified Files

```text
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\__init__.py
tests\test_provider_config.py
tests\test_cli.py
README.md
codex_docs\CLI_QUICKSTART.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
src\novel_agent_workbench\README.md
tests\README.md
```

## Adapter Boundary

New adapter id:

```text
chutes_openai
```

Current state:

```text
enabled=false
network_allowed=false
requires_secret=true
```

`provider-dry-run` can return safe summaries for Chutes. Generation still returns `adapter_disabled` and sends no HTTP requests.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 96 tests in 3.596s
OK
```

## Next Step

If the user explicitly allows real network testing, add a separate real-network gate for `chutes_openai` and run one minimal non-streaming connection test. Until then, keep Chutes dry-run only.
