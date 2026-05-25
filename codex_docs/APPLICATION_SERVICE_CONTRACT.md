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

### prepublish_check(repo_root=None)

Runs a read-only publication readiness check for the source tree and configured runtime projects root.

Returns:

```text
ok
repo_root
projects_root
findings
checked_paths
summary
```

Blocking findings include missing required ignore patterns, publishable secret/env files, real-corpus sample artifacts, and high-risk audit leaks such as secrets, prompt text, content, corpus sample blockers, or invalid Provider smoke-test artifacts. Disabled Provider adapters or missing runtime Provider secrets remain visible in `audit-project`, but they are not prepublish findings unless they leak sensitive content or create a blocking audit condition.

This method must not modify files, delete files, read external corpus text, call Providers, create drafts, create confirmed chapters, update Memory Bank/RAG/export, or print plaintext secrets/sample text.

### project_health(project_id, repo_root=None)

Returns a metadata-only runtime health summary for one project.

Combines:

```text
public project state
project audit summary
Provider role summary
latest Provider smoke-test metadata
optional prepublish upload readiness
```

Returns:

```text
project_id
generated_at
status
next_gate
summary
provider
drafts
smoke_tests
audit
upload_readiness
```

`status` is `blocked` when audit or prepublish has blockers, `warning` when only warnings remain, and `ok` when no blockers or warnings are present. `upload_readiness` is checked only when `repo_root` is provided.

This method must not return prompt text, draft/chapter content, Provider response text, request bodies, raw Provider responses, plaintext secrets, secret values, or corpus sample text. It must not modify files, call Providers, create drafts, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, delete files, or auto-commit.

### profile_corpus(path, max_name_candidates=20)

Reads one external text corpus in read-only metadata mode.

Returns:

```text
source file metadata
encoding detection
line/chapter structure counts
chapter length statistics
dialogue proxy counts
rough name candidate frequencies
safety flags
```

This method must not initialize a project root, write project files, call Providers, copy chapter/source text, create drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

Name candidates are frequency heuristics only and may include false positives. They are not a character database.

### save_corpus_profile(project_id, path, max_name_candidates=20)

Explicitly saves a conservative metadata-only corpus profile artifact inside one project.

Writes:

```text
data/corpus_profiles/*.json
data/corpus_profiles_index.json
```

Persistent artifacts may include encoding, line/chapter counts, chapter statistics, dialogue proxy counts, source file name, source size, and source file SHA-256.

Persistent artifacts must not store:

```text
external source path
source text
chapter heading text
dialogue/source excerpts
candidate-name text
plaintext secrets
```

This method must not import the corpus, create drafts, create confirmed chapters, call Providers, update Memory Bank, update RAG, or create exports.

### list_corpus_profiles(project_id)

Returns corpus profile index metadata.

Metadata-only. Must not return source text, external source path, candidate-name text, or plaintext secrets.

### read_corpus_profile(project_id, profile_id)

Returns one conservative corpus profile artifact.

Metadata-only. Must not return source text, external source path, candidate-name text, or plaintext secrets.

### save_corpus_boundaries(project_id, path)

Explicitly saves a no-text chapter boundary index for one external corpus file.

Writes:

```text
data/corpus_boundaries/*.json
data/corpus_boundaries_index.json
```

Boundary entries may include:

```text
ordinal
heading_line_number
body_start_line
body_end_line
body_start_char
body_end_char
body_char_count
```

Persistent boundary artifacts must not store:

```text
external source path
source text
chapter heading text
dialogue/source excerpts
candidate-name text
plaintext secrets
```

This method must not import the corpus, create drafts, create confirmed chapters, call Providers, update Memory Bank, update RAG, or create exports.

### list_corpus_boundaries(project_id)

Returns corpus boundary index metadata.

Metadata-only. Must not return source text, external source path, heading text, excerpts, or plaintext secrets.

### read_corpus_boundaries(project_id, boundary_id)

Returns one no-text boundary artifact.

Metadata-only. Must not return source text, external source path, heading text, excerpts, or plaintext secrets.

### create_corpus_sample(project_id, boundary_id, source_path, ordinal, max_chars=800)

Explicitly creates a bounded real-text sample from a corpus boundary.

Writes:

```text
data/corpus_samples/*.json
data/corpus_samples_index.json
```

This is a test-only quarantine feature. It may persist bounded source text, but the artifact must include:

```text
test_only=true
publish_blocker=true
required_cleanup
```

Validation:

```text
source file SHA-256 must match the boundary artifact source SHA-256
ordinal must exist in the boundary artifact
max_chars must be between 1 and 2000
```

Default facade/CLI outputs must not return sample text. Sample text is only returned through explicit `include_text=true` / `--include-text`.

