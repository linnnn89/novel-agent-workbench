from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .application_service import WorkbenchApplicationService
from .storage import DEFAULT_PROJECTS_DIRNAME


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_command(args)
    except Exception as exc:
        write_json({"ok": False, "error_type": exc.__class__.__name__, "message": str(exc)}, stderr=True)
        return 1
    write_json({"ok": True, "result": result})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="novel-agent-workbench", description="Backend-only workbench CLI.")
    parser.add_argument(
        "--projects-root",
        default=DEFAULT_PROJECTS_DIRNAME,
        help="Project data root. Defaults to ./workspace_projects relative to the current directory.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-project")
    create.add_argument("project_id")
    create.add_argument("--title", default="")

    subparsers.add_parser("list-projects")

    prepublish = subparsers.add_parser("prepublish-check")
    prepublish.add_argument("--repo-root", default="")

    project_health = subparsers.add_parser("project-health")
    project_health.add_argument("project_id")
    project_health.add_argument("--repo-root", default="")

    profile_corpus = subparsers.add_parser("profile-corpus")
    profile_corpus.add_argument("path")
    profile_corpus.add_argument("--max-name-candidates", type=int, default=20)

    save_corpus_profile = subparsers.add_parser("save-corpus-profile")
    save_corpus_profile.add_argument("project_id")
    save_corpus_profile.add_argument("path")
    save_corpus_profile.add_argument("--max-name-candidates", type=int, default=20)

    list_corpus_profiles = subparsers.add_parser("list-corpus-profiles")
    list_corpus_profiles.add_argument("project_id")

    read_corpus_profile = subparsers.add_parser("read-corpus-profile")
    read_corpus_profile.add_argument("project_id")
    read_corpus_profile.add_argument("profile_id")

    save_corpus_boundaries = subparsers.add_parser("save-corpus-boundaries")
    save_corpus_boundaries.add_argument("project_id")
    save_corpus_boundaries.add_argument("path")

    list_corpus_boundaries = subparsers.add_parser("list-corpus-boundaries")
    list_corpus_boundaries.add_argument("project_id")

    read_corpus_boundaries = subparsers.add_parser("read-corpus-boundaries")
    read_corpus_boundaries.add_argument("project_id")
    read_corpus_boundaries.add_argument("boundary_id")

    create_corpus_sample = subparsers.add_parser("create-corpus-sample")
    create_corpus_sample.add_argument("project_id")
    create_corpus_sample.add_argument("boundary_id")
    create_corpus_sample.add_argument("source_path")
    create_corpus_sample.add_argument("--ordinal", type=int, required=True)
    create_corpus_sample.add_argument("--max-chars", type=int, default=800)

    list_corpus_samples = subparsers.add_parser("list-corpus-samples")
    list_corpus_samples.add_argument("project_id")

    read_corpus_sample = subparsers.add_parser("read-corpus-sample")
    read_corpus_sample.add_argument("project_id")
    read_corpus_sample.add_argument("sample_id")
    read_corpus_sample.add_argument("--include-text", action="store_true")

    create_style_baseline = subparsers.add_parser("create-self-style-baseline")
    create_style_baseline.add_argument("project_id")

    list_style_baselines = subparsers.add_parser("list-self-style-baselines")
    list_style_baselines.add_argument("project_id")

    read_style_baseline = subparsers.add_parser("read-self-style-baseline")
    read_style_baseline.add_argument("project_id")
    read_style_baseline.add_argument("baseline_id")

    check_draft_style = subparsers.add_parser("check-draft-style")
    check_draft_style.add_argument("project_id")
    check_draft_style.add_argument("draft_id")
    check_draft_style.add_argument("--baseline-id", default="")
    check_draft_style.add_argument(
        "--scene-mode",
        default="general",
        choices=["general", "daily", "romance", "battle", "climax", "exposition", "transition", "custom"],
    )
    check_draft_style.add_argument("--disable-style-check", action="store_true")
    calibration_group = check_draft_style.add_mutually_exclusive_group()
    calibration_group.add_argument("--enable-calibration", dest="calibration_enabled", action="store_true", default=None)
    calibration_group.add_argument("--disable-calibration", dest="calibration_enabled", action="store_false")
    hints_group = check_draft_style.add_mutually_exclusive_group()
    hints_group.add_argument("--show-hints", dest="show_hints", action="store_true", default=None)
    hints_group.add_argument("--hide-hints", dest="show_hints", action="store_false")

    list_draft_style_checks = subparsers.add_parser("list-draft-style-checks")
    list_draft_style_checks.add_argument("project_id")

    read_draft_style_check = subparsers.add_parser("read-draft-style-check")
    read_draft_style_check.add_argument("project_id")
    read_draft_style_check.add_argument("check_id")

    create_style_suggestion = subparsers.add_parser("create-style-suggestion")
    create_style_suggestion.add_argument("project_id")
    create_style_suggestion.add_argument("check_id")

    list_style_suggestions = subparsers.add_parser("list-style-suggestions")
    list_style_suggestions.add_argument("project_id")

    read_style_suggestion = subparsers.add_parser("read-style-suggestion")
    read_style_suggestion.add_argument("project_id")
    read_style_suggestion.add_argument("suggestion_id")

    decide_style_suggestion = subparsers.add_parser("decide-style-suggestion")
    decide_style_suggestion.add_argument("project_id")
    decide_style_suggestion.add_argument("suggestion_id")
    decide_style_suggestion.add_argument(
        "--decision",
        required=True,
        choices=["accepted", "ignored", "needs_manual_rewrite"],
    )
    decide_style_suggestion.add_argument("--reason-code", default="")

    create_manual_rewrite_task = subparsers.add_parser("create-manual-rewrite-task")
    create_manual_rewrite_task.add_argument("project_id")
    create_manual_rewrite_task.add_argument("suggestion_id")

    list_manual_rewrite_tasks = subparsers.add_parser("list-manual-rewrite-tasks")
    list_manual_rewrite_tasks.add_argument("project_id")
    list_manual_rewrite_tasks.add_argument("--status", default="")

    read_manual_rewrite_task = subparsers.add_parser("read-manual-rewrite-task")
    read_manual_rewrite_task.add_argument("project_id")
    read_manual_rewrite_task.add_argument("task_id")

    mark_manual_rewrite_task = subparsers.add_parser("mark-manual-rewrite-task")
    mark_manual_rewrite_task.add_argument("project_id")
    mark_manual_rewrite_task.add_argument("task_id")
    mark_manual_rewrite_task.add_argument("--status", required=True, choices=["pending", "in_progress", "done", "skipped"])
    mark_manual_rewrite_task.add_argument("--reason-code", default="")

    submit_manual_rewrite_draft = subparsers.add_parser("submit-manual-rewrite-draft")
    submit_manual_rewrite_draft.add_argument("project_id")
    submit_manual_rewrite_draft.add_argument("task_id")
    text_group = submit_manual_rewrite_draft.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text")
    text_group.add_argument("--text-stdin", action="store_true")

    compare_manual_rewrite = subparsers.add_parser("compare-manual-rewrite-candidate")
    compare_manual_rewrite.add_argument("project_id")
    compare_manual_rewrite.add_argument("task_id")

    list_manual_rewrite_comparisons = subparsers.add_parser("list-manual-rewrite-comparisons")
    list_manual_rewrite_comparisons.add_argument("project_id")
    list_manual_rewrite_comparisons.add_argument("--status", default="")

    read_manual_rewrite_comparison = subparsers.add_parser("read-manual-rewrite-comparison")
    read_manual_rewrite_comparison.add_argument("project_id")
    read_manual_rewrite_comparison.add_argument("comparison_id")

    decide_manual_rewrite_comparison = subparsers.add_parser("decide-manual-rewrite-comparison")
    decide_manual_rewrite_comparison.add_argument("project_id")
    decide_manual_rewrite_comparison.add_argument("comparison_id")
    decide_manual_rewrite_comparison.add_argument(
        "--decision",
        required=True,
        choices=["selected_for_review", "rejected", "needs_more_manual_work"],
    )
    decide_manual_rewrite_comparison.add_argument("--reason-code", default="")

    create_review_handoff = subparsers.add_parser("create-review-handoff-from-manual-comparison")
    create_review_handoff.add_argument("project_id")
    create_review_handoff.add_argument("comparison_id")

    list_review_handoffs = subparsers.add_parser("list-review-handoffs")
    list_review_handoffs.add_argument("project_id")
    list_review_handoffs.add_argument("--status", default="")

    read_review_handoff = subparsers.add_parser("read-review-handoff")
    read_review_handoff.add_argument("project_id")
    read_review_handoff.add_argument("handoff_id")

    state = subparsers.add_parser("state")
    state.add_argument("project_id")

    create_planning_item = subparsers.add_parser("create-planning-item")
    create_planning_item.add_argument("project_id")
    create_planning_item.add_argument("planning_id")
    create_planning_item.add_argument("--title", default="")
    create_planning_item.add_argument(
        "--item-type",
        default="outline",
        choices=["outline", "beat_sheet", "chapter_plan", "character_plan", "world_plan", "constraint", "other"],
    )
    planning_text_group = create_planning_item.add_mutually_exclusive_group(required=True)
    planning_text_group.add_argument("--text")
    planning_text_group.add_argument("--text-stdin", action="store_true")
    create_planning_item.add_argument("--active", action="store_true")
    create_planning_item.add_argument("--disabled", action="store_true")
    create_planning_item.add_argument("--priority", type=int, default=10)
    create_planning_item.add_argument("--adherence-level", default="balanced", choices=["soft", "balanced", "strict"])
    create_planning_item.add_argument("--send-mode", default="reference_text", choices=["reference_text", "metadata_only"])
    create_planning_item.add_argument("--chapter-range", default="")

    list_planning_items = subparsers.add_parser("list-planning-items")
    list_planning_items.add_argument("project_id")

    read_planning_item = subparsers.add_parser("read-planning-item")
    read_planning_item.add_argument("project_id")
    read_planning_item.add_argument("planning_id")
    read_planning_item.add_argument("--include-text", action="store_true")

    activate_planning_item = subparsers.add_parser("activate-planning-item")
    activate_planning_item.add_argument("project_id")
    activate_planning_item.add_argument("planning_id")

    deactivate_planning_item = subparsers.add_parser("deactivate-planning-item")
    deactivate_planning_item.add_argument("project_id")
    deactivate_planning_item.add_argument("planning_id")

    enable_planning_item = subparsers.add_parser("enable-planning-item")
    enable_planning_item.add_argument("project_id")
    enable_planning_item.add_argument("planning_id")

    disable_planning_item = subparsers.add_parser("disable-planning-item")
    disable_planning_item.add_argument("project_id")
    disable_planning_item.add_argument("planning_id")

    mark_chapter = subparsers.add_parser("mark-chapter-planned")
    mark_chapter.add_argument("project_id")
    mark_chapter.add_argument("chapter_id")
    mark_chapter.add_argument("--title", default="")

    chapter_status = subparsers.add_parser("chapter-status")
    chapter_status.add_argument("project_id")
    chapter_status.add_argument("chapter_id")

    list_chapters = subparsers.add_parser("list-chapters")
    list_chapters.add_argument("project_id")

    configure = subparsers.add_parser("configure-mock-writer")
    configure.add_argument("project_id")
    configure.add_argument("--model", default="mock-writer")

    configure_provider = subparsers.add_parser("configure-provider-role")
    configure_provider.add_argument("project_id")
    configure_provider.add_argument("role", choices=["writer", "scorer", "reviser"])
    configure_provider.add_argument("--provider", required=True)
    configure_provider.add_argument("--model", required=True)
    configure_provider.add_argument("--api-key-ref", default="")
    configure_provider.add_argument("--base-url", default="")

    set_secret = subparsers.add_parser("set-project-secret")
    set_secret.add_argument("project_id")
    set_secret.add_argument("name")
    value_group = set_secret.add_mutually_exclusive_group(required=True)
    value_group.add_argument("--value")
    value_group.add_argument("--value-stdin", action="store_true")

    generate = subparsers.add_parser("generate-draft")
    generate.add_argument("project_id")
    generate.add_argument("--chapter-id", required=True)
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--title", default="")
    generate.add_argument("--system-prompt", default="")
    generate.add_argument("--max-tokens", type=int, default=None)
    generate.add_argument("--temperature", type=float, default=None)

    generate_context = subparsers.add_parser("generate-context-draft")
    generate_context.add_argument("project_id")
    generate_context.add_argument("--chapter-id", required=True)
    generate_context.add_argument("--prompt", required=True)
    generate_context.add_argument("--title", default="")
    generate_context.add_argument("--system-prompt", default="")
    generate_context.add_argument("--max-context-tokens", type=int, default=None)
    generate_context.add_argument("--final-assembly-gate-id", default="")
    generate_context.add_argument("--max-tokens", type=int, default=None)
    generate_context.add_argument("--temperature", type=float, default=None)

    list_drafts = subparsers.add_parser("list-drafts")
    list_drafts.add_argument("project_id")

    read_draft = subparsers.add_parser("read-draft")
    read_draft.add_argument("project_id")
    read_draft.add_argument("draft_id")

    commit = subparsers.add_parser("commit-draft")
    commit.add_argument("project_id")
    commit.add_argument("draft_id")

    review = subparsers.add_parser("review-draft")
    review.add_argument("project_id")
    review.add_argument("draft_id")

    list_reviews = subparsers.add_parser("list-reviews")
    list_reviews.add_argument("project_id")

    read_review = subparsers.add_parser("read-review")
    read_review.add_argument("project_id")
    read_review.add_argument("review_id")

    decide_review = subparsers.add_parser("decide-review")
    decide_review.add_argument("project_id")
    decide_review.add_argument("review_id")
    decide_review.add_argument("--decision", required=True, choices=["accepted", "needs_revision", "blocked"])
    decide_review.add_argument("--reason-code", default="")

    create_revision_request = subparsers.add_parser("create-revision-request")
    create_revision_request.add_argument("project_id")
    create_revision_request.add_argument("review_id")

    list_revision_requests = subparsers.add_parser("list-revision-requests")
    list_revision_requests.add_argument("project_id")

    read_revision_request = subparsers.add_parser("read-revision-request")
    read_revision_request.add_argument("project_id")
    read_revision_request.add_argument("revision_request_id")

    generate_revision_draft = subparsers.add_parser("generate-revision-draft")
    generate_revision_draft.add_argument("project_id")
    generate_revision_draft.add_argument("revision_request_id")

    list_revision_candidates = subparsers.add_parser("list-revision-candidates")
    list_revision_candidates.add_argument("project_id")
    list_revision_candidates.add_argument("revision_request_id")

    compare_revision_candidate = subparsers.add_parser("compare-revision-candidate")
    compare_revision_candidate.add_argument("project_id")
    compare_revision_candidate.add_argument("revision_request_id")
    compare_revision_candidate.add_argument("candidate_draft_id")

    enqueue_context = subparsers.add_parser("enqueue-context-updates")
    enqueue_context.add_argument("project_id")

    list_context = subparsers.add_parser("list-context-updates")
    list_context.add_argument("project_id")
    list_context.add_argument("--status", default="")

    mark_context = subparsers.add_parser("mark-context-update")
    mark_context.add_argument("project_id")
    mark_context.add_argument("update_id")
    mark_context.add_argument("--status", required=True, choices=["pending", "acknowledged", "skipped"])
    mark_context.add_argument("--reason-code", default="")

    create_context_preview = subparsers.add_parser("create-context-preview")
    create_context_preview.add_argument("project_id")
    create_context_preview.add_argument("update_id")

    list_context_previews = subparsers.add_parser("list-context-previews")
    list_context_previews.add_argument("project_id")

    read_context_preview = subparsers.add_parser("read-context-preview")
    read_context_preview.add_argument("project_id")
    read_context_preview.add_argument("preview_id")

    create_formal_context_plan = subparsers.add_parser("create-formal-context-plan")
    create_formal_context_plan.add_argument("project_id")
    create_formal_context_plan.add_argument("preview_id")

    list_formal_context_plans = subparsers.add_parser("list-formal-context-plans")
    list_formal_context_plans.add_argument("project_id")

    read_formal_context_plan = subparsers.add_parser("read-formal-context-plan")
    read_formal_context_plan.add_argument("project_id")
    read_formal_context_plan.add_argument("plan_id")

    context_assembly = subparsers.add_parser("context-assembly-dry-run")
    context_assembly.add_argument("project_id")
    context_assembly.add_argument("--max-context-tokens", type=int, default=None)

    context_package = subparsers.add_parser("context-package-preview")
    context_package.add_argument("project_id")
    context_package.add_argument("--max-context-tokens", type=int, default=None)
    context_package.add_argument("--include-text", action="store_true")

    prompt_render = subparsers.add_parser("prompt-render-dry-run")
    prompt_render.add_argument("project_id")
    prompt_render.add_argument("--prompt", required=True)
    prompt_render.add_argument("--system-prompt", default="")
    prompt_render.add_argument("--max-context-tokens", type=int, default=None)
    prompt_render.add_argument("--include-prompt-text", action="store_true")
    prompt_render.add_argument("--include-context-text", action="store_true")

    create_final_gate = subparsers.add_parser("create-final-assembly-gate")
    create_final_gate.add_argument("project_id")
    create_final_gate.add_argument("--chapter-id", required=True)
    create_final_gate.add_argument("--prompt", required=True)
    create_final_gate.add_argument("--system-prompt", default="")
    create_final_gate.add_argument("--max-context-tokens", type=int, default=None)

    approve_final_gate = subparsers.add_parser("approve-final-assembly-gate")
    approve_final_gate.add_argument("project_id")
    approve_final_gate.add_argument("gate_id")
    approve_final_gate.add_argument("--reason-code", default="")

    list_final_gates = subparsers.add_parser("list-final-assembly-gates")
    list_final_gates.add_argument("project_id")
    list_final_gates.add_argument("--status", default="")

    read_final_gate = subparsers.add_parser("read-final-assembly-gate")
    read_final_gate.add_argument("project_id")
    read_final_gate.add_argument("gate_id")

    create_final_runbook = subparsers.add_parser("create-final-provider-runbook")
    create_final_runbook.add_argument("project_id")
    create_final_runbook.add_argument("gate_id")

    list_final_runbooks = subparsers.add_parser("list-final-provider-runbooks")
    list_final_runbooks.add_argument("project_id")
    list_final_runbooks.add_argument("--status", default="")

    read_final_runbook = subparsers.add_parser("read-final-provider-runbook")
    read_final_runbook.add_argument("project_id")
    read_final_runbook.add_argument("runbook_id")

    authorize_final_runbook = subparsers.add_parser("authorize-final-provider-runbook")
    authorize_final_runbook.add_argument("project_id")
    authorize_final_runbook.add_argument("runbook_id")
    authorize_final_runbook.add_argument("--reason-code", default="")

    list_final_authorizations = subparsers.add_parser("list-final-provider-authorizations")
    list_final_authorizations.add_argument("project_id")
    list_final_authorizations.add_argument("--status", default="")

    read_final_authorization = subparsers.add_parser("read-final-provider-authorization")
    read_final_authorization.add_argument("project_id")
    read_final_authorization.add_argument("authorization_id")

    create_final_preflight = subparsers.add_parser("create-final-provider-execution-preflight")
    create_final_preflight.add_argument("project_id")
    create_final_preflight.add_argument("authorization_id")

    list_final_preflights = subparsers.add_parser("list-final-provider-execution-preflights")
    list_final_preflights.add_argument("project_id")
    list_final_preflights.add_argument("--status", default="")

    read_final_preflight = subparsers.add_parser("read-final-provider-execution-preflight")
    read_final_preflight.add_argument("project_id")
    read_final_preflight.add_argument("preflight_id")

    attempt_final_execution = subparsers.add_parser("attempt-final-provider-execution")
    attempt_final_execution.add_argument("project_id")
    attempt_final_execution.add_argument("preflight_id")

    list_final_attempts = subparsers.add_parser("list-final-provider-execution-attempts")
    list_final_attempts.add_argument("project_id")
    list_final_attempts.add_argument("--status", default="")

    read_final_attempt = subparsers.add_parser("read-final-provider-execution-attempt")
    read_final_attempt.add_argument("project_id")
    read_final_attempt.add_argument("attempt_id")

    create_final_readiness = subparsers.add_parser("create-final-provider-real-execution-readiness")
    create_final_readiness.add_argument("project_id")
    create_final_readiness.add_argument("attempt_id")

    list_final_readiness = subparsers.add_parser("list-final-provider-real-execution-readiness")
    list_final_readiness.add_argument("project_id")
    list_final_readiness.add_argument("--status", default="")

    read_final_readiness = subparsers.add_parser("read-final-provider-real-execution-readiness")
    read_final_readiness.add_argument("project_id")
    read_final_readiness.add_argument("readiness_id")

    execute_final_real = subparsers.add_parser("execute-final-provider-real")
    execute_final_real.add_argument("project_id")
    execute_final_real.add_argument("readiness_id")
    execute_prompt_group = execute_final_real.add_mutually_exclusive_group(required=True)
    execute_prompt_group.add_argument("--prompt")
    execute_prompt_group.add_argument("--prompt-stdin", action="store_true")
    execute_final_real.add_argument("--system-prompt", default="")
    execute_final_real.add_argument("--title", default="")
    execute_final_real.add_argument("--max-context-tokens", type=int, default=None)
    execute_final_real.add_argument("--temperature", type=float, default=None)
    execute_final_real.add_argument("--max-tokens", type=int, default=None)
    execute_final_real.add_argument("--reason-code", default="")

    list_final_executions = subparsers.add_parser("list-final-provider-real-executions")
    list_final_executions.add_argument("project_id")
    list_final_executions.add_argument("--status", default="")

    read_final_execution = subparsers.add_parser("read-final-provider-real-execution")
    read_final_execution.add_argument("project_id")
    read_final_execution.add_argument("execution_id")

    postcheck_final_execution = subparsers.add_parser("postcheck-final-provider-real-execution")
    postcheck_final_execution.add_argument("project_id")
    postcheck_final_execution.add_argument("execution_id")

    enqueue_formal_context_tasks = subparsers.add_parser("enqueue-formal-context-tasks")
    enqueue_formal_context_tasks.add_argument("project_id")
    enqueue_formal_context_tasks.add_argument("plan_id")

    list_formal_context_tasks = subparsers.add_parser("list-formal-context-tasks")
    list_formal_context_tasks.add_argument("project_id")
    list_formal_context_tasks.add_argument("--status", default="")

    mark_formal_context_task = subparsers.add_parser("mark-formal-context-task")
    mark_formal_context_task.add_argument("project_id")
    mark_formal_context_task.add_argument("task_id")
    mark_formal_context_task.add_argument("--status", required=True, choices=["pending", "acknowledged", "skipped"])
    mark_formal_context_task.add_argument("--reason-code", default="")

    create_memory_apply_preview = subparsers.add_parser("create-memory-apply-preview")
    create_memory_apply_preview.add_argument("project_id")
    create_memory_apply_preview.add_argument("--status", default="pending")

    list_memory_apply_previews = subparsers.add_parser("list-memory-apply-previews")
    list_memory_apply_previews.add_argument("project_id")

    read_memory_apply_preview = subparsers.add_parser("read-memory-apply-preview")
    read_memory_apply_preview.add_argument("project_id")
    read_memory_apply_preview.add_argument("preview_id")

    commit_memory_apply_preview = subparsers.add_parser("commit-memory-apply-preview")
    commit_memory_apply_preview.add_argument("project_id")
    commit_memory_apply_preview.add_argument("preview_id")

    list_memory_items = subparsers.add_parser("list-memory-items")
    list_memory_items.add_argument("project_id")

    read_memory_item = subparsers.add_parser("read-memory-item")
    read_memory_item.add_argument("project_id")
    read_memory_item.add_argument("memory_id")
    read_memory_item.add_argument("--include-text", action="store_true")

    set_memory_text = subparsers.add_parser("set-memory-text")
    set_memory_text.add_argument("project_id")
    set_memory_text.add_argument("memory_id")
    text_group = set_memory_text.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text")
    text_group.add_argument("--text-stdin", action="store_true")

    disable_memory_item = subparsers.add_parser("disable-memory-item")
    disable_memory_item.add_argument("project_id")
    disable_memory_item.add_argument("memory_id")
    disable_memory_item.add_argument("--reason-code", default="")

    enable_memory_item = subparsers.add_parser("enable-memory-item")
    enable_memory_item.add_argument("project_id")
    enable_memory_item.add_argument("memory_id")
    enable_memory_item.add_argument("--reason-code", default="")

    list_confirmed = subparsers.add_parser("list-confirmed")
    list_confirmed.add_argument("project_id")

    read_confirmed = subparsers.add_parser("read-confirmed")
    read_confirmed.add_argument("project_id")
    read_confirmed.add_argument("chapter_id")

    audit = subparsers.add_parser("audit-project")
    audit.add_argument("project_id")

    provider_status = subparsers.add_parser("provider-status")
    provider_status.add_argument("project_id")
    provider_status.add_argument("role", choices=["writer", "scorer", "reviser"])

    provider_dry_run = subparsers.add_parser("provider-dry-run")
    provider_dry_run.add_argument("project_id")
    provider_dry_run.add_argument("role", choices=["writer", "scorer", "reviser"])
    provider_dry_run.add_argument("--prompt", required=True)
    provider_dry_run.add_argument("--system-prompt", default="")
    provider_dry_run.add_argument("--max-tokens", type=int, default=None)
    provider_dry_run.add_argument("--temperature", type=float, default=None)

    provider_real_test = subparsers.add_parser("provider-real-test")
    provider_real_test.add_argument("project_id")
    provider_real_test.add_argument("role", choices=["writer", "scorer", "reviser"])
    provider_real_test.add_argument("--prompt", default="Return exactly OK.")
    provider_real_test.add_argument("--system-prompt", default="")
    provider_real_test.add_argument("--max-tokens", type=int, default=16)
    provider_real_test.add_argument("--temperature", type=float, default=0)

    provider_smoke_test = subparsers.add_parser("run-provider-smoke-test")
    provider_smoke_test.add_argument("project_id")
    provider_smoke_test.add_argument("role", choices=["writer", "scorer", "reviser"])
    provider_smoke_test.add_argument("--prompt", default="Return exactly OK.")
    provider_smoke_test.add_argument("--system-prompt", default="")
    provider_smoke_test.add_argument("--max-tokens", type=int, default=16)
    provider_smoke_test.add_argument("--temperature", type=float, default=0)
    provider_smoke_test.add_argument("--reason-code", default="")

    list_provider_smoke_tests = subparsers.add_parser("list-provider-smoke-tests")
    list_provider_smoke_tests.add_argument("project_id")
    list_provider_smoke_tests.add_argument("--status", default="")

    read_provider_smoke_test = subparsers.add_parser("read-provider-smoke-test")
    read_provider_smoke_test.add_argument("project_id")
    read_provider_smoke_test.add_argument("smoke_test_id")

    chutes_once = subparsers.add_parser("chutes-generate-once")
    chutes_once.add_argument("project_id")
    chutes_once.add_argument("--chapter-id", required=True)
    chutes_once.add_argument("--prompt", required=True)
    chutes_once.add_argument("--title", default="")
    chutes_once.add_argument("--system-prompt", default="")
    chutes_once.add_argument("--model", default="Qwen/Qwen3-32B-TEE")
    chutes_once.add_argument("--base-url", default="https://llm.chutes.ai/v1")
    chutes_once.add_argument("--secret-name", default="chutes_key")
    secret_value_group = chutes_once.add_mutually_exclusive_group()
    secret_value_group.add_argument("--secret-value")
    secret_value_group.add_argument("--secret-value-stdin", action="store_true")
    chutes_once.add_argument("--max-tokens", type=int, default=96)
    chutes_once.add_argument("--temperature", type=float, default=0.2)
    clear_group = chutes_once.add_mutually_exclusive_group()
    clear_group.add_argument("--clear-secret-after-run", dest="clear_secret_after_run", action="store_true", default=True)
    clear_group.add_argument("--keep-secret-after-run", dest="clear_secret_after_run", action="store_false")

    subparsers.add_parser("list-provider-adapters")

    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("project_id")
    smoke.add_argument("--title", default="")
    smoke.add_argument("--chapter-id", default="chapter_001")
    smoke.add_argument("--chapter-title", default="")
    smoke.add_argument("--prompt", required=True)
    smoke.add_argument("--commit", action="store_true")

    return parser


