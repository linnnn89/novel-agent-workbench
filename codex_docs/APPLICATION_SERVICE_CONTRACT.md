# Application Service Contract

Date: 2026-05-17, Asia/Shanghai.

## Scope

`WorkbenchApplicationService` is the stable backend facade for future CLI, HTTP, or UI layers.

It must stay thin. It delegates to:

```text
ProjectRegistry
DraftGenerationService
DraftReviewService
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
review_count
revision_request_count
context_update_count
context_preview_count
formal_context_plan_count
formal_context_task_count
memory_apply_preview_count
memory_bank_item_count
chapter_count
committed_chapter_count
latest_chapter
latest_draft
latest_review
latest_revision_request
latest_context_update
latest_context_preview
latest_formal_context_plan
latest_formal_context_task
latest_memory_apply_preview
latest_memory_bank_item
latest_committed_chapter
provider_roles
```

Must not return prompt text, chapter content, or plaintext secrets.

### mark_chapter_planned(project_id, chapter_id, title="")

Creates or updates a metadata-only chapter workflow entry.

Returns:

```text
chapter_id
title
status
created_at
updated_at
latest_draft_id
latest_review_id
latest_review_decision
latest_revision_request_id
latest_revision_draft_id
confirmed_chapter_id
error_summary
```

Status is `planned`.

Must not return prompt text, generated content, or plaintext secrets.

### list_chapters(project_id)

Returns chapter workflow metadata from:

```text
data/chapters_workflow.json
```

Metadata-only. Must not return prompt text, generated content, or plaintext secrets.

### chapter_status(project_id, chapter_id)

Returns one chapter workflow entry.

Metadata-only. Must not return prompt text, generated content, or plaintext secrets.

### configure_mock_writer(project_id, model="mock-writer")

Configures the writer role for deterministic local mock generation.

Must not write raw API keys.

### configure_provider_role(project_id, role, provider, model, api_key_ref="", base_url="")

Writes Provider role configuration for a known adapter.

For secret-requiring adapters, `api_key_ref` must use:

```text
project_secret.<name>
```

This method may configure disabled adapters for preflight only. It must not send network requests.

Must not write plaintext API keys to `config.json`.

### set_project_secret(project_id, name, value)

Writes a project-local secret into:

```text
data/secrets.local.json
```

Returns only:

```text
name
has_value
masked
```

Must not return plaintext secret values.

### enable_real_provider(project_id, role, provider)

Enables the controlled real-generation flag for one supported role/provider pair.

Current supported pair:

```text
role=writer
provider=chutes_openai
```

Writes only Provider role config:

```text
settings.real_generation_enabled=true
```

Must not send network requests, generate drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

Must not return plaintext secrets.

### disable_real_provider(project_id, role, provider="chutes_openai")

Disables the controlled real-generation flag for one supported role/provider pair.

Writes only Provider role config:

```text
settings.real_generation_enabled=false
```

Must not send network requests, generate drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

Must not return plaintext secrets.

### chutes_generate_once(...)

Runs the safe operator runbook for one controlled Chutes writer draft.

Inputs:

```text
project_id
chapter_id
prompt
title
system_prompt
model
base_url
secret_name
secret_value
temperature
max_tokens
allow_network
clear_secret_after_run
```

Required order:

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

`allow_network=true` is required for any real HTTP request.

Returns metadata only:

```text
status
project_id
role
provider
model
base_url_host
chapter_id
steps
draft metadata
error_type
message
secret state summary
audit code summaries
side effect summary
```

Must not return prompt text, system prompt text, generated draft content, raw response JSON, request body, or plaintext secrets.

Must not auto-commit, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or run scoring/revision workflows.

If `clear_secret_after_run=true`, the runbook rewrites `data/secrets.local.json` without creating a `.bak` containing the old key.

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

`chapter_id` must use ASCII letters, numbers, `_`, or `-`.

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