This method must not create drafts, create confirmed chapters, call Providers, update Memory Bank, update RAG, create exports, or store the external source path.

### list_corpus_samples(project_id)

Returns corpus sample index metadata.

Metadata-only. Must not return sample text, external source path, prompt text, or plaintext secrets.

### read_corpus_sample(project_id, sample_id, include_text=False)

Returns one corpus sample artifact.

Default behavior:

```text
include_text=false
```

Default output must not include `sample_text`.

With `include_text=true`, this method may return bounded real corpus text for local testing only. This content is non-publishable and must be removed before GitHub publication.

### create_self_style_baseline(project_id)

Creates a local metadata-only style baseline from the project's own confirmed chapters.

Writes:

```text
data/style_baselines/*.json
data/style_baselines_index.json
```

Metrics may include:

```text
chapter length distributions
paragraph count distributions
sentence count and average sentence length
dialogue-line ratio
punctuation frequency per 1000 nonspace characters
```

This method reads confirmed chapter text in memory only. Persistent artifacts must not store chapter text, prompt text, external corpus text, source paths, raw Provider responses, or plaintext secrets.

This method must not read external corpus files, call Providers, create drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

### list_self_style_baselines(project_id)

Returns style baseline index metadata.

Metadata-only. Must not return confirmed chapter text, prompt text, external corpus text, or plaintext secrets.

### read_self_style_baseline(project_id, baseline_id)

Returns one style baseline artifact.

Metadata-only. Must not return confirmed chapter text, prompt text, external corpus text, or plaintext secrets.

### check_draft_style(project_id, draft_id, baseline_id="", scene_mode="general")

Creates a local metadata-only style check comparing one draft to a self-style baseline.

Writes:

```text
data/style_checks/*.json
data/style_checks_index.json
```

If `baseline_id` is empty, the latest self-style baseline is used.

Supported scene modes:

```text
general
daily
romance
battle
climax
exposition
transition
custom
```

Style checks are hints, not pass/fail grading. `scene_mode` adjusts tolerance so deliberately different chapters, such as exposition, battle, climax, daily, romance, or transition chapters, are not forced toward the global average.

Project-level defaults live at:

```text
config.context_policy.style_check_policy
```

Fields:

```text
enabled
calibration_enabled
show_hints
default_scene_mode
severity_mode
auto_create_revision_request
ui_placement
```

`auto_create_revision_request` must remain `false` unless a later explicit operator workflow is implemented.

Checks may include:

```text
chapter length vs baseline P25/P50/P75
paragraph count vs baseline P25/P50/P75
sentence count vs baseline P25/P50/P75
dialogue-line ratio vs baseline P25/P50/P75
average sentence and paragraph length
selected punctuation frequency
```

This method reads draft text in memory only. Persistent artifacts must not store draft text, prompt text, confirmed chapter text, external corpus text, raw Provider responses, or plaintext secrets.

This method must not call Providers, create drafts, create confirmed chapters, create revision requests, auto-revise drafts, auto-commit drafts, update Memory Bank, update RAG, or create exports. If style checks are disabled by policy, the method must fail without writing a style check artifact.

### list_draft_style_checks(project_id)

Returns draft style check index metadata.

Metadata-only. Must not return draft text, prompt text, generated content, or plaintext secrets.

### read_draft_style_check(project_id, check_id)

Returns one draft style check artifact.

Metadata-only. Must not return draft text, prompt text, generated content, or plaintext secrets.

### create_style_suggestion(project_id, check_id)

Creates a local metadata-only suggestion artifact from one draft style check.

Writes:

```text
data/style_suggestions/*.json
data/style_suggestions_index.json
```

The suggestions are manual review aids. They may name a metric, direction, severity, and generic action, but they must not contain draft text, prompt text, generated content, confirmed chapter text, external corpus text, raw Provider responses, or plaintext secrets.

This method must not call Providers, modify drafts, create revision requests, auto-revise drafts, auto-commit drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

### list_style_suggestions(project_id)

Returns style suggestion index metadata.

Metadata-only. Must not return draft text, prompt text, generated content, or plaintext secrets.

### read_style_suggestion(project_id, suggestion_id)

Returns one style suggestion artifact.

Metadata-only. Must not return draft text, prompt text, generated content, or plaintext secrets.

### decide_style_suggestion(project_id, suggestion_id, decision, reason_code="")

Records an explicit manual decision on a style suggestion.

Supported decisions:

```text
accepted
ignored
needs_manual_rewrite
```

The method updates only:

```text
data/style_suggestions/*.json
data/style_suggestions_index.json
```

`reason_code` is a short ASCII code, not free-form prose. This method must not accept or persist draft text, prompt text, generated content, or plaintext secrets.

