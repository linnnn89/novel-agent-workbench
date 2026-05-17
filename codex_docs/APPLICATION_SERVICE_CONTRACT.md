# Application Service Contract

Date: 2026-05-17, Asia/Shanghai.

## Scope

`WorkbenchApplicationService` is the stable backend facade for future CLI, HTTP, or UI layers.

It must stay thin. It delegates to:

```text
ProjectRegistry
DraftGenerationService
public_project_state
set_model_role_config
```

It must not directly implement storage internals, Provider HTTP calls, Memory Bank updates, RAG updates, export generation, DOCX, or UI routing.

## Construction

Default:

```python
WorkbenchApplicationService.default()
```

Custom project root:

```python
WorkbenchApplicationService.open(projects_root)
```

## Methods

### create_project(project_id, title="")

Creates and initializes a project.

Returns metadata plus safe project state:

```text
project_id
title
path
state
```

`state` must not include prompt text, chapter content, or plaintext secrets.

### list_projects()

Returns registry entries.

Metadata-only. Must not return prompt text, generated content, or plaintext secrets.

### project_state(project_id)

Returns safe public project state.

Required top-level fields:

```text
project_id
config
secrets
draft_count
committed_chapter_count
latest_draft
latest_committed_chapter
provider_roles
```

Must not return prompt text, chapter content, or plaintext secrets.

### configure_mock_writer(project_id, model="mock-writer")

Configures the writer role for deterministic local mock generation.

Must not write raw API keys.

### generate_draft(...)

Inputs:

```text
project_id
chapter_id
prompt
title
system_prompt
temperature
max_tokens
metadata
```

Returns draft metadata:

```text
draft_id
chapter_id
title
path
provider
model
usage
```

Must not auto-commit.

### list_drafts(project_id)

Returns draft metadata from `data/drafts_index.json`.

Metadata-only. Must not return prompt text or generated content.

### read_draft(project_id, draft_id)

Returns the draft artifact.

May return generated draft content for human review.

Must not return original prompt text or plaintext secrets.

### commit_draft(project_id, draft_id)

Explicitly promotes a draft to confirmed chapter.

Returns:

```text
draft_id
chapter_id
title
path
committed_at
checkpoint
```

Must create a `pre_commit` checkpoint before confirmed files are written.

Must not update Memory Bank, RAG, or exports.

### list_confirmed_chapters(project_id)

Returns confirmed chapter metadata from `data/confirmed_chapters.json`.

Metadata-only. Must not return chapter content.

### read_confirmed_chapter(project_id, chapter_id)

Returns confirmed chapter artifact.

May return generated chapter content for human review.

Must not return original prompt text or plaintext secrets.

### audit_project(project_id)

Runs a read-only safety audit.

Returns:

```text
ok
project_id
findings
checked_paths
```

Must not modify project files.

Must not return prompt text, generated content, or plaintext secrets.

## Provider Contract Summary

Current enabled Provider:

```text
mock
```

Future real Providers must:

- read secrets only through `secrets.local.json`,
- use `project_secret.<name>` references in config,
- never write plaintext keys to `config.json`,
- never log prompt text or plaintext secrets in provider logs,
- pass `audit-project` before being considered safe for normal use.

Provider error types currently used:

```text
missing_provider
unsupported_provider
missing_model
missing_secret_ref
missing_secret
invalid_request
rate_limit
timeout
```
