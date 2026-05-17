# MVP-2 Provider Config Preflight

Date: 2026-05-17, Asia/Shanghai.

## Goal

Add a safe Provider configuration write path before enabling any real LLM adapter.

## Modified Files

```text
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\__init__.py
tests\test_provider_config.py
tests\test_application_service.py
tests\test_cli.py
README.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\CLI_QUICKSTART.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
src\novel_agent_workbench\README.md
tests\README.md
```

## New Backend APIs

```text
configure_provider_role(...)
set_project_secret(...)
```

`configure_provider_role(...)` writes role config and `api_key_ref` only.

`set_project_secret(...)` writes the local secret into `data\secrets.local.json` and returns only masked metadata.

## New CLI Commands

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> set-project-secret <project_id> <name> --value <value>
py -3.13 -m novel_agent_workbench.cli --projects-root <root> set-project-secret <project_id> <name> --value-stdin
py -3.13 -m novel_agent_workbench.cli --projects-root <root> configure-provider-role <project_id> writer --provider deepseek --model deepseek-chat --api-key-ref project_secret.deepseek_key
```

These commands do not send network requests.

## Safety Rules

```text
API key plaintext may exist only in data\secrets.local.json.
config.json stores only project_secret.<name>.
CLI output returns masked secret state only.
disabled adapters still return adapter_disabled.
generation with disabled adapters still creates no draft, no confirmed chapter, no Memory Bank/RAG/export side effects.
```

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 87 tests in 3.157s
OK
```

## Known Not Implemented

```text
real HTTP calls
real provider enablement
streaming
cost accounting
UI provider settings
```

## Next Step

The next phase can add a dry-run provider request translator for disabled adapters, or move to an explicit real-provider approval gate after the user confirms which Provider should be first.