This method must not apply edits, mutate draft content, create revision requests, auto-revise drafts, auto-commit drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports. A style suggestion can be decided only once.

### create_manual_rewrite_task(project_id, suggestion_id)

Creates a metadata-only human rewrite task from a style suggestion whose manual decision is `needs_manual_rewrite`.

Writes:

```text
data/manual_rewrite_tasks/*.json
data/manual_rewrite_tasks_index.json
```

Task metadata includes:

```text
task_id
suggestion_id
check_id
draft_id
chapter_id
status
reason_code
created_at
safety
```

The method must reject suggestions decided as `accepted` or `ignored`. It must also reject duplicate tasks for the same suggestion.

This method must not call Providers, generate a draft, modify drafts, create revision requests, auto-revise drafts, auto-commit drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports.

### list_manual_rewrite_tasks(project_id, status="")

Returns manual rewrite task index metadata. Optional `status` can filter `pending`, `in_progress`, `done`, or `skipped`.

Metadata-only. Must not return draft text, prompt text, generated content, or plaintext secrets.

### read_manual_rewrite_task(project_id, task_id)

Returns one manual rewrite task artifact.

Metadata-only. Must not return draft text, prompt text, generated content, or plaintext secrets.

### mark_manual_rewrite_task(project_id, task_id, status, reason_code="")

Marks a manual rewrite task as `pending`, `in_progress`, `done`, or `skipped`.

This updates task metadata only. It must not modify drafts, create new drafts, create revision requests, commit chapters, call Providers, or update Memory Bank/RAG/export.

### submit_manual_rewrite_draft(project_id, task_id, text)

Submits explicit human rewrite text as a new draft candidate.

Writes:

```text
data/drafts/*.json
data/drafts_index.json
data/manual_rewrite_tasks/*.json
data/manual_rewrite_tasks_index.json
```

The new draft must have a new `draft_id` and must not overwrite the source draft. The draft artifact stores the submitted text as `content` because draft artifacts are the explicit place where human-visible draft text lives.

The draft artifact must include:

```text
manual_rewrite.manual_rewrite_task_id
manual_rewrite.source_suggestion_id
manual_rewrite.source_check_id
manual_rewrite.source_draft_id
```

The command/facade result must be metadata-only and must not return submitted text. The submitted content may only be retrieved through `read_draft`.

