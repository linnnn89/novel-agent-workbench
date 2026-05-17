# MVP-2 Provider Dry-Run Adapter

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add a no-network dry-run adapter path for reserved real Provider ids before any real HTTP integration.

## Modified Files

```text
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\__init__.py
tests\test_provider_config.py
tests\test_application_service.py
tests\test_cli.py
tests\test_audit.py
README.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\CLI_QUICKSTART.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
src\novel_agent_workbench\README.md
tests\README.md
```

## Dry-Run Output

`provider-dry-run` returns a safe request summary only:

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

It does not return:

```text
prompt text
system prompt text
full request body
API key
secret name value
raw response content
```

## Adapter Boundary

`mock` remains the only enabled generation adapter.

`deepseek` and `openai_compatible` now have a disabled dry-run adapter path. They return `adapter_disabled` and `network_allowed=false`.

Generation with disabled adapters still creates no draft, no confirmed chapter, no Memory Bank/RAG/export side effects.

## CLI

New command:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> provider-dry-run <project_id> writer --prompt "..." --system-prompt "..." --temperature 0.3 --max-tokens 1000
```

The command does not write provider preflight logs by default.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 94 tests in 3.519s
OK
```

## Known Not Implemented

```text
HTTP request execution
streaming
retry/backoff
cost ledger
real Provider enablement
UI setup
```

## Next Step

The next phase can add an explicit real-network approval gate for one Provider, most likely DeepSeek first, with a separate commit that introduces the HTTP client behind a disabled-by-default flag.
