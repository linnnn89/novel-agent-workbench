# MVP-1 Provider Config Stub Log

Date: 2026-05-17, Asia/Shanghai.

## Operation

Add the first MVP-1 slice: Provider role configuration objects and fake connection testing.

## Scope

Allowed:

```text
writer/scorer/reviser config parsing
project_secret.* api_key_ref validation
safe config updates
fake connection test with no network
unit tests
```

Not allowed:

```text
real HTTP calls
LLM generation
frontend
chapter generation
scoring/revision execution
DOCX export
reference project edits
```

## Design

Add `providers.py` with:

- `ModelRoleConfig`
- `ProviderConnectionResult`
- `set_model_role_config(...)`
- `fake_test_model_role(...)`

The fake test verifies configuration shape and secret references only. It must never return a plaintext secret.

## Verification

First run found one overly broad test assertion: `api_key_ref` is an allowed field name, while raw plaintext keys are forbidden. The test was corrected to assert that raw key material such as `sk-...` is absent from config.

Command:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 33 tests in 0.621s
OK
```

## Files Changed

```text
README.md
codex_docs\DECISIONS.md
codex_docs\PROJECT_CHARTER.md
codex_logs\2026-05-17_mvp1_provider_config_stub\README.md
src\novel_agent_workbench\__init__.py
src\novel_agent_workbench\providers.py
src\novel_agent_workbench\README.md
tests\README.md
tests\test_provider_config.py
```

## Notes

No network code was added. No real Provider API call is possible in this slice.
