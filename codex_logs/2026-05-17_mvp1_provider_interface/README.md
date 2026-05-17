# MVP-1 Provider Interface Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Implement the first Provider interface layer and a deterministic local Mock Provider.

## Scope

Allowed:

```text
ProviderRequest / ProviderResponse / ProviderClient
MockProviderClient
mock-only provider factory
local provider call audit log
unit tests
```

Not allowed:

```text
real HTTP calls
real LLM provider integration
frontend
chapter generation
scoring/revision execution
DOCX export
reference project edits
```

## Design

`providers.py` now includes:

- `ProviderRequest`
- `ProviderResponse`
- `ProviderError`
- `ProviderClient`
- `MockProviderClient`
- `create_provider_client(...)`
- `generate_with_provider(...)`
- `read_provider_call_log(...)`

The factory only enables `provider="mock"`. Non-mock provider ids return `unsupported_provider` and never attempt network access.

Provider call logs are stored in project data:

```text
data/provider_call_log.json
```

The log records call metadata only:

```text
call_id
timestamp
role
provider
model
status
error_type
usage
request_summary.prompt_chars
request_summary.system_prompt_chars
request_summary.metadata_keys
```

The log must not contain prompt text, system prompt text, or plaintext secrets. Because the log is metadata-only, default checkpoints include it while still excluding `data/secrets.local.json`.

## Verification

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 40 tests
OK
```

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_provider_interface\README.md
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_provider_config.py
```

## Known Boundaries

- No real provider can be called.
- Mock output is intentionally minimal and deterministic.
- Usage numbers are placeholder token estimates.
- The provider audit log is append-only JSON for now; later phases may rotate or index it.

## Next Step

Build an MVP-1 generation service skeleton that consumes `ProviderRequest` and writes draft artifacts only, with no confirmed-state side effects.