This method must not call Providers, create revision requests, auto-commit drafts, create confirmed chapters, update Memory Bank, update RAG, or create exports. Empty text, skipped tasks, and duplicate submissions must be rejected.

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
corpus_boundary_count
corpus_profile_count
corpus_sample_count
self_style_baseline_count
draft_style_check_count
style_suggestion_count
formal_context_plan_count
formal_context_task_count
manual_rewrite_task_count
manual_rewrite_comparison_count
review_handoff_count
memory_apply_preview_count
memory_bank_item_count
final_assembly_gate_count
final_provider_runbook_count
final_provider_authorization_count
final_provider_execution_preflight_count
planning_item_count
active_planning_reference_count
chapter_count
committed_chapter_count
latest_chapter
latest_draft
latest_review
latest_revision_request
latest_context_update
latest_context_preview
latest_corpus_boundary
latest_corpus_profile
latest_corpus_sample
latest_self_style_baseline
latest_draft_style_check
latest_style_suggestion
latest_formal_context_plan
latest_formal_context_task
latest_manual_rewrite_task
latest_manual_rewrite_comparison
latest_review_handoff
latest_memory_apply_preview
latest_memory_bank_item
latest_final_assembly_gate
latest_final_provider_runbook
latest_final_provider_authorization
latest_final_provider_execution_preflight
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
clear_secret_after_run
```

Required order:

```text
audit precheck
secret/config setup
generate draft
optional secret cleanup
audit postcheck
metadata-only summary
```

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

Before saving draft content, Provider output must pass through the response sanitizer. The sanitizer removes `<think>...</think>` reasoning blocks and standalone `<think>` tags from saved `content`, then records metadata only:

```text
request_summary.response_sanitizer.reasoning_markup_detected
request_summary.response_sanitizer.reasoning_blocks_removed
request_summary.response_sanitizer.reasoning_tags_removed
request_summary.response_sanitizer.chars_removed
```

Sanitized reasoning text must not be stored in the draft artifact, draft index, commit log, review metadata, public state, Memory Bank, RAG, export files, or UI-facing output.

On successful draft generation, chapter workflow state may update to `draft_ready` with `latest_draft_id`.

On generation failure, chapter workflow state may update to `blocked` with metadata-only error summary.

### generate_context_draft(...)

Inputs:

```text
project_id
chapter_id
prompt
title
system_prompt
temperature
max_tokens
max_context_tokens
final_assembly_gate_id
metadata
```

Current phase requirement:

```text
writer provider must be mock
```

This method builds a prompt render dry-run with local text inclusion internally, renders a combined in-memory prompt, and sends it to the local mock writer only.

If the writer role is not `mock`, this method must require a matching approved final assembly gate before any Provider call, draft write, or chapter workflow mutation. Passing that gate does not enable real context-aware Provider generation in this phase; the method must still fail closed after the gate check.

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

The draft artifact may include:

```text
context_generation.mode
context_generation.context_section_count
context_generation.skipped_context_count
context_generation.context_source_ids
context_generation.prompt_summary
```

It must not store operator prompt text, Memory Bank text, raw Provider responses, request bodies, or plaintext secrets in artifact metadata, indexes, logs, facade output, CLI output, or public state.

It must not call real Providers, auto-commit, update Memory Bank text, update world book, update RAG/export, create DOCX, or mutate confirmed chapters.

### list_drafts(project_id)

Returns draft metadata from `data/drafts_index.json`.

Metadata-only. Must not return prompt text or generated content.

### read_draft(project_id, draft_id)

Returns the draft artifact.

May return generated draft content for human review.

Must not return original prompt text or plaintext secrets.

### commit_draft(project_id, draft_id)

Explicitly promotes a draft to confirmed chapter.

Current commit gate:

```text
The same draft must have a review whose manual decision is accepted.
```

Drafts without an accepted review, drafts with pending review decisions, drafts marked `needs_revision`, and drafts marked `blocked` must fail before confirmed files, checkpoints, commit logs, or draft status are written. This gate failure must not mark the chapter as `blocked`; the operator should still be able to review and accept the draft afterward.

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

Confirmed chapter artifacts and commit logs may record metadata-only `commit_gate` fields such as `review_id`, `decision`, `reason_code`, and `decided_at`. They must not record review comments, draft content in commit logs, prompt text, or plaintext secrets.

On successful explicit commit, chapter workflow state updates to `committed` with `confirmed_chapter_id`.

On failed commit after the gate passes, chapter workflow records metadata-only error. If the chapter is already `committed`, it must not be downgraded to `blocked`.

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

Before scorer execution, the review path must run the reasoning leak guard. If draft content contains `<think` or `</think>`, the service must skip scorer Provider calls, write a metadata-only review with `provider=local_guard`, issue code `reasoning_leak_detected`, and automatic decision:

```text
status=needs_revision
reason_code=reasoning_leak
```

This guard must not store the leaked reasoning text in review artifacts or indexes.

If the draft is a submitted manual rewrite draft candidate, review is allowed only when one matching gate exists:

```text
selected_for_review manual rewrite comparison
pending_review review handoff
```

Rejected or `needs_more_manual_work` comparisons are not valid gates. Missing gate must fail before any Provider call, review artifact write, or chapter workflow mutation.

On success, chapter workflow state may update to `review_ready` with `latest_review_id`.

Must not auto-commit, auto-revise, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or enable real Providers.

Must not return draft content, original prompt text, raw Provider responses, request bodies, or plaintext secrets.

For a successful manual rewrite candidate review, `request_summary.manual_rewrite_review_gate` may record metadata-only gate fields such as `required`, `allowed`, `matched_gate`, `comparison_id`, and `handoff_id`.

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

Candidate items may include source type, ids, category id, priority, memory weight, estimated tokens, character count, and reason. They must not include prompt text, chapter text, Planning Library text, Memory Bank text, raw Provider responses, request bodies, or plaintext secrets.

Disabled Memory Bank items remain visible as metadata candidates but must be skipped with:

```text
skip_reason=memory_item_disabled
```

Inactive or disabled Planning Library items remain visible as metadata candidates but must be skipped with:

```text
skip_reason=planning_item_inactive
skip_reason=planning_item_disabled
```

This method is read-only. It must not write artifacts, mutate Memory Bank, update RAG/export, create drafts, create confirmed chapters, or call Providers.

### context_package_preview(project_id, max_context_tokens=None, include_text=False)

Builds a read-only local context package preview from active/enabled Planning Library items and enabled manual Memory Bank items.

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

With default behavior, section output may include ids, category id, priority, memory weight, estimated tokens, character count, lifecycle metadata, and selection status, but must not include Planning Library or Memory Bank `text` fields.

With `include_text=true`, selected sections may include manual Planning Library and Memory Bank text for explicit human review. This is not a Provider prompt and must not be logged as one.

Selection rules:

```text
enabled=false -> skip_reason=memory_item_disabled
planning active=false -> skip_reason=planning_item_inactive
planning enabled=false -> skip_reason=planning_item_disabled
status not ready or empty text -> skip_reason=manual_text_missing
budget overflow -> skip_reason=token_budget_exceeded
```

Provider boundary:

```text
provider_called=false
final_prompt_rendering=dry_run_only
```

This method must not write artifacts, call Providers, read chapter content, write prompt logs, update world book, update RAG/export, create drafts, create confirmed chapters, or return plaintext secrets.

### prompt_render_dry_run(project_id, prompt, system_prompt="", max_context_tokens=None, include_prompt_text=False, include_context_text=False)

Builds a no-write redacted envelope for future Provider prompt rendering.

Returns:

```text
project_id
mode
provider_api_boundary
include_prompt_text
include_context_text
prompt_summary
context_package
rendered_messages
warnings
```

Default behavior:

```text
include_prompt_text=false
include_context_text=false
```

Default output must not include operator prompt text, system prompt text, Planning Library text, or Memory Bank text. It may return character counts, selected/skipped context metadata, estimated tokens, and message roles.

Explicit text flags:

```text
include_prompt_text=true
include_context_text=true
```

These flags are for human local inspection only. The result is still not a Provider call and must not be persisted as a prompt log by this service.

Provider boundary:

```text
provider_called=false
writes_project_files=false
final_prompt_for_provider=false
```

This method must not write artifacts, call Providers, create drafts, read confirmed chapter content, update world book, update RAG/export, create prompt logs, create confirmed chapters, or return plaintext secrets.

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

Context-aware draft audit checks include:

```text
invalid_context_generation_draft_index_entry
unsafe_context_generation_draft_path
missing_context_generation_draft_artifact
context_generation_metadata_missing
context_generation_mode_invalid
context_generation_text_flag_invalid
context_generation_section_count_mismatch
possible_secret_in_context_generation
possible_prompt_in_context_generation
context_generation_forbidden_metadata_key
```

Audit checks `context_generation` metadata and drafts index consistency. It does not flag normal draft `content` merely because draft artifacts are allowed to contain generated text for human review.

Corpus profile artifact audit checks include:

```text
corpus_boundary_source_path_stored
corpus_boundary_text_field_stored
corpus_sample_source_path_stored
non_publishable_corpus_sample_present
corpus_profile_source_path_stored
corpus_profile_candidate_names_stored
possible_prompt_in_corpus_boundary
possible_secret_in_corpus_boundary
possible_content_in_corpus_boundary
possible_secret_in_corpus_sample
possible_secret_in_corpus_sample_index
possible_prompt_in_corpus_profile
possible_secret_in_corpus_profile
possible_content_in_corpus_profile
```

Audit must fail if a persistent corpus profile stores an external source path or candidate-name text, if a corpus boundary artifact stores an external source path, heading text, source text, chapter text, or excerpt fields, or if any non-publishable corpus sample artifact exists.

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
chutes_openai writer only, through explicit user-triggered generation or connection-test commands
```

