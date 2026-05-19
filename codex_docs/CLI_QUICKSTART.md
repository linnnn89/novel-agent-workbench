# CLI Quickstart

Date: 2026-05-17, Asia/Shanghai.

## Scope

This is a backend-only local workflow. It does not start a UI, does not call a real model, does not use the network, and does not cost API credits.

Current Provider mode:

```text
mock only
```

## PowerShell Setup

Run commands from:

```powershell
cd I:\AI-NOVEL\novel_agent_workbench
$env:PYTHONPATH="I:\AI-NOVEL\novel_agent_workbench\src"
```

Use Python 3.13:

```powershell
py -3.13 -m novel_agent_workbench.cli --help
```

Recommended safe practice path for experiments:

```powershell
$env:TEMP\naw_manual_test
```

Real project path when ready:

```powershell
I:\AI-NOVEL\novel_agent_workbench\workspace_projects
```

`workspace_projects` is ignored by Git.

## One-Command Smoke

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test smoke demo_project --title "Demo Novel" --chapter-id chapter_001 --chapter-title "Opening" --prompt "Write a short mock opening." --commit
```

Expected high-level result:

```text
ok: true
draft_count: 1
committed_chapter_count: 1
```

The JSON output should not contain the original prompt text.

## Corpus Profiler

Profile a local `.txt` corpus without creating project files:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test profile-corpus "T:\path\to\novel.txt" --max-name-candidates 12
```

This command returns metadata only:

```text
encoding
line and chapter counts
chapter length statistics
dialogue proxy counts
rough name candidate frequencies
safety flags
```

It does not write project files, call Providers, copy chapter/source text, create drafts, create confirmed chapters, or update Memory Bank/RAG/export. Name candidates are heuristic and may include common-word false positives; do not treat them as a final character list.

Save a conservative project-local profile artifact:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test save-corpus-profile demo_project "T:\path\to\novel.txt" --max-name-candidates 12
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-corpus-profiles demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-corpus-profile demo_project <profile_id>
```

The saved artifact is more conservative than transient `profile-corpus`: it stores source file name, size, SHA-256, structure statistics, and safety flags, but not source text, external source path, chapter heading text, dialogue excerpts, or candidate-name text.

Save no-text chapter boundaries for future manual import planning:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test save-corpus-boundaries demo_project "T:\path\to\novel.txt"
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-corpus-boundaries demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-corpus-boundaries demo_project <boundary_id>
```

Boundary artifacts store line and character offsets only. They do not store chapter heading text, source text, excerpts, candidate names, or the external source path.

Create a temporary real-text sample for local testing only:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-corpus-sample demo_project <boundary_id> "T:\path\to\novel.txt" --ordinal 1 --max-chars 800
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-corpus-samples demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-corpus-sample demo_project <sample_id>
```

Default `read-corpus-sample` does not print sample text.

For explicit local inspection:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-corpus-sample demo_project <sample_id> --include-text
```

Corpus samples are `test_only` and `publish_blocker`. `audit-project` must fail while they exist so they cannot be missed before GitHub publication.

## Step-By-Step Flow

Create a project:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-project demo_project --title "Demo Novel"
```

Configure mock writer:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test configure-mock-writer demo_project
```

Configure mock scorer for Draft Review / Quality Check:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test configure-provider-role demo_project scorer --provider mock --model mock-scorer
```

Plan a chapter:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test mark-chapter-planned demo_project chapter_001 --title "Opening"
```

Inspect chapter workflow state:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test chapter-status demo_project chapter_001
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-chapters demo_project
```

Check Provider adapter registry:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-provider-adapters
```

Check writer Provider status:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test provider-status demo_project writer
```

This is a local config check only. It does not send network requests.

Preflight a disabled real Provider config:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test set-project-secret demo_project deepseek_key --value-stdin
```

Then type or paste the key and press `Ctrl+Z`, then `Enter` in PowerShell.

Write the Provider role config with a secret reference:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test configure-provider-role demo_project writer --provider deepseek --model deepseek-chat --api-key-ref project_secret.deepseek_key
```

Check status:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test provider-status demo_project writer
```

Expected current result:

```text
ok: false
error_type: adapter_disabled
network_allowed: false
```

