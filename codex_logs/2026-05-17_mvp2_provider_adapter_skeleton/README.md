# MVP-2 Provider Adapter Skeleton

Date: 2026-05-17, Asia/Shanghai.

## Goal

Create the real-Provider preflight foundation without enabling real LLM access.

## Modified Files

```text
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\audit.py
src\novel_agent_workbench\__init__.py
tests\test_provider_config.py
tests\test_cli.py
tests\test_audit.py
tests\test_application_service.py
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
```

Documentation updates were also made in README, PROJECT_CHARTER, DECISIONS, APPLICATION_SERVICE_CONTRACT, CLI_QUICKSTART, package README, and tests README.

## Adapter Registry

`mock` remains the only enabled Provider adapter.

Reserved adapters:

```text
openai_compatible
deepseek
```

Both are disabled and marked `network_allowed=false`. Generation with a disabled adapter short-circuits locally with `adapter_disabled`.

## Secret Resolver

Secret lookup now uses one contract:

```text
project_secret.<name> -> data\secrets.local.json
```

The resolver does not read environment variables, config plaintext fields, logs, public state, or checkpoint data.

Stable errors:

```text
missing_secret_ref
invalid_secret_ref
missing_secret
empty_secret
```

## CLI

New commands:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> provider-status <project_id> writer
py -3.13 -m novel_agent_workbench.cli --projects-root <root> list-provider-adapters
```

These commands return JSON and do not perform network checks.

## Audit Rules

`audit-project` now checks Provider adapter config for:

```text
raw_provider_api_key_in_config
provider_adapter_unregistered
provider_adapter_disabled
provider_missing_secret_ref
provider_invalid_secret_ref
provider_missing_secret
provider_invalid_role_config
```

Audit remains read-only.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 81 tests in 2.889s
OK
```

## Known Not Implemented

```text
real Provider HTTP adapter
streaming
retry/backoff
cost ledger
UI Provider setup
DOCX export
scoring/revision workflow
Memory Bank/RAG/export auto-updates
```

## Next Step

The next phase should introduce a controlled Provider configuration write path for disabled real adapters, still without enabling network, or begin the explicit approval gate for one real Provider adapter after audit passes.