When the writer role uses `chutes_openai`, real generation is allowed only after `enable_real_provider(...)`, local secret resolution, and audit leak-gate success. CLI/facade output remains metadata-only; generated content is visible through `read_draft(...)`.

On successful draft generation, chapter workflow state may update to `draft_ready` with `latest_draft_id`.

On generation failure, chapter workflow state may update to `blocked` with metadata-only error summary.

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

On successful explicit commit, chapter workflow state updates to `committed` with `confirmed_chapter_id`.

On failed commit, chapter workflow records metadata-only error. If the chapter is already `committed`, it must not be downgraded to `blocked`.

### review_draft(project_id, draft_id)

Creates a metadata-only Draft Review / Quality Check artifact for one draft.

Returns:

```text
review_id
draft_id
chapter_id
status
path
provider
model
usage
```

Current implementation uses the configured `scorer` role, normally `provider=mock`.

On success, chapter workflow state may update to `review_ready` with `latest_review_id`.

Must not auto-commit, auto-revise, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or enable real Providers.

Must not return draft content, original prompt text, raw Provider responses, request bodies, or plaintext secrets.

### list_reviews(project_id)

Returns review metadata from `data/reviews_index.json`.

Metadata-only. Must not return draft content, prompt text, raw Provider responses, or plaintext secrets.

### read_review(project_id, review_id)

Returns one review artifact from `data/reviews/*.json`.

May return scores, issues, recommendation, and short safe comments.

Must not return draft content, original prompt text, raw Provider responses, or plaintext secrets.

### decide_review(project_id, review_id, decision, reason_code="")

Records one manual decision for an existing review.

Allowed decisions:

```text
accepted
needs_revision
blocked
```

Returns:

```text
review_id
draft_id
chapter_id
decision
reason_code
decided_at
```

`reason_code` is optional and must use safe ASCII letters, numbers, `_`, or `-`. Free-text notes are intentionally not stored in this phase.

On success, chapter workflow may update to:

```text
review_accepted
needs_revision
blocked
```

`accepted` is not a confirmed chapter. It must not auto-commit, auto-revise, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or enable real Providers.

Must not return draft content, original prompt text, raw Provider responses, request bodies, or plaintext secrets.

### create_revision_request(project_id, review_id)

Creates a metadata-only revision request from an existing review.

Required source state:

```text
review.decision.status == needs_revision
```

Returns:

```text
revision_request_id
review_id
draft_id
chapter_id
status
path
created_at
```

Writes:

```text
data/revision_requests/*.json
data/revision_requests_index.json
```

On success, chapter workflow may update to:

```text
revision_requested
```

Must reject pending, accepted, blocked, missing, and duplicate revision requests.

Must not call Providers, generate text, mutate draft artifacts, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or enable real Providers.

Must not return or store draft content, original prompt text, raw Provider responses, request bodies, plaintext secrets, or free-text notes.

### list_revision_requests(project_id)

Returns revision request metadata from `data/revision_requests_index.json`.

Metadata-only. Must not return draft content, prompt text, raw Provider responses, or plaintext secrets.

### read_revision_request(project_id, revision_request_id)

Returns one revision request artifact from `data/revision_requests/*.json`.

Metadata-only. Must not return draft content, prompt text, raw Provider responses, or plaintext secrets.

### generate_revision_draft(project_id, revision_request_id)

Creates a new mock revision draft candidate from one revision request.

Required source state:

