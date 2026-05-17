# Tests

This folder will contain tests for the new implementation.

Minimum early test targets:

- atomic JSON write recovery,
- backup creation,
- project lock behavior,
- API key masking and secrets isolation,
- draft revisions having no confirmed-state side effects,
- confirmed revision commit behavior.

Current backend verification command:

```powershell
py -3.13 -m unittest discover -s tests
```

Current implemented tests cover the storage kernel only. Draft/confirmed tests belong to a later MVP slice.

Checkpoint tests currently cover:

- manifest creation,
- default secret exclusion,
- explicit secret inclusion,
- restore to checkpoint state,
- `.trash` retirement of overwritten files,
- project mismatch rejection,
- unsafe checkpoint path rejection.

Registry tests currently cover:

- default `workspace_projects` routing,
- project creation,
- opening existing projects,
- missing project rejection,
- discovery of valid unindexed projects,
- unsafe project id rejection,
- no hard delete API.

Foundation tests currently cover:

- default config schema and placeholder data files,
- legacy config migration,
- migration idempotence,
- checkpoint-before-migration behavior,
- missing project metadata repair,
- secrets isolation and masked public state,
- checkpoint exclusion of secrets, backups, and `.trash` files.

Provider config tests currently cover:

- default role config is unconfigured,
- model role config persistence,
- raw API key rejection,
- raw `api_key_ref` rejection,
- missing project secret reporting,
- fake connection success without network,
- invalid role rejection.

Provider interface tests currently cover:

- request/response serialization,
- mock writer/scorer/reviser generation,
- unsupported provider rejection without network,
- missing model and missing secret-ref errors,
- simulated rate limit, timeout, and invalid-request errors,
- provider call log exclusion of prompt text and plaintext secrets,
- checkpoint inclusion of safe provider logs while excluding `secrets.local.json`.

Draft generation tests currently cover:

- mock writer output written to `data/drafts/*.json`,
- draft index creation at `data/drafts_index.json`,
- no creation of confirmed chapter files or export folders,
- no mutation of Memory Bank or export settings,
- draft artifact/index exclusion of prompt text and plaintext secrets,
- provider error path leaving no draft artifact behind,
- checkpoint inclusion of draft artifacts without secrets or prompt text.
