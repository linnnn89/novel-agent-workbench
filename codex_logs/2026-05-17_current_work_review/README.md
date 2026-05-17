# Current Work Review

Date: 2026-05-17, Asia/Shanghai.

## Scope

Reviewed the current backend workbench state after MVP-0, MVP-1, and MVP-2 Chutes gate work.

Focus areas:

```text
Git cleanliness
unit test baseline
workspace_projects ignore boundary
Provider gate safety
Chutes real-generation cleanup
audit leak gate
no hard delete policy
documentation consistency
```

## Baseline Checks

Git status before review:

```text
clean
```

Recent commit head:

```text
3110d5e Add Chutes real draft generation gate
```

Runtime data check:

```text
workspace_projects/ remains ignored by Git
```

Unit test baseline:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 107 tests in 3.966s
OK
```

Exact real Chutes key residue scan:

```text
exact_key_file_hit_count: 0
```

## Finding

One recoverability issue was found.

`disable-real-provider` reused the same strict validation as `enable-real-provider`. That meant a partially broken Chutes writer config could fail to disable if required fields such as `base_url` or `api_key_ref` were missing.

Risk:

```text
operator may be unable to return a malformed role config to real_generation_enabled=false
```

## Correction

Changed `set_real_generation_enabled(...)` so:

```text
enabled=true  -> strict model/base_url/api_key_ref validation
enabled=false -> lenient rollback when role/provider match
```

Added regression coverage:

```text
test_disable_real_generation_can_recover_incomplete_chutes_config
```

Updated documentation:

```text
codex_docs\PROVIDER_ADAPTER_CONTRACT.md
codex_logs\2026-05-17_mvp2_chutes_real_generation_gate\README.md
```

## Verification

Targeted test:

```powershell
py -3.13 -m unittest tests.test_provider_config.ProviderConfigTest.test_disable_real_generation_can_recover_incomplete_chutes_config tests.test_provider_config.ProviderConfigTest.test_chutes_real_generation_writes_draft_only_with_mocked_http
```

Result:

```text
Ran 2 tests
OK
```

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 108 tests in 3.752s
OK
```

## Residual Notes

No hard-delete path was found in public project APIs.

The old reference project remains untouched.

`provider_adapter_disabled` remains expected for Chutes because the registry stays disabled even when the explicit writer-only real-generation gate is enabled.