This is correct in the current phase. The config is ready for audit, but the adapter is still disabled.

Dry-run the future Provider request summary:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test provider-dry-run demo_project writer --prompt "Write a short mock opening." --system-prompt "You are a careful novelist." --temperature 0.3 --max-tokens 1000
```

Expected current result:

```text
error_type: adapter_disabled
request_summary.prompt_chars: <length only>
request_summary.system_prompt_chars: <length only>
```

The output must not contain prompt text, system prompt text, request body, or API key.

Chutes preflight example:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test set-project-secret demo_project chutes_key --value-stdin
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test configure-provider-role demo_project writer --provider chutes_openai --model "Qwen/Qwen3-32B-TEE" --api-key-ref project_secret.chutes_key --base-url https://llm.chutes.ai/v1
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test provider-dry-run demo_project writer --prompt "Tell me a 250 word story." --temperature 0.7 --max-tokens 1024
```

Current expected Chutes result:

```text
error_type: adapter_disabled
network_allowed: false
request_summary.provider: chutes_openai
request_summary.base_url_host: llm.chutes.ai
```

This is a dry-run only. It does not call Chutes.

Explicit Chutes real connection test:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test provider-real-test demo_project writer --prompt "Return exactly OK." --temperature 0 --max-tokens 16
```

This command sends a real non-streaming request. Use it only after explicit user approval.

Output returns metadata only, not generated text.

Controlled Chutes real draft generation:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test enable-real-provider demo_project writer --provider chutes_openai
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test generate-draft demo_project --chapter-id chapter_001 --title "Opening" --prompt "Write a short test draft." --temperature 0.2 --max-tokens 128
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test disable-real-provider demo_project writer
```

Use this only after explicit user approval. It sends a real non-streaming Chutes request and writes the generated text as a draft artifact only.

The `generate-draft` command returns metadata only. To inspect the generated content, use `read-draft <draft_id>`.

The real draft path still does not auto-commit, update Memory Bank, update RAG, create exports, or create DOCX.

Preferred one-command Chutes runbook:

```powershell
$env:PYTHONPATH="I:\AI-NOVEL\novel_agent_workbench\src"
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test chutes-generate-once demo_project --chapter-id chapter_001 --prompt "Write a short test draft." --secret-value-stdin --allow-network --clear-secret-after-run --temperature 0.2 --max-tokens 96
```

Paste the Chutes key through stdin when prompted by PowerShell pipeline or terminal input. Do not put real keys directly in reusable command history.

This command runs:

```text
audit precheck
secret/config setup
enable gate
generate draft
disable gate
clear secret by default
audit postcheck
```

The JSON output is metadata-only. It does not include prompt text, generated text, request body, raw response, or API key.

Generate a draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test generate-draft demo_project --chapter-id chapter_001 --title "Opening" --prompt "Write a short mock opening."
```

Copy the returned `draft_id`, then inspect safe state:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test state demo_project
```

List drafts:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-drafts demo_project
```

Read a draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-draft demo_project <draft_id>
```

Review a draft with the mock scorer:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test review-draft demo_project <draft_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-reviews demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-review demo_project <review_id>
```

Review output is metadata-only. It does not include the draft body, original prompt, raw Provider response, or API key. It also does not commit the draft, revise it, update Memory Bank/RAG, or create exports.

Record a manual review decision:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test decide-review demo_project <review_id> --decision accepted --reason-code manual_pass
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test decide-review demo_project <review_id> --decision needs_revision --reason-code tone_fix
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test decide-review demo_project <review_id> --decision blocked --reason-code manual_block
```

Only one decision may be recorded for a review in this phase. `accepted` still does not create a confirmed chapter; use `commit-draft` explicitly when the draft should enter confirmed storage.

Create a revision request after `needs_revision`:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-revision-request demo_project <review_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-revision-requests demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-revision-request demo_project <revision_request_id>
```

This only creates metadata. It does not call an LLM, edit the draft, create a confirmed chapter, or update Memory Bank/RAG/export.

Generate a mock revision draft candidate:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test configure-provider-role demo_project reviser --provider mock --model mock-reviser
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test generate-revision-draft demo_project <revision_request_id>
```