```text
revision_request.status == requested
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

Writes:

```text
data/drafts/*.json
data/drafts_index.json
```

Updates the revision request:

```text
status=draft_created
generated_draft_id=<new draft id>
```

The new draft artifact may contain mock generated content for human review. It must include revision metadata linking:

```text
source_draft_id
source_review_id
revision_request_id
```

Must use only the configured `reviser` role with the local `mock` Provider in this phase.

Must not overwrite or mutate the source draft, create confirmed chapters, auto-commit, update Memory Bank, update RAG, create exports, create DOCX, call real Providers, or enable real Providers.

CLI/facade output, indexes, logs, public state, and audit output must not return source draft content, candidate draft content, original prompt text, raw Provider responses, request bodies, or plaintext secrets.

### list_revision_candidates(project_id, revision_request_id)

Returns a read-only metadata view of revision draft candidates linked to one revision request.

Returns:

```text
revision_request_id
chapter_id
source_draft_id
candidate_count
candidates
```

Each candidate summary may include:

```text
draft_id
chapter_id
title
status
created_at
provider
model
usage
char_count
word_count
line_count
```

Must not write project files, choose a candidate, auto-commit, update Memory Bank, update RAG, create exports, create DOCX, call Providers, return draft content, return prompt text, or return plaintext secrets.

### compare_revision_candidate(project_id, revision_request_id, candidate_draft_id)

Returns a read-only metadata comparison between the source draft and one linked revision candidate.

Returns:

```text
revision_request_id
chapter_id
source_draft
candidate_draft
deltas
link_check
recommendation
```

`recommendation` is currently:

```text
manual_review_required
```

This is not an automatic decision. It must not choose a winner, overwrite drafts, auto-commit, update Memory Bank, update RAG, create exports, create DOCX, call Providers, return draft content, return prompt text, or return plaintext secrets.

### enqueue_context_updates(project_id)

Scans confirmed chapter metadata and creates missing pending context update queue entries.

Writes:

```text
data/context_update_queue.json
```

Returns:

```text
created_count
total_count
items
```

Each item may include:

```text
update_id
chapter_id
title
source_draft_id
confirmed_chapter_id
status
created_at
updated_at
source
text_stats
targets
```

This is idempotent by `chapter_id`. It must not return chapter content, prompt text, or plaintext secrets. It must not update Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers.

### list_context_updates(project_id, status="")

Returns context update queue metadata.

Optional `status` filter:

```text
pending
acknowledged
skipped
```

Must not return chapter content, prompt text, or plaintext secrets.

### mark_context_update(project_id, update_id, status, reason_code="")

Updates one context update queue item status.

Allowed statuses:

```text
pending
acknowledged
skipped
```

`reason_code` must use safe ASCII letters, numbers, `_`, or `-`.

This marks queue metadata only. It must not update Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers.

### create_context_preview(project_id, update_id)

Creates a metadata-only preview artifact for one context update queue item.

Writes:

```text
data/context_update_previews/*.json
data/context_update_previews_index.json
```

Returns:

```text
preview_id
update_id
chapter_id
status
path
created_at
```

The preview artifact may include:

```text
preview_id
update_id
chapter_id
title
source_draft_id
confirmed_chapter_id
status
created_at
source
text_stats
target_plan
safety
recommendation
```

`target_plan.formal_context.priority_order` follows the project config policy:

```text
world_building
character_relationships
chapter_summary
style_memory
foreshadowing
```

Must reject skipped queue items and duplicate previews.

Must not return or store chapter text, prompt text, raw Provider responses, request bodies, or plaintext secrets. Must not update Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers.

### list_context_previews(project_id)

Returns context preview index metadata.

Metadata-only. Must not return chapter text, prompt text, or plaintext secrets.

### read_context_preview(project_id, preview_id)

Returns one context preview artifact.

May return target placeholders, text statistics, safety flags, and recommendation. Must not return chapter text, prompt text, raw Provider responses, request bodies, or plaintext secrets.

### create_formal_context_plan(project_id, preview_id)

Creates a metadata-only formal context extraction plan from one context preview.

Writes:

```text
data/formal_context_plans/*.json
data/formal_context_plans_index.json
```

Returns:

```text
plan_id
preview_id
chapter_id
status
path
created_at
```

The plan artifact may include:

```text
plan_id
preview_id
update_id
chapter_id
title
source_draft_id
confirmed_chapter_id
status
created_at
priority_order
categories
text_stats
safety
recommendation
```

`categories` follow the project `formal_context_policy` priority order and are marked `auto_extract=false`.

Category items may include:

```text
memory_weight
world_book_enabled
world_book_overlap_policy
recommendation
```

For `world_building`, default behavior is:

```text
memory_weight=1.0
world_book_overlap_policy=reduce_memory_when_world_book_enabled
world_book_enabled_memory_weight=0.35
```

When `context_policy.world_book_enabled=true`, the effective plan item for `world_building` uses `memory_weight=0.35` and recommends reducing Memory Bank duplication.

Must reject duplicate plans for the same preview.

Must not return or store chapter text, prompt text, raw Provider responses, request bodies, or plaintext secrets. Must not update Memory Bank, RAG, exports, drafts, confirmed chapters, or Providers.

### list_formal_context_plans(project_id)

Returns formal context plan index metadata.

Metadata-only. Must not return chapter text, prompt text, or plaintext secrets.

### read_formal_context_plan(project_id, plan_id)

Returns one formal context plan artifact.

May return category work items, priority order, text statistics, safety flags, and recommendation. Must not return chapter text, prompt text, raw Provider responses, request bodies, or plaintext secrets.

### context_assembly_dry_run(project_id, max_context_tokens=None)

Builds a metadata-only preview of future local context assembly.

Returns:

```text
project_id
mode
token_budget
provider_api_boundary
selected
skipped
candidates
warnings
```

`provider_api_boundary` must show:

```text
llm_api_accepts_priority_fields=false
requires_local_context_assembly=true
provider_called=false
output_contains_prompt_text=false
output_contains_chapter_text=false
```

Candidate items may include source type, ids, category id, priority, memory weight, estimated tokens, character count, and reason. They must not include prompt text, chapter text, Memory Bank text, raw Provider responses, request bodies, or plaintext secrets.

Disabled Memory Bank items remain visible as metadata candidates but must be skipped with:

```text
skip_reason=memory_item_disabled
```

This method is read-only. It must not write artifacts, mutate Memory Bank, update RAG/export, create drafts, create confirmed chapters, or call Providers.

### context_package_preview(project_id, max_context_tokens=None, include_text=False)

Builds a read-only local context package preview from enabled manual Memory Bank items.

Returns:

```text
project_id
mode
token_budget
provider_api_boundary
include_text
sections
skipped
warnings
```

Default behavior:

```text
include_text=false
```

With default behavior, section output may include ids, category id, priority, memory weight, estimated tokens, character count, lifecycle metadata, and selection status, but must not include the Memory Bank `text` field.

With `include_text=true`, selected sections may include manual Memory Bank text for explicit human review. This is not a Provider prompt and must not be logged as one.

Selection rules:

```text
enabled=false -> skip_reason=memory_item_disabled
status not ready or empty text -> skip_reason=manual_text_missing
budget overflow -> skip_reason=token_budget_exceeded
```

Provider boundary:

```text
provider_called=false
final_prompt_rendering=not_implemented
```

This method must not write artifacts, call Providers, read chapter content, write prompt logs, update world book, update RAG/export, create drafts, create confirmed chapters, or return plaintext secrets.

### enqueue_formal_context_tasks(project_id, plan_id)

Creates metadata-only manual tasks from one formal context plan.

Writes:

```text
data/formal_context_task_queue.json
```

Returns:

```text
created_count
total_count
items
```

Each task may include:

```text
task_id
plan_id
preview_id
update_id
chapter_id
title
category_id
priority
target
memory_weight
recommendation
status
created_at
updated_at
safety
```

This is idempotent by `plan_id + category_id`. It must not return or store chapter text, prompt text, Memory Bank text, raw Provider responses, request bodies, or plaintext secrets. It must not update Memory Bank, world book, RAG, exports, drafts, confirmed chapters, or Providers.

### list_formal_context_tasks(project_id, status="")

Returns formal context manual task metadata.

Optional `status` filter:

```text
pending
acknowledged
skipped
```

Metadata-only. Must not return chapter text, prompt text, Memory Bank text, or plaintext secrets.

### mark_formal_context_task(project_id, task_id, status, reason_code="")

Updates one formal context task status.

Allowed statuses:

```text
pending
acknowledged
skipped
```

`reason_code` must use safe ASCII letters, numbers, `_`, or `-`.

This marks task metadata only. It must not update Memory Bank, world book, RAG, exports, drafts, confirmed chapters, or Providers.

### create_memory_apply_preview(project_id, status="pending")

Creates a metadata-only preview before any Memory Bank write.

Writes:

```text
data/memory_apply_previews/*.json
data/memory_apply_previews_index.json
```

Returns:

```text
preview_id
status
task_count
path
created_at
```

The preview artifact may include:

```text
preview_id
status
created_at
source
task_status_filter
task_count
world_book_enabled
items
summary
safety
recommendation
```

Each item may include task id, plan id, category id, priority, target, memory weight, duplicate-risk metadata, and proposed action. Items must not include chapter text, prompt text, Memory Bank text, raw Provider responses, request bodies, or plaintext secrets.

This method must not write `memory_bank.json`, update world book, update RAG/export, create drafts, create confirmed chapters, or call Providers.

### list_memory_apply_previews(project_id)

Returns Memory Apply Preview index metadata.

Metadata-only. Must not return chapter text, prompt text, Memory Bank text, or plaintext secrets.

### read_memory_apply_preview(project_id, preview_id)

Returns one Memory Apply Preview artifact.

May return candidate metadata, safety flags, duplicate-risk metadata, and recommendation. Must not return chapter text, prompt text, Memory Bank text, raw Provider responses, request bodies, or plaintext secrets.

### commit_memory_apply_preview(project_id, preview_id)

Explicitly commits one Memory Apply Preview into placeholder Memory Bank entries.

Writes:

```text
data/memory_bank.json
```

Creates a pre-write checkpoint:

```text
label=pre_memory_apply
```

Returns:

```text
preview_id
status
created_count
skipped_count
checkpoint
committed_at
```

Written entries must be placeholders only:

```text
entry_type=formal_context_placeholder
status=manual_text_required
text=""
text_status=not_extracted
```

Repeated commits of the same preview must skip duplicate source tasks rather than writing duplicate Memory Bank entries.

This method must not extract or copy chapter text, prompt text, existing Memory Bank text, raw Provider responses, request bodies, or plaintext secrets. It must not update world book, update RAG/export, create drafts, create confirmed chapters, or call Providers.

### list_memory_items(project_id, include_text=False)

Returns Memory Bank item metadata from:

```text
data/memory_bank.json
```

Default output is metadata-only and excludes the `text` field. It may include:

```text
memory_id
entry_type
status
source ids
chapter_id
category_id
priority
target
memory_weight
duplicate_risk
enabled
lifecycle_status
lifecycle_reason_code
text_status
text_chars
created_at
updated_at
```

`include_text=True` is reserved for explicit human review surfaces. It must not be used by default state, list, or audit-style outputs.

### read_memory_item(project_id, memory_id, include_text=False)

Returns one Memory Bank item.

Default output excludes `text`. With `include_text=True`, this method may return the manual Memory Bank text for human review.

Must not return prompt text, chapter text, raw Provider responses, request bodies, or plaintext secrets.

### set_memory_text(project_id, memory_id, text)

Explicitly writes manual text into one Memory Bank placeholder item.

Creates a pre-write checkpoint:

```text
label=pre_memory_text_update
```

Validation:

```text
text must be nonempty after trimming
text length <= 1200 characters
obvious sk-/cpk_-style secret strings are rejected
```

Returns metadata only:

```text
memory_id
status
text_chars
checkpoint
updated_at
```

The returned value must not include the written text. The operation may set:

```text
status=ready
text_status=manual
safety.manual_text=true
safety.provider_called=false
```

This method must not call Providers, auto-extract from chapters, update world book, update RAG/export, create drafts, create confirmed chapters, or auto-assemble Provider prompts.

### set_memory_item_enabled(project_id, memory_id, enabled, reason_code="")

Explicitly changes the lifecycle switch for one Memory Bank item.

Creates a pre-write checkpoint:

```text
label=pre_memory_lifecycle_update
```

Validation:

```text
reason_code is optional
reason_code must use ASCII letters, numbers, "_" or "-"
reason_code length <= 80 characters
```

Returns metadata only:

```text
memory_id
enabled
lifecycle_status
reason_code
checkpoint
updated_at
```

When `enabled=false`, future Context Assembler dry-runs must keep the item on disk but skip it with:

```text
skip_reason=memory_item_disabled
```

This method must not delete files, alter Memory Bank text, call Providers, update world book, update RAG/export, create drafts, create confirmed chapters, or auto-assemble Provider prompts.

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

### provider_status(project_id, role)

Runs a local Provider configuration check for one role.

Returns:

```text
ok
role
provider
model
mode
message
has_api_key
masked_key
adapter_enabled
network_allowed
error_type
real_generation_enabled
```

Must not send network requests.

Must not create drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

Must not return plaintext secrets.

### provider_dry_run(project_id, role, prompt, system_prompt="", temperature=None, max_tokens=None, metadata=None)

Builds a no-network Provider request summary for one role.

Returns:

```text
ok
role
provider
model
mode
message
adapter_enabled
network_allowed
error_type
request_summary
real_generation_enabled
```

`request_summary` may include only:

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

Must not send network requests.

Must not create drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

Must not return prompt text, system prompt text, full request bodies, raw response content, or plaintext secrets.

### provider_real_test(project_id, role, prompt="Return exactly OK.", system_prompt="", temperature=0, max_tokens=16, metadata=None)

Runs one explicitly approved real network test for a supported Provider.

Current supported Provider:

```text
chutes_openai
```

Returns:

```text
ok
role
provider
model
mode
message
network_attempted
status_code
error_type
base_url_host
finish_reason
usage
response_text_chars
```

Must not create drafts, create confirmed chapters, update Memory Bank, update RAG, create exports, or write provider call logs.

Must not return prompt text, system prompt text, full request bodies, raw response content, or plaintext secrets.

### list_provider_adapters()

Returns registered Provider adapter metadata:

```text
adapter_id
enabled
network_allowed
requires_secret
description
```

Metadata-only. Must not read project secrets and must not send network requests.

## Provider Contract Summary

Current enabled Provider:

```text
mock
```

Current disabled dry-run Provider ids:

```text
openai_compatible
deepseek
chutes_openai
```

Future real Providers must:

- read secrets only through `secrets.local.json`,
- use `project_secret.<name>` references in config,
- never write plaintext keys to `config.json`,
- never log prompt text or plaintext secrets in provider logs,
- pass `audit-project` before being considered safe for normal use.

Current controlled real-generation Provider:

```text
chutes_openai writer only, gated by settings.real_generation_enabled=true
```

The Chutes gate keeps the adapter registry disabled, ignores the expected `provider_adapter_disabled` audit finding, and blocks only key/prompt/content leak findings plus secret resolution failures.

Provider error types currently used:

```text
missing_provider
unsupported_provider
adapter_disabled
missing_model
missing_secret_ref
missing_secret
empty_secret
invalid_secret_ref
invalid_request
rate_limit
timeout
real_generation_disabled
unsupported_real_provider
audit_gate_failed
http_error
network_error
invalid_response
empty_response
```