The Chutes path requires safe Provider configuration, secret resolution for remote Providers, and key/prompt/content leak checks.

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

## Manual Rewrite Comparison Facade

### compare_manual_rewrite_candidate(project_id, task_id)

Creates a metadata-only comparison between a manual rewrite task's source draft and submitted draft candidate.

Writes:

```text
data/manual_rewrite_comparisons/*.json
data/manual_rewrite_comparisons_index.json
```

Returns metadata only:

```text
comparison_id
task_id
suggestion_id
check_id
chapter_id
source_draft_id
submitted_draft_id
char_count_delta
paragraph_count_delta
path
created_at
```

It does not return source or submitted draft text.

### list_manual_rewrite_comparisons(project_id, status="")

Returns index metadata only. It may be filtered by `comparison_ready`, `selected_for_review`, `rejected`, or `needs_more_manual_work`.

### read_manual_rewrite_comparison(project_id, comparison_id)

Returns the comparison artifact. The artifact contains ids, structural metrics, deltas, link checks, safety flags, and decision metadata. It must not contain draft text, prompt text, Provider raw output, or plaintext secrets.

### decide_manual_rewrite_comparison(project_id, comparison_id, decision, reason_code="")

Records a one-time operator decision.

Allowed decisions:

```text
selected_for_review
rejected
needs_more_manual_work
```

The `reason_code` is optional short ASCII metadata. This method does not call Providers, modify draft bodies, create revision requests, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

## Review Handoff Facade

### create_review_handoff_from_manual_comparison(project_id, comparison_id)

Creates a metadata-only pending-review handoff from a manual rewrite comparison already decided as `selected_for_review`.

Writes:

```text
data/review_handoffs/*.json
data/review_handoffs_index.json
```

Returns metadata only:

```text
handoff_id
comparison_id
task_id
chapter_id
selected_draft_id
status
path
created_at
```