This creates a new draft candidate in `data/drafts/`. It does not overwrite the source draft and does not create a confirmed chapter. Use `read-draft <new_draft_id>` to inspect the mock candidate content.

List and compare revision candidates without returning content:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-revision-candidates demo_project <revision_request_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test compare-revision-candidate demo_project <revision_request_id> <candidate_draft_id>
```

These commands are read-only. They return ids, provider/model/usage, character/word/line counts, deltas, and link checks. They do not return draft body text, prompt text, API keys, or make a commit decision.

Explicitly commit a draft:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test commit-draft demo_project <draft_id>
```

List confirmed chapters:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-confirmed demo_project
```

Queue confirmed chapters for future formal context updates:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test enqueue-context-updates demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-context-updates demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test mark-context-update demo_project <update_id> --status acknowledged --reason-code manual_done
```

This queue is metadata-only. It does not update Memory Bank, RAG, exports, DOCX, or confirmed chapter content.

Create and inspect a context update preview:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-context-preview demo_project <update_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-context-previews demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-context-preview demo_project <preview_id>
```

Preview artifacts are plans only. They include text statistics and target placeholders, but they do not copy chapter text or update Memory Bank/RAG/export.

Create and inspect a formal context extraction plan:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-formal-context-plan demo_project <preview_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-formal-context-plans demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-formal-context-plan demo_project <plan_id>
```

Formal context plans split future manual work by category and priority. They still do not extract chapter text, call Providers, or update Memory Bank/RAG/export.

Current formal context priority:

```text
1. world_building
2. character_relationships
3. chapter_summary
4. style_memory
5. foreshadowing
```

This maps to:

```text
世界观设定 > 人物关系 > 章节摘要 > 文风记忆 > 剧情伏笔
```

World book overlap option:

```text
world_building memory_weight=1.0 normally
world_building memory_weight=0.35 when context_policy.world_book_enabled=true
```

Meaning: if the future world book is enabled, world-building facts should mainly live there. Memory Bank should keep only compact continuity cues to avoid repeated tokens.

Preview local context assembly:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test context-assembly-dry-run demo_project --max-context-tokens 4096
```

This command does not call a Provider and does not print chapter text, prompt text, Memory Bank text, or secrets. It previews candidate priority, estimated token use, selected/skipped status, and world-book overlap recommendations.

Preview an actual local context package from enabled manual Memory Bank text:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test context-package-preview demo_project --max-context-tokens 4096
```

Default output is metadata-only and does not print Memory Bank text.

To explicitly inspect selected manual Memory Bank text:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test context-package-preview demo_project --max-context-tokens 4096 --include-text
```

This preview is not a Provider prompt and does not call a model. Disabled items are skipped with `memory_item_disabled`; empty or not-ready items are skipped with `manual_text_missing`; budget overflow is skipped with `token_budget_exceeded`.

Preview the future prompt/message envelope without showing text:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test prompt-render-dry-run demo_project --prompt "Draft the next scene." --system-prompt "Use a restrained tone." --max-context-tokens 4096
```

Default output redacts the operator prompt, system prompt, and Memory Bank text. It reports message roles, character counts, token estimates, and selected context metadata only.

For explicit local inspection:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test prompt-render-dry-run demo_project --prompt "Draft the next scene." --max-context-tokens 4096 --include-prompt-text --include-context-text
```

This is still a dry-run. It does not call a Provider, write prompt logs, create drafts, or update confirmed chapters/Memory Bank/RAG/export.

Generate a context-aware draft through the local mock writer:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test generate-context-draft demo_project --chapter-id chapter_002 --title "Second Scene" --prompt "Draft the next scene." --max-context-tokens 4096
```

Current phase requirement:

```text
writer provider must be mock
```

The command creates a normal draft artifact and marks chapter workflow as `draft_ready`. It does not call real Providers, does not auto-commit, does not print operator prompt text or Memory Bank text, and does not update Memory Bank/world book/RAG/export.

Create manual formal context tasks:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test enqueue-formal-context-tasks demo_project <plan_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-formal-context-tasks demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test mark-formal-context-task demo_project <task_id> --status acknowledged --reason-code manual_done
```

Tasks are operator-facing metadata only. They do not extract text or apply Memory Bank/world book/RAG/export updates.

Preview future Memory Bank apply candidates:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-memory-apply-preview demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-memory-apply-previews demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-memory-apply-preview demo_project <preview_id>
```

