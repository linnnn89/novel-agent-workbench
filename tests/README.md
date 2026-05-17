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

Current implemented tests cover storage, registry, foundation config, Provider config/interface, draft generation, explicit draft commit, and safe project state summaries.

Chapter workflow tests currently cover:

- planned chapter creation,
- generate success moving state to `draft_ready`,
- explicit commit moving state to `committed`,
- generation failure moving state to `blocked` without prompt leakage,
- duplicate commit keeping `committed` while recording metadata-only error,
- chapter CLI commands `mark-chapter-planned`, `chapter-status`, and `list-chapters`,
- public state and audit output excluding prompt text, generated content, and plaintext secrets.

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
- fake connection success without network for mock roles,
- Provider adapter registry state,
- project secret resolver reads only `secrets.local.json`,
- resolver errors for invalid, missing, and empty secret refs,
- disabled real-provider adapters failing locally without draft/confirmed/Memory/RAG/export side effects,
- safe disabled Provider config writes with `project_secret.*` refs,
- project-local secret writes returning masked metadata only,
- rejection of missing real-provider secret refs and raw key settings,
- disabled Provider dry-run summaries for `deepseek` and `openai_compatible`,
- disabled Chutes OpenAI-compatible dry-run summary,
- mocked Chutes real-test metadata path without log/draft side effects,
- Chutes `generate-draft` blocked until `settings.real_generation_enabled=true`,
- Chutes real-generation disable path can recover incomplete Chutes config,
- mocked Chutes real draft generation writing draft content only to `data/drafts/*.json`,
- Chutes real generation audit gate blocking prompt/key/content leak findings,
- dry-run secret error handling without request summaries,
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
- unsafe `chapter_id` rejection,
- no creation of confirmed chapter files or export folders,
- no mutation of Memory Bank or export settings,
- draft artifact/index exclusion of prompt text and plaintext secrets,
- provider error path leaving no draft artifact behind,
- checkpoint inclusion of draft artifacts without secrets or prompt text.

Draft commit and project state tests currently cover:

- draft status checks,
- explicit draft commit to confirmed chapter,
- duplicate commit rejection,
- pre-commit checkpoint creation,
- confirmed chapter artifact and index creation,
- commit log exclusion of prompt text, chapter content, and plaintext secrets,
- checkpoint-after-commit exclusion of prompt text and plaintext secrets,
- no Memory Bank, RAG, or export side effects,
- public project state exclusion of prompt text, chapter content, and plaintext secrets.

Application service facade tests currently cover:

- project creation and project listing,
- mock writer configuration through the backend facade,
- draft generation/list/read through the backend facade,
- explicit commit and confirmed chapter read through the backend facade,
- facade state exclusion of prompt text, chapter content, and plaintext secrets,
- failed generation leaving no draft behind,
- facade enable/disable real-provider flag updates without plaintext secret exposure,
- facade Chutes one-command runbook output excluding prompt, key, and generated content.

CLI tests currently cover:

- one-command smoke flow with mock writer and explicit commit,
- chapter workflow CLI commands,
- split create/configure/generate/commit/list commands,
- JSON error output on failed generation,
- no prompt text in smoke JSON output,
- `audit-project` checking a smoke-generated project.
- `provider-status` for mock writer,
- disabled provider status without network,
- Provider status output excluding plaintext secrets.
- `configure-provider-role` and `set-project-secret` output excluding plaintext secrets,
- missing secret ref rejection in CLI config write.
- `provider-dry-run` output excluding prompt text, system prompt text, and plaintext secrets.
- Chutes `provider-dry-run` CLI output with `llm.chutes.ai` host and no prompt/key leak.
- Chutes `provider-real-test` CLI output with mocked HTTP and no prompt/key/response-text leak.
- `enable-real-provider` / `disable-real-provider` only changing config and making no network call.
- Chutes real `generate-draft` CLI output with mocked HTTP excluding prompt/key/generated content.
- `chutes-generate-once` requiring `--allow-network`, using mocked HTTP for success, cleaning secrets, disabling the gate, and excluding prompt/key/generated content.
- `chutes-generate-once` mocked success leaving zero file hits for the fake key after cleanup.
- `chutes-generate-once` audit-gate blocking without network or draft side effects.

Audit tests currently cover:

- clean smoke project passes audit,
- plaintext `sk-...` / `api_key` in config fails audit,
- prompt text in provider log fails audit,
- content in commit log fails audit,
- orphan confirmed artifact detection,
- confirmed index entry with uncommitted source draft detection,
- audit read-only behavior on uninitialized projects.
- raw Provider API keys in config/settings,
- disabled Provider adapter findings,
- missing Provider secret refs and local secrets.
- audit after provider dry-run excluding prompt text and plaintext secrets.
- Chutes real-generation-enabled config with the expected disabled-adapter finding but no secret leak.
- real-generation-enabled missing secret findings.
