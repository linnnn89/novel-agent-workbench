# MVP-2.5 Real Provider Runbook

Date: 2026-05-17, Asia/Shanghai.

## Goal

Create a safer backend-only operator path for one controlled Chutes real draft generation run.

The runbook keeps the existing boundaries:

```text
no UI
no DOCX
no scoring/revision workflow
no automatic commit
no Memory Bank update
no RAG update
no export creation
```

## Added Command

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> chutes-generate-once <project_id> --chapter-id chapter_001 --prompt "short approved prompt" --secret-value-stdin --allow-network --clear-secret-after-run --max-tokens 96 --temperature 0.2
```

`--allow-network` is required before any HTTP request is possible.

`--clear-secret-after-run` defaults to enabled. `--keep-secret-after-run` is available for manual debugging but should not be the normal path.

## Fixed Sequence

```text
audit precheck
secret/config setup
enable real-generation gate
generate draft
disable real-generation gate
optional secret cleanup
audit postcheck
metadata-only summary
```

## Safety Rules

The command output must not include:

```text
prompt text
system prompt text
generated draft content
raw response JSON
request body
plaintext API key
```

Generated content is allowed only in:

```text
data\drafts\*.json
```

The runbook uses no-backup writes for temporary secret setup/cleanup so clearing a runtime key does not create a new `.bak` containing the old key.

## Modified Files

Code:

```text
src\novel_agent_workbench\runbooks.py
src\novel_agent_workbench\application_service.py
src\novel_agent_workbench\cli.py
src\novel_agent_workbench\__init__.py
```

Tests:

```text
tests\test_cli.py
tests\test_application_service.py
```

Docs:

```text
README.md
codex_docs\PROJECT_CHARTER.md
codex_docs\DECISIONS.md
codex_docs\APPLICATION_SERVICE_CONTRACT.md
codex_docs\CLI_QUICKSTART.md
src\novel_agent_workbench\README.md
tests\README.md
```

## Verification

Targeted tests:

```powershell
py -3.13 -m unittest tests.test_cli.CliTest.test_chutes_generate_once_requires_explicit_network_allowance tests.test_cli.CliTest.test_chutes_generate_once_cli_success_cleans_secret_and_outputs_metadata_only tests.test_cli.CliTest.test_chutes_generate_once_cli_audit_gate_blocks_leak_and_cleans_nothing_sensitive tests.test_application_service.WorkbenchApplicationServiceTest.test_facade_chutes_generate_once_is_metadata_only
```

Result:

```text
Ran 4 tests
OK
```

Full test:

```powershell
py -3.13 -m unittest discover -s tests
```

Result:

```text
Ran 112 tests in 3.930s
OK
```

Additional targeted secret residue check was added to the mocked CLI success test. It verifies that the temporary test root has zero file hits for the fake key after `--clear-secret-after-run`.

Final real-key residue scan:

```text
exact_key_file_hit_count: 0
```

## Real Trial

Not executed in this stage. A fresh user-provided Chutes key should be used for any future live run; do not restore or reuse a previously cleared key.