Memory apply previews do not write `memory_bank.json`. They show candidate category metadata, priority, weight, and duplicate-risk hints only.

Explicitly commit placeholder Memory Bank entries:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test commit-memory-apply-preview demo_project <preview_id>
```

This creates a `pre_memory_apply` checkpoint and writes placeholder entries with empty `text` and `manual_text_required` status. It still does not extract chapter text or call a Provider.

List and fill Memory Bank items manually:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-memory-items demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test set-memory-text demo_project <memory_id> --text "Manual continuity note goes here."
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-memory-item demo_project <memory_id>
```

Default list/read output is metadata-only. It shows `text_chars`, not the note itself.

To explicitly inspect the manual Memory Bank text:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-memory-item demo_project <memory_id> --include-text
```

Manual Memory Bank text writes create a `pre_memory_text_update` checkpoint, reject empty text, reject text longer than 1200 characters, and reject obvious secret-like values. They do not call Providers, update world book, update RAG/export, mutate drafts/confirmed chapters, or auto-assemble Provider prompts.

Disable or re-enable one Memory Bank item:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test disable-memory-item demo_project <memory_id> --reason-code duplicate_world_book
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test enable-memory-item demo_project <memory_id> --reason-code manual_restore
```

These commands create a `pre_memory_lifecycle_update` checkpoint and return metadata only. Disabled items stay in `memory_bank.json`; they are not deleted and their text is not printed. `context-assembly-dry-run` skips disabled Memory Bank items with `skip_reason=memory_item_disabled`.

Read a confirmed chapter:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-confirmed demo_project chapter_001
```

Audit a project:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test audit-project demo_project
```

Expected clean audit:

```text
ok: true
findings: []
```

For context-aware drafts, audit validates `context_generation` metadata and drafts index consistency. It does not reject normal draft body text, because draft artifacts are allowed to contain generated content for human review.

Run a repository prepublish check before any GitHub publication:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root I:\AI-NOVEL\novel_agent_workbench\workspace_projects prepublish-check --repo-root I:\AI-NOVEL\novel_agent_workbench
```

This is read-only. It checks required `.gitignore` patterns, publishable source files, runtime project audit findings, and test-only corpus samples. Real corpus samples are blockers until removed or retired from runtime state. Disabled real Provider adapters or missing local Provider secrets may appear as warnings when they do not leak secrets, prompts, or content.

Create a self-style baseline from confirmed chapters:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-self-style-baseline demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-self-style-baselines demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-self-style-baseline demo_project <baseline_id>
```

This uses only the project's own confirmed chapters. It does not read external reference novels, call Providers, or store chapter text. The output is numeric/statistical metadata for future draft style checks.

Check one draft against the self-style baseline:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test check-draft-style demo_project <draft_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-draft-style-checks demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-draft-style-check demo_project <check_id>
```

This is local only. It compares draft statistics against the latest self-style baseline unless `--baseline-id` is provided. Use `--scene-mode exposition`, `--scene-mode battle`, `--scene-mode climax`, `--scene-mode daily`, `--scene-mode romance`, or `--scene-mode transition` when a chapter intentionally differs from the average. The result is a calibrated hint, not a strict grade. It does not call Providers, return draft text, create revision requests, auto-revise, auto-commit, or update Memory Bank/RAG/export.

Optional style-check controls:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test check-draft-style demo_project <draft_id> --hide-hints
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test check-draft-style demo_project <draft_id> --disable-calibration
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test check-draft-style demo_project <draft_id> --disable-style-check
```

Future UI placement: the per-draft style check belongs in the draft review side panel, with defaults under Project Settings > Writing Quality. It should not be a blocking pop-up window.