def run_command(args: argparse.Namespace) -> Any:
    app = WorkbenchApplicationService.open(Path(args.projects_root))
    command = args.command
    if command == "create-project":
        return app.create_project(args.project_id, title=args.title)
    if command == "list-projects":
        return app.list_projects()
    if command == "prepublish-check":
        return app.prepublish_check(repo_root=args.repo_root or None)
    if command == "project-health":
        return app.project_health(args.project_id, repo_root=args.repo_root or None)
    if command == "profile-corpus":
        return app.profile_corpus(args.path, max_name_candidates=args.max_name_candidates)
    if command == "save-corpus-profile":
        return app.save_corpus_profile(args.project_id, args.path, max_name_candidates=args.max_name_candidates)
    if command == "list-corpus-profiles":
        return app.list_corpus_profiles(args.project_id)
    if command == "read-corpus-profile":
        return app.read_corpus_profile(args.project_id, args.profile_id)
    if command == "save-corpus-boundaries":
        return app.save_corpus_boundaries(args.project_id, args.path)
    if command == "list-corpus-boundaries":
        return app.list_corpus_boundaries(args.project_id)
    if command == "read-corpus-boundaries":
        return app.read_corpus_boundaries(args.project_id, args.boundary_id)
    if command == "create-corpus-sample":
        return app.create_corpus_sample(
            args.project_id,
            args.boundary_id,
            args.source_path,
            ordinal=args.ordinal,
            max_chars=args.max_chars,
        )
    if command == "list-corpus-samples":
        return app.list_corpus_samples(args.project_id)
    if command == "read-corpus-sample":
        return app.read_corpus_sample(args.project_id, args.sample_id, include_text=args.include_text)
    if command == "create-self-style-baseline":
        return app.create_self_style_baseline(args.project_id)
    if command == "list-self-style-baselines":
        return app.list_self_style_baselines(args.project_id)
    if command == "read-self-style-baseline":
        return app.read_self_style_baseline(args.project_id, args.baseline_id)
    if command == "check-draft-style":
        return app.check_draft_style(
            args.project_id,
            args.draft_id,
            baseline_id=args.baseline_id,
            scene_mode=args.scene_mode,
            enabled=False if args.disable_style_check else None,
            calibration_enabled=args.calibration_enabled,
            show_hints=args.show_hints,
        )
    if command == "list-draft-style-checks":
        return app.list_draft_style_checks(args.project_id)
    if command == "read-draft-style-check":
        return app.read_draft_style_check(args.project_id, args.check_id)
    if command == "create-style-suggestion":
        return app.create_style_suggestion(args.project_id, args.check_id)
    if command == "list-style-suggestions":
        return app.list_style_suggestions(args.project_id)
    if command == "read-style-suggestion":
        return app.read_style_suggestion(args.project_id, args.suggestion_id)
    if command == "decide-style-suggestion":
        return app.decide_style_suggestion(
            args.project_id,
            args.suggestion_id,
            decision=args.decision,
            reason_code=args.reason_code,
        )
    if command == "create-manual-rewrite-task":
        return app.create_manual_rewrite_task(args.project_id, args.suggestion_id)
    if command == "list-manual-rewrite-tasks":
        return app.list_manual_rewrite_tasks(args.project_id, status=args.status)
    if command == "read-manual-rewrite-task":
        return app.read_manual_rewrite_task(args.project_id, args.task_id)
    if command == "mark-manual-rewrite-task":
        return app.mark_manual_rewrite_task(
            args.project_id,
            args.task_id,
            status=args.status,
            reason_code=args.reason_code,
        )
    if command == "submit-manual-rewrite-draft":
        text = sys.stdin.read() if args.text_stdin else args.text
        return app.submit_manual_rewrite_draft(args.project_id, args.task_id, text=text)
    if command == "compare-manual-rewrite-candidate":
        return app.compare_manual_rewrite_candidate(args.project_id, args.task_id)
    if command == "list-manual-rewrite-comparisons":
        return app.list_manual_rewrite_comparisons(args.project_id, status=args.status)
    if command == "read-manual-rewrite-comparison":
        return app.read_manual_rewrite_comparison(args.project_id, args.comparison_id)
    if command == "decide-manual-rewrite-comparison":
        return app.decide_manual_rewrite_comparison(
            args.project_id,
            args.comparison_id,
            decision=args.decision,
            reason_code=args.reason_code,
        )
    if command == "create-review-handoff-from-manual-comparison":
        return app.create_review_handoff_from_manual_comparison(args.project_id, args.comparison_id)
    if command == "list-review-handoffs":
        return app.list_review_handoffs(args.project_id, status=args.status)
    if command == "read-review-handoff":
        return app.read_review_handoff(args.project_id, args.handoff_id)
    if command == "state":
        return app.project_state(args.project_id)
    if command == "create-planning-item":
        text = sys.stdin.read() if args.text_stdin else args.text
        return app.create_planning_item(
            args.project_id,
            args.planning_id,
            text=text,
            title=args.title,
            item_type=args.item_type,
            active=args.active,
            enabled=not args.disabled,
            priority=args.priority,
            adherence_level=args.adherence_level,
            send_mode=args.send_mode,
            chapter_range=args.chapter_range,
        )
    if command == "list-planning-items":
        return app.list_planning_items(args.project_id)
    if command == "read-planning-item":
        return app.read_planning_item(args.project_id, args.planning_id, include_text=args.include_text)
    if command == "activate-planning-item":
        return app.set_planning_item_active(args.project_id, args.planning_id, active=True)
    if command == "deactivate-planning-item":
        return app.set_planning_item_active(args.project_id, args.planning_id, active=False)
    if command == "enable-planning-item":
        return app.set_planning_item_enabled(args.project_id, args.planning_id, enabled=True)
    if command == "disable-planning-item":
        return app.set_planning_item_enabled(args.project_id, args.planning_id, enabled=False)
    if command == "mark-chapter-planned":
        return app.mark_chapter_planned(args.project_id, args.chapter_id, title=args.title)
    if command == "chapter-status":
        return app.chapter_status(args.project_id, args.chapter_id)
    if command == "list-chapters":
        return app.list_chapters(args.project_id)
    if command == "configure-mock-writer":
        return app.configure_mock_writer(args.project_id, model=args.model)
    if command == "configure-provider-role":
        return app.configure_provider_role(
            args.project_id,
            args.role,
            provider=args.provider,
            model=args.model,
            api_key_ref=args.api_key_ref,
            base_url=args.base_url,
        )
    if command == "set-project-secret":
        value = sys.stdin.read().strip() if args.value_stdin else args.value
        return app.set_project_secret(args.project_id, args.name, value)
    if command == "generate-draft":
        return app.generate_draft(
            args.project_id,
            chapter_id=args.chapter_id,
            title=args.title,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "generate-context-draft":
        return app.generate_context_draft(
            args.project_id,
            chapter_id=args.chapter_id,
            title=args.title,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_context_tokens=args.max_context_tokens,
            final_assembly_gate_id=args.final_assembly_gate_id,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "list-drafts":
        return app.list_drafts(args.project_id)
    if command == "read-draft":
        return app.read_draft(args.project_id, args.draft_id)
    if command == "commit-draft":
        return app.commit_draft(args.project_id, args.draft_id)
    if command == "review-draft":
        return app.review_draft(args.project_id, args.draft_id)
    if command == "list-reviews":
        return app.list_reviews(args.project_id)
    if command == "read-review":
        return app.read_review(args.project_id, args.review_id)
    if command == "decide-review":
        return app.decide_review(
            args.project_id,
            args.review_id,
            decision=args.decision,
            reason_code=args.reason_code,
        )
    if command == "create-revision-request":
        return app.create_revision_request(args.project_id, args.review_id)
    if command == "list-revision-requests":
        return app.list_revision_requests(args.project_id)
    if command == "read-revision-request":
        return app.read_revision_request(args.project_id, args.revision_request_id)
    if command == "generate-revision-draft":
        return app.generate_revision_draft(args.project_id, args.revision_request_id)
    if command == "list-revision-candidates":
        return app.list_revision_candidates(args.project_id, args.revision_request_id)
    if command == "compare-revision-candidate":
        return app.compare_revision_candidate(args.project_id, args.revision_request_id, args.candidate_draft_id)
    if command == "enqueue-context-updates":
        return app.enqueue_context_updates(args.project_id)
    if command == "list-context-updates":
        return app.list_context_updates(args.project_id, status=args.status)
    if command == "mark-context-update":
        return app.mark_context_update(args.project_id, args.update_id, status=args.status, reason_code=args.reason_code)
    if command == "create-context-preview":
        return app.create_context_preview(args.project_id, args.update_id)
    if command == "list-context-previews":
        return app.list_context_previews(args.project_id)
    if command == "read-context-preview":
        return app.read_context_preview(args.project_id, args.preview_id)
    if command == "create-formal-context-plan":
        return app.create_formal_context_plan(args.project_id, args.preview_id)
    if command == "list-formal-context-plans":
        return app.list_formal_context_plans(args.project_id)
    if command == "read-formal-context-plan":
        return app.read_formal_context_plan(args.project_id, args.plan_id)
    if command == "context-assembly-dry-run":
        return app.context_assembly_dry_run(args.project_id, max_context_tokens=args.max_context_tokens)
    if command == "context-package-preview":
        return app.context_package_preview(
            args.project_id,
            max_context_tokens=args.max_context_tokens,
            include_text=args.include_text,
        )
    if command == "prompt-render-dry-run":
        return app.prompt_render_dry_run(
            args.project_id,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_context_tokens=args.max_context_tokens,
            include_prompt_text=args.include_prompt_text,
            include_context_text=args.include_context_text,
        )
    if command == "create-final-assembly-gate":
        return app.create_final_assembly_gate(
            args.project_id,
            chapter_id=args.chapter_id,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_context_tokens=args.max_context_tokens,
        )
    if command == "approve-final-assembly-gate":
        return app.approve_final_assembly_gate(args.project_id, args.gate_id, reason_code=args.reason_code)
    if command == "list-final-assembly-gates":
        return app.list_final_assembly_gates(args.project_id, status=args.status)
    if command == "read-final-assembly-gate":
        return app.read_final_assembly_gate(args.project_id, args.gate_id)
    if command == "create-final-provider-runbook":
        return app.create_final_provider_runbook(args.project_id, args.gate_id)
    if command == "list-final-provider-runbooks":
        return app.list_final_provider_runbooks(args.project_id, status=args.status)
    if command == "read-final-provider-runbook":
        return app.read_final_provider_runbook(args.project_id, args.runbook_id)
    if command == "authorize-final-provider-runbook":
        return app.authorize_final_provider_runbook(
            args.project_id,
            args.runbook_id,
            reason_code=args.reason_code,
        )
    if command == "list-final-provider-authorizations":
        return app.list_final_provider_authorizations(args.project_id, status=args.status)
    if command == "read-final-provider-authorization":
        return app.read_final_provider_authorization(args.project_id, args.authorization_id)
    if command == "create-final-provider-execution-preflight":
        return app.create_final_provider_execution_preflight(args.project_id, args.authorization_id)
    if command == "list-final-provider-execution-preflights":
        return app.list_final_provider_execution_preflights(args.project_id, status=args.status)
    if command == "read-final-provider-execution-preflight":
        return app.read_final_provider_execution_preflight(args.project_id, args.preflight_id)
    if command == "attempt-final-provider-execution":
        return app.attempt_final_provider_execution(args.project_id, args.preflight_id)
    if command == "list-final-provider-execution-attempts":
        return app.list_final_provider_execution_attempts(args.project_id, status=args.status)
    if command == "read-final-provider-execution-attempt":
        return app.read_final_provider_execution_attempt(args.project_id, args.attempt_id)
    if command == "create-final-provider-real-execution-readiness":
        return app.create_final_provider_real_execution_readiness(args.project_id, args.attempt_id)
    if command == "list-final-provider-real-execution-readiness":
        return app.list_final_provider_real_execution_readiness(args.project_id, status=args.status)
    if command == "read-final-provider-real-execution-readiness":
        return app.read_final_provider_real_execution_readiness(args.project_id, args.readiness_id)
    if command == "execute-final-provider-real":
        prompt = read_stdin_for_exact_prompt_match() if args.prompt_stdin else args.prompt
        return app.execute_final_provider_real(
            args.project_id,
            args.readiness_id,
            prompt=prompt,
            system_prompt=args.system_prompt,
            title=args.title,
            max_context_tokens=args.max_context_tokens,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            reason_code=args.reason_code,
        )
    if command == "list-final-provider-real-executions":
        return app.list_final_provider_real_executions(args.project_id, status=args.status)
    if command == "read-final-provider-real-execution":
        return app.read_final_provider_real_execution(args.project_id, args.execution_id)
    if command == "postcheck-final-provider-real-execution":
        return app.postcheck_final_provider_real_execution(args.project_id, args.execution_id)
    if command == "enqueue-formal-context-tasks":
        return app.enqueue_formal_context_tasks(args.project_id, args.plan_id)
    if command == "list-formal-context-tasks":
        return app.list_formal_context_tasks(args.project_id, status=args.status)
    if command == "mark-formal-context-task":
        return app.mark_formal_context_task(
            args.project_id,
            args.task_id,
            status=args.status,
            reason_code=args.reason_code,
        )
    if command == "create-memory-apply-preview":
        return app.create_memory_apply_preview(args.project_id, status=args.status)
    if command == "list-memory-apply-previews":
        return app.list_memory_apply_previews(args.project_id)
    if command == "read-memory-apply-preview":
        return app.read_memory_apply_preview(args.project_id, args.preview_id)
    if command == "commit-memory-apply-preview":
        return app.commit_memory_apply_preview(args.project_id, args.preview_id)
    if command == "list-memory-items":
        return app.list_memory_items(args.project_id)
    if command == "read-memory-item":
        return app.read_memory_item(args.project_id, args.memory_id, include_text=args.include_text)
    if command == "set-memory-text":
        text = sys.stdin.read().strip() if args.text_stdin else args.text
        return app.set_memory_text(args.project_id, args.memory_id, text)
    if command == "disable-memory-item":
        return app.set_memory_item_enabled(
            args.project_id,
            args.memory_id,
            enabled=False,
            reason_code=args.reason_code,
        )
    if command == "enable-memory-item":
        return app.set_memory_item_enabled(
            args.project_id,
            args.memory_id,
            enabled=True,
            reason_code=args.reason_code,
        )
    if command == "list-confirmed":
        return app.list_confirmed_chapters(args.project_id)
    if command == "read-confirmed":
        return app.read_confirmed_chapter(args.project_id, args.chapter_id)
    if command == "audit-project":
        return app.audit_project(args.project_id)
    if command == "provider-status":
        return app.provider_status(args.project_id, args.role)
    if command == "provider-dry-run":
        return app.provider_dry_run(
            args.project_id,
            args.role,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "provider-real-test":
        return app.provider_real_test(
            args.project_id,
            args.role,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    if command == "run-provider-smoke-test":
        return app.run_provider_smoke_test(
            args.project_id,
            args.role,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            reason_code=args.reason_code,
        )
    if command == "list-provider-smoke-tests":
        return app.list_provider_smoke_tests(args.project_id, status=args.status)
    if command == "read-provider-smoke-test":
        return app.read_provider_smoke_test(args.project_id, args.smoke_test_id)
    if command == "chutes-generate-once":
        secret_value = sys.stdin.read().strip() if args.secret_value_stdin else (args.secret_value or "")
        return app.chutes_generate_once(
            args.project_id,
            chapter_id=args.chapter_id,
            title=args.title,
            prompt=args.prompt,
            system_prompt=args.system_prompt,
            model=args.model,
            base_url=args.base_url,
            secret_name=args.secret_name,
            secret_value=secret_value,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            clear_secret_after_run=args.clear_secret_after_run,
        )
    if command == "list-provider-adapters":
        return app.list_provider_adapters()
    if command == "smoke":
        return run_smoke(app, args)
    raise ValueError(f"Unknown command: {command}")


def run_smoke(app: WorkbenchApplicationService, args: argparse.Namespace) -> dict[str, Any]:
    created = app.create_project(args.project_id, title=args.title)
    writer = app.configure_mock_writer(args.project_id)
    draft = app.generate_draft(
        args.project_id,
        chapter_id=args.chapter_id,
        title=args.chapter_title,
        prompt=args.prompt,
    )
    review = None
    decision = None
    committed = None
    if args.commit:
        app.configure_provider_role(args.project_id, "scorer", provider="mock", model="mock-scorer")
        review = app.review_draft(args.project_id, draft["draft_id"])
        decision = app.decide_review(args.project_id, review["review_id"], decision="accepted", reason_code="smoke_accept")
        committed = app.commit_draft(args.project_id, draft["draft_id"])
    state = app.project_state(args.project_id)
    return {
        "project": {"project_id": created["project_id"], "title": created["title"], "path": created["path"]},
        "writer": {"provider": writer["provider"], "model": writer["model"], "configured": bool(writer["provider"])},
        "draft": draft,
        "review": review,
        "review_decision": decision,
        "committed": committed,
        "state": state,
    }


def write_json(value: Any, *, stderr: bool = False) -> None:
    stream = sys.stderr if stderr else sys.stdout
    stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    stream.write("\n")


def read_stdin_for_exact_prompt_match() -> str:
    return sys.stdin.read().strip()


if __name__ == "__main__":
    raise SystemExit(main())