This method rejects pending, rejected, or `needs_more_manual_work` comparisons. It does not call Providers, create a review, modify draft bodies, auto-commit, create confirmed chapters, or update Memory Bank/RAG/export.

### list_review_handoffs(project_id, status="")

Returns review handoff index metadata only. It may be filtered by `pending_review` or `review_created`.

### read_review_handoff(project_id, handoff_id)

Returns one handoff artifact. The artifact contains ids, the selected draft reference, source decision metadata, pending-review status, and safety flags. It must not contain draft text, prompt text, Provider raw output, or plaintext secrets.

When a `pending_review` handoff is used as the gate for a successful `review-draft`, the handoff may be consumed into:

```text
status=review_created
review.created=true
review.review_id=<created review id>
```

This update is metadata only. It must not edit draft bodies, create drafts, auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, or call an extra Provider beyond the explicit review operation.

## Planning Library Facade

### create_planning_item(project_id, planning_id, text, ...)

Creates one manual Planning Library item in `data/planning_library.json`.

Default fields include:

```text
title
item_type
active
enabled
priority
adherence_level
send_mode
chapter_range
```

The method rejects empty text, oversized text, duplicate ids, unsafe ids, invalid choices, and secret-like values. It creates a checkpoint before writing. Returned data is metadata-only and must not include the planning text.

### list_planning_items(project_id, include_text=False)

Returns Planning Library metadata. Default output excludes `text`; `text_chars` is allowed.

With `include_text=True`, the method may return manual planning text for explicit human review only.

### read_planning_item(project_id, planning_id, include_text=False)

Returns one Planning Library item. Default output excludes `text`; explicit `include_text=True` may expose the manual planning text.

### set_planning_item_active(project_id, planning_id, active)

Sets the active switch for one item and refreshes `active_reference_ids`. Inactive items must not enter Context Assembler selected sections.

### set_planning_item_enabled(project_id, planning_id, enabled)

Sets the lifecycle switch for one item and refreshes `active_reference_ids`. Disabled items remain on disk but must be skipped by Context Assembler.

Planning Library operations must not call Providers, generate drafts, mutate draft bodies, auto-commit, create confirmed chapters, update Memory Bank, update RAG, create exports, create DOCX, or run UI workflows.

## Final Assembly Gate Facade

### create_final_assembly_gate(project_id, chapter_id, prompt, system_prompt="", max_context_tokens=None)

Creates a metadata-only approval artifact for a future real context-aware Provider request.

Writes:

```text
data/final_assembly_gates/*.json
data/final_assembly_gates_index.json
```

The artifact may store:

```text
gate_id
chapter_id
writer provider/model metadata
prompt_digest
system_prompt_digest
context_digest
prompt/context character counts
token estimates
selected/skipped context section summaries
approval metadata
safety flags
```

It must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, request bodies, or plaintext secrets.

### approve_final_assembly_gate(project_id, gate_id, reason_code="")

Approves one pending final assembly gate.

`reason_code` is optional short ASCII metadata. Duplicate approval must fail. This method must not call Providers, create drafts, mutate workflow state, update Memory Bank/RAG/export, create DOCX, or print prompt/context text.

### list_final_assembly_gates(project_id, status="")

Returns gate index metadata. Optional `status` can filter `pending_approval` or `approved`.

Default output must remain metadata-only and must not return prompt/context text or plaintext secrets.

### read_final_assembly_gate(project_id, gate_id)

Returns one gate artifact. The artifact is metadata-only by design.

Future real context-aware Provider paths must compare the approved gate against the current request and assembled context by digest before any Provider or workflow side effect. A mismatch in chapter id, prompt digest, system prompt digest, context digest, provider, or model must fail closed.

## Final Provider Runbook Facade

### create_final_provider_runbook(project_id, gate_id)

Creates a metadata-only operator runbook from an approved final assembly gate.

Writes:

```text
data/final_provider_runbooks/*.json
data/final_provider_runbooks_index.json
```

The artifact may store:

```text
runbook_id
gate_id
chapter_id
pending_operator_authorization status
writer provider/model metadata
prompt/system/context/gate digests
prompt/context character counts
token estimates
selected context section counts/types
operator checklist flags
safety flags
```

It must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, request bodies, or plaintext secrets. It must not call real LLMs, create or overwrite drafts, mutate workflow state, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, or delete files.

### list_final_provider_runbooks(project_id, status="")

Returns runbook index metadata. Optional `status` can filter `pending_operator_authorization`.

Default output must remain metadata-only and must not return prompt/context text or plaintext secrets.

### read_final_provider_runbook(project_id, runbook_id)

Returns one runbook artifact. The artifact is metadata-only and represents a stop point before future operator authorization.

## Final Provider Authorization Facade

### authorize_final_provider_runbook(project_id, runbook_id, reason_code="")