Create manual style suggestions from a style check:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-style-suggestion demo_project <check_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-style-suggestions demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-style-suggestion demo_project <suggestion_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test decide-style-suggestion demo_project <suggestion_id> --decision ignored --reason-code scene_intentional
```

This converts warning/hint metadata into manual advice, then lets the operator record a decision: `accepted`, `ignored`, or `needs_manual_rewrite`. Decisions update only metadata. They do not edit the draft, create a revision request, call Providers, auto-commit, or update Memory Bank/RAG/export. Suggestions and decisions are generic metric-level metadata and must not contain draft text, prompt text, generated content, or plaintext secrets.

Create a human rewrite task from a `needs_manual_rewrite` style suggestion:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test create-manual-rewrite-task demo_project <suggestion_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test list-manual-rewrite-tasks demo_project
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test read-manual-rewrite-task demo_project <task_id>
py -3.13 -m novel_agent_workbench.cli --projects-root $env:TEMP\naw_manual_test mark-manual-rewrite-task demo_project <task_id> --status in_progress --reason-code started
```

Manual rewrite tasks are workspace metadata only. They do not edit the draft, create a new draft, create a revision request, call Providers, auto-commit, or update Memory Bank/RAG/export.

## Safety And Cleanup Policy

Do not hard delete real project files during early MVP.

If a real file must be retired later, rename it with `.trash`.

Unit tests and manual experiments under system temp directories are allowed to use temporary cleanup. Do not treat that exception as permission to delete real `workspace_projects` data.

## Common Errors

Writer is not configured:

```text
ProviderError: Model role has no provider configured.
```

Fix:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> configure-mock-writer <project_id>
```

Disabled real Provider:

```text
adapter_disabled
```

Meaning: `openai_compatible` or `deepseek` is only reserved in this phase. It is not allowed to connect to the network yet.

Missing Provider secret reference:

```text
missing_secret_ref
```

Meaning: a future real Provider role must use `api_key_ref` in the form `project_secret.<name>`.

Missing or empty local secret:

```text
missing_secret
empty_secret
```

Meaning: the referenced key is absent or empty in `data\secrets.local.json`. Do not put the key into `config.json`.

Duplicate commit:

```text
DraftGenerationError: Draft is not committable
```

Meaning: the draft was already committed, or another confirmed chapter already owns the same `chapter_id`.

Duplicate review:

```text
DraftReviewError: Draft already has a review
```

Meaning: the draft has already produced one review artifact. This phase keeps review creation idempotent by rejecting duplicate review writes.

Duplicate decision:

```text
DraftReviewError: Review already has a manual decision
```

Meaning: a review decision is intentionally one-shot in this phase. Create a later revision/review cycle instead of silently overwriting the decision.

Revision request before `needs_revision`:

```text
RevisionRequestError: Revision request requires a needs_revision review decision.
```

Meaning: only drafts explicitly marked `needs_revision` can receive a revision request artifact.

Duplicate revision request:

```text
RevisionRequestError: Review already has a revision request
```

Meaning: this phase stores one revision request per review.

Revision draft before request is draftable:

```text
RevisionRequestError: Revision request is not draftable
```

Meaning: the request is missing, already consumed, or no longer in `requested` state.

Missing reviser role:

```text
ProviderError: Model role has no provider configured.
```

Fix:

```powershell
py -3.13 -m novel_agent_workbench.cli --projects-root <root> configure-provider-role <project_id> reviser --provider mock --model mock-reviser
```

Non-mock reviser role:

```text
RevisionRequestError: Revision draft generation is mock-only in this phase.
```

Meaning: revision draft candidates are intentionally limited to the local `mock` Provider. Configure `reviser --provider mock --model mock-reviser` before using `generate-revision-draft`.

Revision audit inconsistency:

```text
revision_request_generated_draft_missing
revision_generated_draft_request_mismatch
```

Meaning: `audit-project` found a broken link between a revision request and its generated draft candidate. Do not build UI automation on that project state until the artifact/index mismatch is investigated.

Unsafe project id:

```text
InvalidProjectIdError
```

Use only letters, numbers, `_`, and `-`. Do not use slashes, colons, spaces, `.` or `..`.

Unsafe chapter id:

```text
DraftGenerationError: Unsafe chapter_id
```

Use ASCII letters, numbers, `_`, and `-` for `chapter_id`. Put Chinese or long human-readable names in `--title` / `--chapter-title`.

Manual Memory Bank text is too long or secret-like:

```text
MemoryBankError
```

Meaning: keep each manual Memory Bank item compact, and never paste API keys or provider credentials into Memory Bank text.