Creates a metadata-only authorization record from a pending final Provider runbook and creates a no-secrets pre-authorization checkpoint.

Writes:

```text
data/final_provider_authorizations/*.json
data/final_provider_authorizations_index.json
backups/checkpoints/*.zip
```

The artifact may store:

```text
authorization_id
runbook_id
gate_id
chapter_id
authorized_pending_execution status
writer provider/model metadata
prompt/system/context/gate/runbook/authorization digests
prompt/context character counts
token estimates
selected context section counts/types
checkpoint id/path/file count
execution boundary flags
safety flags
```

It must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, request bodies, plaintext secrets, or plaintext execution tokens. It must not call real LLMs, enable real Providers, create or overwrite drafts, mutate workflow state, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, or delete files.

### list_final_provider_authorizations(project_id, status="")

Returns authorization index metadata. Optional `status` can filter `authorized_pending_execution`.

Default output must remain metadata-only and must not return prompt/context text, plaintext secrets, or plaintext execution tokens.

### read_final_provider_authorization(project_id, authorization_id)

Returns one authorization artifact. The artifact is metadata-only and still represents a stop point before any future execute command or real Provider call.

## Final Provider Execution Preflight Facade

### create_final_provider_execution_preflight(project_id, authorization_id)

Creates a metadata-only verifier artifact for the final Provider gate/runbook/authorization/current-provider chain.

Writes:

```text
data/final_provider_execution_preflights/*.json
data/final_provider_execution_preflights_index.json
```

The artifact may store:

```text
preflight_id
authorization_id
runbook_id
gate_id
chapter_id
passed_pending_execute_authorization or blocked status
writer provider/model metadata
authorization/runbook/gate digests
prompt/context character counts
token estimates
check result ids and boolean pass/fail values
issue codes
execution boundary flags
safety flags
```

It must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, request bodies, plaintext secrets, or plaintext execution tokens. It must not call real LLMs, enable real Providers, create or overwrite drafts, mutate workflow state, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, or delete files.

### list_final_provider_execution_preflights(project_id, status="")

Returns execution preflight index metadata. Optional `status` can filter `passed_pending_execute_authorization` or `blocked`.

Default output must remain metadata-only and must not return prompt/context text, plaintext secrets, or plaintext execution tokens.

### read_final_provider_execution_preflight(project_id, preflight_id)

Returns one execution preflight artifact. The artifact is metadata-only and still does not execute any Provider call.

## Final Provider Execution Attempt Facade

### attempt_final_provider_execution(project_id, preflight_id)

Creates a fail-closed execution attempt artifact from a passed zero-issue final Provider execution preflight.

Writes:

```text
data/final_provider_execution_attempts/*.json
data/final_provider_execution_attempts_index.json
```

The artifact may store:

```text
attempt_id
preflight_id
authorization_id
runbook_id
gate_id
chapter_id
aborted_real_llm_disabled status
real_llm_disabled_by_policy abort reason
writer provider/model metadata
authorization/runbook/gate digests
prompt/context character counts
token estimates
execution boundary flags
safety flags
```

It requires a preflight with `status=passed_pending_execute_authorization` and `issue_count=0`. Duplicate attempts for the same preflight must fail.

It must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, request bodies, plaintext secrets, or plaintext execution tokens. This stub attempt method must not call real LLMs, enable real Providers, create or overwrite drafts, mutate workflow state, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or start execution. Real Provider calls belong to the separate explicit real execution service.

### list_final_provider_execution_attempts(project_id, status="")

Returns execution attempt index metadata. Optional `status` can filter `aborted_real_llm_disabled`.

Default output must remain metadata-only and must not return prompt/context text, plaintext secrets, or plaintext execution tokens.

### read_final_provider_execution_attempt(project_id, attempt_id)

Returns one execution attempt artifact. The artifact is metadata-only and records a forced abort for the no-network stub attempt path.

## Final Provider Real Execution Readiness Facade

### create_final_provider_real_execution_readiness(project_id, attempt_id)

Creates a no-network readiness report from a fail-closed final Provider execution attempt.

Writes:

```text
data/final_provider_real_execution_readiness/*.json
data/final_provider_real_execution_readiness_index.json
```

The artifact may store:

```text
readiness_id
attempt_id
preflight_id
authorization_id
runbook_id
gate_id
chapter_id
ready_for_manual_real_llm_authorization or blocked status
writer provider/model metadata
current writer provider/model/base_url_host/api_key_ref/secret-name metadata
project-secret presence boolean
authorization/runbook/gate digests
prompt/context character counts
token estimates
manual required action ids
execution boundary flags
safety flags
```

It must not store prompt text, system prompt text, Planning Library text, Memory Bank text, draft content, Provider raw responses, request bodies, plaintext secrets, secret values, plaintext execution tokens, or generated text. It must not call real LLMs, enable real Providers, read secret values for use, create or overwrite drafts, mutate workflow state, update Memory Bank/RAG/export, create DOCX, add UI, auto-commit, delete files, or start execution.

### list_final_provider_real_execution_readiness(project_id, status="")

Returns real execution readiness index metadata. Optional `status` can filter `ready_for_manual_real_llm_authorization` or `blocked`.

Default output must remain metadata-only and must not return prompt/context text, plaintext secrets, or plaintext execution tokens.

### read_final_provider_real_execution_readiness(project_id, readiness_id)

Returns one real execution readiness artifact. The artifact is metadata-only and represents the last no-network stop before an operator supplies/authorizes Chutes execution.

## Final Provider Real Execution Facade

### execute_final_provider_real(project_id, readiness_id, prompt, system_prompt="", title="", max_context_tokens=None, temperature=None, max_tokens=None, reason_code="")

Executes the real Chutes-backed final Provider path after a ready report and digest match.

Writes:

```text
data/drafts/*.json
data/drafts_index.json
data/provider_call_log.json
data/final_provider_real_executions/*.json
data/final_provider_real_executions_index.json
```

Required:

```text
readiness status ready_for_manual_real_llm_authorization
readiness issue_count=0
current writer provider chutes_openai
approved gate digest matches provided prompt/system/context
project secret exists
```

The command calls the Chutes writer Provider and writes exactly one new draft artifact on success.

Execution artifacts must not store prompt text, system prompt text, Planning Library text, Memory Bank text, generated draft text, Provider raw responses, request bodies, plaintext secrets, secret values, or plaintext execution tokens. This method must not auto-commit, create confirmed chapters, update Memory Bank/RAG/export, create DOCX, add UI, or delete files.

### list_final_provider_real_executions(project_id, status="")

Returns real execution index metadata. Optional `status` can filter `draft_created`.

### read_final_provider_real_execution(project_id, execution_id)

Returns one real execution artifact. The artifact is metadata-only and links to the new draft id without returning generated text.

### postcheck_final_provider_real_execution(project_id, execution_id)

Runs a read-only postcheck after a real execution artifact exists.

Reads:

```text
data/final_provider_real_executions/*.json
data/drafts/*.json
data/drafts_index.json
data/confirmed_chapters.json
config.json
```

Returns:

```text
ok
status passed or failed
issue_count
issues
checks
execution_id
draft_id
chapter_id
```

The postcheck verifies that the execution status is `draft_created`, the linked draft is readable and still in `draft` status, the draft provider is `chutes_openai`, the execution boundary records no auto-commit, the chapter is not confirmed, and execution metadata does not contain forbidden text-bearing keys. It does not call Providers, read secret values, return draft content, mutate drafts, update Memory Bank/RAG/export, create DOCX, add UI, delete files, or auto-commit.

## Provider Smoke Test Facade

### run_provider_smoke_test(project_id, role="writer", prompt="Return exactly OK.", system_prompt="", temperature=0, max_tokens=16, reason_code="")

Creates a metadata-only Provider connectivity smoke-test artifact.

Writes:

```text
data/provider_smoke_tests/*.json
data/provider_smoke_tests_index.json
```

Behavior:

```text
calls provider_real_test(...)
status passed or failed
```

The artifact must store Provider/model/host, status code, finish reason, safe usage, response character count, request length metadata, user-trigger metadata, safety flags, and a safe `config_snapshot` only. The snapshot may include role, provider, model, base URL host, `api_key_ref`, secret name, and api-key-reference presence; it must not include secret values. The artifact must classify the result as `sample_only` and `non_committable`.

It must not store prompt text, system prompt text, response text, raw Provider responses, request bodies, plaintext secrets, secret values, generated draft text, or execution tokens. It must not write drafts, create confirmed chapters, auto-commit, update Memory Bank/RAG/export, create DOCX, add UI, or delete files.

`audit-project` must validate Provider smoke-test artifacts for metadata-only storage, valid status, passed/network-attempted consistency, `sample_only/non_committable` classification, and no draft or confirmed-chapter linkage. It must compare the latest passed smoke test with a config snapshot against the current role config and emit a drift finding if provider/model/host/api-key reference changed. `prepublish-check` must treat invalid Provider smoke-test artifacts as blockers and config drift as a warning.

### list_provider_smoke_tests(project_id, status="")

Returns provider smoke-test index metadata. Optional `status` can filter `passed` or `failed`.

### read_provider_smoke_test(project_id, smoke_test_id)

Returns one provider smoke-test artifact. The artifact is metadata-only and must not return prompt text, response text, raw request bodies, or plaintext secrets.
