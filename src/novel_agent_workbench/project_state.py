from __future__ import annotations

from typing import Any

from .chapters import ChapterWorkflowService
from .context_previews import ContextUpdatePreviewService
from .context_queue import ContextUpdateQueueService
from .corpus_boundaries import CorpusBoundaryService
from .corpus_profiles import CorpusProfileArtifactService
from .corpus_samples import CorpusSampleService
from .drafts import DraftGenerationService
from .final_assembly_gates import FinalAssemblyGateService
from .final_provider_authorizations import FinalProviderAuthorizationService
from .final_provider_execution_attempts import FinalProviderExecutionAttemptService
from .final_provider_execution_preflights import FinalProviderExecutionPreflightService
from .final_provider_real_executions import FinalProviderRealExecutionService
from .final_provider_real_execution_readiness import FinalProviderRealExecutionReadinessService
from .final_provider_runbooks import FinalProviderRunbookService
from .formal_context import FormalContextPlanService
from .formal_context_tasks import FormalContextTaskQueueService
from .manual_rewrite import ManualRewriteTaskService
from .manual_rewrite_comparison import ManualRewriteComparisonService
from .memory_apply_preview import MemoryApplyPreviewService
from .planning_library import normalize_library
from .provider_smoke_tests import ProviderSmokeTestService
from .providers import MODEL_ROLES, ProviderConfigError, get_model_role_config, safe_url_host
from .review_handoffs import ReviewHandoffService
from .reviews import DraftReviewService
from .revisions import RevisionRequestService
from .self_style import SelfStyleBaselineService
from .storage import ProjectStore


def public_project_state(store: ProjectStore, *, initialize: bool = True) -> dict[str, Any]:
    """Return a UI-safe project summary without prompt, content, or plaintext secrets."""

    if initialize:
        store.initialize()
    draft_service = DraftGenerationService(store)
    review_service = DraftReviewService(store)
    revision_request_service = RevisionRequestService(store)
    chapter_service = ChapterWorkflowService(store)
    context_queue_service = ContextUpdateQueueService(store)
    context_preview_service = ContextUpdatePreviewService(store)
    corpus_boundary_service = CorpusBoundaryService(store)
    corpus_profile_service = CorpusProfileArtifactService(store)
    corpus_sample_service = CorpusSampleService(store)
    self_style_service = SelfStyleBaselineService(store)
    formal_context_plan_service = FormalContextPlanService(store)
    formal_context_task_service = FormalContextTaskQueueService(store)
    manual_rewrite_task_service = ManualRewriteTaskService(store)
    manual_rewrite_comparison_service = ManualRewriteComparisonService(store)
    review_handoff_service = ReviewHandoffService(store)
    memory_apply_preview_service = MemoryApplyPreviewService(store)
    final_assembly_gate_service = FinalAssemblyGateService(store)
    final_provider_runbook_service = FinalProviderRunbookService(store)
    final_provider_authorization_service = FinalProviderAuthorizationService(store)
    final_provider_execution_preflight_service = FinalProviderExecutionPreflightService(store)
    final_provider_execution_attempt_service = FinalProviderExecutionAttemptService(store)
    final_provider_real_execution_readiness_service = FinalProviderRealExecutionReadinessService(store)
    final_provider_real_execution_service = FinalProviderRealExecutionService(store)
    provider_smoke_test_service = ProviderSmokeTestService(store)
    drafts = draft_service.list_drafts()
    reviews = review_service.list_reviews()
    revision_requests = revision_request_service.list_revision_requests()
    confirmed = draft_service.list_confirmed_chapters()
    chapters = chapter_service.list_chapters()
    context_updates = context_queue_service.list_context_updates()
    context_previews = context_preview_service.list_context_previews()
    corpus_boundaries = corpus_boundary_service.list_corpus_boundaries()
    corpus_profiles = corpus_profile_service.list_corpus_profiles()
    corpus_samples = corpus_sample_service.list_corpus_samples()
    style_baselines = self_style_service.list_baselines()
    style_checks = self_style_service.list_style_checks()
    style_suggestions = self_style_service.list_style_suggestions()
    formal_context_plans = formal_context_plan_service.list_formal_context_plans()
    formal_context_tasks = formal_context_task_service.list_tasks()
    manual_rewrite_tasks = manual_rewrite_task_service.list_tasks()
    manual_rewrite_comparisons = manual_rewrite_comparison_service.list_comparisons()
    review_handoffs = review_handoff_service.list_handoffs()
    memory_apply_previews = memory_apply_preview_service.list_memory_apply_previews()
    final_assembly_gates = final_assembly_gate_service.list_gates()
    final_provider_runbooks = final_provider_runbook_service.list_runbooks()
    final_provider_authorizations = final_provider_authorization_service.list_authorizations()
    final_provider_execution_preflights = final_provider_execution_preflight_service.list_preflights()
    final_provider_execution_attempts = final_provider_execution_attempt_service.list_attempts()
    final_provider_real_execution_readiness = final_provider_real_execution_readiness_service.list_readiness()
    final_provider_real_executions = final_provider_real_execution_service.list_executions()
    provider_smoke_tests = provider_smoke_test_service.list_smoke_tests()
    planning_items = safe_planning_items(store)
    memory_bank_items = safe_memory_bank_items(store)
    visible_chapters = visible_chapter_summaries(chapters, drafts, confirmed)
    store_state = store.public_state()
    config = store_state.get("config") if isinstance(store_state.get("config"), dict) else {}
    return {
        "project_id": store.project_id,
        "config": {
            "schema_version": config.get("schema_version"),
            "active_workflow_preset_id": config.get("active_workflow_preset_id"),
            "context_policy": config.get("context_policy") if isinstance(config.get("context_policy"), dict) else {},
        },
        "secrets": store_state.get("secrets", {}),
        "draft_count": len(drafts),
        "review_count": len(reviews),
        "revision_request_count": len(revision_requests),
        "context_update_count": len(context_updates),
        "context_preview_count": len(context_previews),
        "corpus_boundary_count": len(corpus_boundaries),
        "corpus_profile_count": len(corpus_profiles),
        "corpus_sample_count": len(corpus_samples),
        "self_style_baseline_count": len(style_baselines),
        "draft_style_check_count": len(style_checks),
        "style_suggestion_count": len(style_suggestions),
        "formal_context_plan_count": len(formal_context_plans),
        "formal_context_task_count": len(formal_context_tasks),
        "manual_rewrite_task_count": len(manual_rewrite_tasks),
        "manual_rewrite_comparison_count": len(manual_rewrite_comparisons),
        "review_handoff_count": len(review_handoffs),
        "memory_apply_preview_count": len(memory_apply_previews),
        "final_assembly_gate_count": len(final_assembly_gates),
        "final_provider_runbook_count": len(final_provider_runbooks),
        "final_provider_authorization_count": len(final_provider_authorizations),
        "final_provider_execution_preflight_count": len(final_provider_execution_preflights),
        "final_provider_execution_attempt_count": len(final_provider_execution_attempts),
        "final_provider_real_execution_readiness_count": len(final_provider_real_execution_readiness),
        "final_provider_real_execution_count": len(final_provider_real_executions),
        "provider_smoke_test_count": len(provider_smoke_tests),
        "planning_item_count": len(planning_items),
        "active_planning_reference_count": sum(1 for item in planning_items if planning_item_active(item)),
        "memory_bank_item_count": len(memory_bank_items),
        "chapter_count": len(visible_chapters),
        "committed_chapter_count": len(confirmed),
        "latest_chapter": safe_chapter_summary(latest_by(visible_chapters, "updated_at")),
        "latest_draft": safe_draft_summary(latest_by(drafts, "created_at")),
        "latest_review": safe_review_summary(latest_by(reviews, "created_at")),
        "latest_revision_request": safe_revision_request_summary(latest_by(revision_requests, "created_at")),
        "latest_context_update": safe_context_update_summary(latest_by(context_updates, "updated_at")),
        "latest_context_preview": safe_context_preview_summary(latest_by(context_previews, "created_at")),
        "latest_corpus_boundary": safe_corpus_boundary_summary(latest_by(corpus_boundaries, "created_at")),
        "latest_corpus_profile": safe_corpus_profile_summary(latest_by(corpus_profiles, "created_at")),
        "latest_corpus_sample": safe_corpus_sample_summary(latest_by(corpus_samples, "created_at")),
        "latest_self_style_baseline": safe_self_style_baseline_summary(latest_by(style_baselines, "created_at")),
        "latest_draft_style_check": safe_draft_style_check_summary(latest_by(style_checks, "created_at")),
        "latest_style_suggestion": safe_style_suggestion_summary(latest_by(style_suggestions, "created_at")),
        "latest_formal_context_plan": safe_formal_context_plan_summary(
            latest_by(formal_context_plans, "created_at")
        ),
        "latest_formal_context_task": safe_formal_context_task_summary(
            latest_by(formal_context_tasks, "updated_at")
        ),
        "latest_manual_rewrite_task": safe_manual_rewrite_task_summary(
            latest_by(manual_rewrite_tasks, "updated_at")
        ),
        "latest_manual_rewrite_comparison": safe_manual_rewrite_comparison_summary(
            latest_by(manual_rewrite_comparisons, "updated_at")
        ),
        "latest_review_handoff": safe_review_handoff_summary(latest_by(review_handoffs, "updated_at")),
        "latest_memory_apply_preview": safe_memory_apply_preview_summary(
            latest_by(memory_apply_previews, "created_at")
        ),
        "latest_final_assembly_gate": safe_final_assembly_gate_summary(latest_by(final_assembly_gates, "created_at")),
        "latest_final_provider_runbook": safe_final_provider_runbook_summary(
            latest_by(final_provider_runbooks, "created_at")
        ),
        "latest_final_provider_authorization": safe_final_provider_authorization_summary(
            latest_by(final_provider_authorizations, "created_at")
        ),
        "latest_final_provider_execution_preflight": safe_final_provider_execution_preflight_summary(
            latest_by(final_provider_execution_preflights, "created_at")
        ),
        "latest_final_provider_execution_attempt": safe_final_provider_execution_attempt_summary(
            latest_by(final_provider_execution_attempts, "created_at")
        ),
        "latest_final_provider_real_execution_readiness": safe_final_provider_real_execution_readiness_summary(
            latest_by(final_provider_real_execution_readiness, "created_at")
        ),
        "latest_final_provider_real_execution": safe_final_provider_real_execution_summary(
            latest_by(final_provider_real_executions, "created_at")
        ),
        "latest_provider_smoke_test": safe_provider_smoke_test_summary(
            latest_by(provider_smoke_tests, "created_at")
        ),
        "latest_planning_item": safe_planning_item_summary(latest_by(planning_items, "updated_at")),
        "latest_memory_bank_item": safe_memory_bank_item_summary(latest_by(memory_bank_items, "updated_at")),
        "latest_committed_chapter": safe_confirmed_summary(latest_by(confirmed, "committed_at")),
        "provider_roles": provider_roles_summary(store),
    }


def provider_roles_summary(store: ProjectStore) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    public_secrets = store.public_state().get("secrets", {})
    for role in sorted(MODEL_ROLES):
        role_config = get_model_role_config(store, role)
        config_error = ""
        try:
            secret_name = role_config.secret_name() if role_config.api_key_ref else ""
        except ProviderConfigError as exc:
            secret_name = ""
            config_error = str(exc)
        secret_state = public_secrets.get(secret_name) if isinstance(public_secrets, dict) and secret_name else {}
        summary[role] = {
            "configured": role_config.is_configured(),
            "provider": role_config.provider,
            "model": role_config.model,
            "base_url_host": safe_url_host(role_config.base_url),
            "api_key_ref": role_config.api_key_ref,
            "has_api_key": bool(secret_state.get("has_value")) if isinstance(secret_state, dict) else False,
            "masked_key": str(secret_state.get("masked") or "") if isinstance(secret_state, dict) else "",
            "config_error": config_error,
        }
    return summary


def visible_chapter_summaries(
    chapters: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
    confirmed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    draft_chapter_ids = {str(item.get("chapter_id") or "") for item in drafts if item.get("chapter_id")}
    confirmed_chapter_ids = {str(item.get("chapter_id") or "") for item in confirmed if item.get("chapter_id")}
    visible_ids = draft_chapter_ids | confirmed_chapter_ids
    if not visible_ids:
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chapter in chapters:
        chapter_id = str(chapter.get("chapter_id") or "")
        if not chapter_id or chapter_id in seen:
            continue
        if chapter_id not in visible_ids and str(chapter.get("status") or "") != "planned":
            continue
        result.append(chapter)
        seen.add(chapter_id)
    for chapter_id in sorted(visible_ids - seen):
        result.append({"chapter_id": chapter_id, "status": "draft_ready", "updated_at": ""})
    return result


def latest_by(items: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda item: str(item.get(key) or ""))


def safe_draft_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "committed_at": item.get("committed_at"),
        "committed_chapter_id": item.get("committed_chapter_id"),
        "provider": item.get("provider"),
        "model": item.get("model"),
    }


def safe_confirmed_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "committed_at": item.get("committed_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
        "usage": item.get("usage") if isinstance(item.get("usage"), dict) else {},
    }


def safe_review_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "review_id": item.get("review_id"),
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
        "recommendation": item.get("recommendation"),
        "decision": item.get("decision") if isinstance(item.get("decision"), dict) else {},
    }


def safe_revision_request_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "revision_request_id": item.get("revision_request_id"),
        "review_id": item.get("review_id"),
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "source_decision": item.get("source_decision") if isinstance(item.get("source_decision"), dict) else {},
        "revision_policy": item.get("revision_policy"),
    }


def safe_context_update_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "update_id": item.get("update_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "confirmed_chapter_id": item.get("confirmed_chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "targets": item.get("targets") if isinstance(item.get("targets"), dict) else {},
    }


def safe_context_preview_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "preview_id": item.get("preview_id"),
        "update_id": item.get("update_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "confirmed_chapter_id": item.get("confirmed_chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "recommendation": item.get("recommendation"),
    }


def safe_corpus_profile_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "profile_id": item.get("profile_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "file_name": item.get("file_name"),
        "source_sha256": item.get("source_sha256"),
        "encoding": item.get("encoding") if isinstance(item.get("encoding"), dict) else {},
        "strict_chapter_heading_count": item.get("strict_chapter_heading_count"),
        "line_count": item.get("line_count"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_corpus_boundary_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "boundary_id": item.get("boundary_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "file_name": item.get("file_name"),
        "source_sha256": item.get("source_sha256"),
        "encoding": item.get("encoding") if isinstance(item.get("encoding"), dict) else {},
        "chapter_count": item.get("chapter_count"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_corpus_sample_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "sample_id": item.get("sample_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "test_only": item.get("test_only"),
        "publish_blocker": item.get("publish_blocker"),
        "boundary_id": item.get("boundary_id"),
        "ordinal": item.get("ordinal"),
        "source_sha256": item.get("source_sha256"),
        "char_count": item.get("char_count"),
    }


def safe_self_style_baseline_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "baseline_id": item.get("baseline_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "chapter_count": item.get("chapter_count"),
        "metrics": item.get("metrics") if isinstance(item.get("metrics"), dict) else {},
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_draft_style_check_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "check_id": item.get("check_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "baseline_id": item.get("baseline_id"),
        "scene_mode": item.get("scene_mode"),
        "issue_count": item.get("issue_count"),
        "hint_count": item.get("hint_count"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_style_suggestion_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "suggestion_id": item.get("suggestion_id"),
        "check_id": item.get("check_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "scene_mode": item.get("scene_mode"),
        "suggestion_count": item.get("suggestion_count"),
        "decision": item.get("decision") if isinstance(item.get("decision"), dict) else {},
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_formal_context_plan_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "plan_id": item.get("plan_id"),
        "preview_id": item.get("preview_id"),
        "update_id": item.get("update_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "confirmed_chapter_id": item.get("confirmed_chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "recommendation": item.get("recommendation"),
        "priority_order": item.get("priority_order") if isinstance(item.get("priority_order"), list) else [],
    }


def safe_formal_context_task_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "task_id": item.get("task_id"),
        "plan_id": item.get("plan_id"),
        "preview_id": item.get("preview_id"),
        "update_id": item.get("update_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "category_id": item.get("category_id"),
        "priority": item.get("priority"),
        "target": item.get("target"),
        "memory_weight": item.get("memory_weight"),
        "recommendation": item.get("recommendation"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def safe_manual_rewrite_task_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "task_id": item.get("task_id"),
        "suggestion_id": item.get("suggestion_id"),
        "check_id": item.get("check_id"),
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "reason_code": item.get("reason_code"),
        "submitted_draft_id": item.get("submitted_draft_id"),
        "submitted_at": item.get("submitted_at"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_manual_rewrite_comparison_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "comparison_id": item.get("comparison_id"),
        "task_id": item.get("task_id"),
        "suggestion_id": item.get("suggestion_id"),
        "check_id": item.get("check_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "submitted_draft_id": item.get("submitted_draft_id"),
        "status": item.get("status"),
        "char_count_delta": item.get("char_count_delta"),
        "paragraph_count_delta": item.get("paragraph_count_delta"),
        "decision": item.get("decision") if isinstance(item.get("decision"), dict) else {},
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_review_handoff_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "handoff_id": item.get("handoff_id"),
        "comparison_id": item.get("comparison_id"),
        "task_id": item.get("task_id"),
        "suggestion_id": item.get("suggestion_id"),
        "check_id": item.get("check_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "selected_draft_id": item.get("selected_draft_id"),
        "status": item.get("status"),
        "review": item.get("review") if isinstance(item.get("review"), dict) else {},
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }


def safe_memory_apply_preview_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "preview_id": item.get("preview_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "task_status_filter": item.get("task_status_filter"),
        "task_count": item.get("task_count"),
        "recommendation": item.get("recommendation"),
    }


def safe_final_assembly_gate_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    prompt_summary = item.get("prompt_summary") if isinstance(item.get("prompt_summary"), dict) else {}
    writer_role = item.get("writer_role") if isinstance(item.get("writer_role"), dict) else {}
    return {
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "approved_at": item.get("approved_at"),
        "provider": writer_role.get("provider"),
        "model": writer_role.get("model"),
        "context_section_count": prompt_summary.get("context_section_count"),
        "estimated_total_tokens": prompt_summary.get("estimated_total_tokens"),
    }


def safe_final_provider_runbook_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    writer_role = item.get("writer_role") if isinstance(item.get("writer_role"), dict) else {}
    return {
        "runbook_id": item.get("runbook_id"),
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider") or writer_role.get("provider"),
        "model": item.get("model") or writer_role.get("model"),
        "context_section_count": item.get("context_section_count"),
        "estimated_total_tokens": item.get("estimated_total_tokens"),
    }


def safe_final_provider_authorization_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    writer_role = item.get("writer_role") if isinstance(item.get("writer_role"), dict) else {}
    return {
        "authorization_id": item.get("authorization_id"),
        "runbook_id": item.get("runbook_id"),
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider") or writer_role.get("provider"),
        "model": item.get("model") or writer_role.get("model"),
        "checkpoint_id": item.get("checkpoint_id"),
    }


def safe_final_provider_execution_preflight_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "preflight_id": item.get("preflight_id"),
        "authorization_id": item.get("authorization_id"),
        "runbook_id": item.get("runbook_id"),
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
        "issue_count": item.get("issue_count"),
        "issue_codes": item.get("issue_codes") if isinstance(item.get("issue_codes"), list) else [],
    }


def safe_final_provider_execution_attempt_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "attempt_id": item.get("attempt_id"),
        "preflight_id": item.get("preflight_id"),
        "authorization_id": item.get("authorization_id"),
        "runbook_id": item.get("runbook_id"),
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "abort_reason_code": item.get("abort_reason_code"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
    }


def safe_final_provider_real_execution_readiness_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "readiness_id": item.get("readiness_id"),
        "attempt_id": item.get("attempt_id"),
        "preflight_id": item.get("preflight_id"),
        "authorization_id": item.get("authorization_id"),
        "runbook_id": item.get("runbook_id"),
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
        "issue_count": item.get("issue_count"),
        "issue_codes": item.get("issue_codes") if isinstance(item.get("issue_codes"), list) else [],
    }


def safe_final_provider_real_execution_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "execution_id": item.get("execution_id"),
        "readiness_id": item.get("readiness_id"),
        "attempt_id": item.get("attempt_id"),
        "preflight_id": item.get("preflight_id"),
        "authorization_id": item.get("authorization_id"),
        "runbook_id": item.get("runbook_id"),
        "gate_id": item.get("gate_id"),
        "chapter_id": item.get("chapter_id"),
        "draft_id": item.get("draft_id"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
    }


def safe_provider_smoke_test_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "smoke_test_id": item.get("smoke_test_id"),
        "purpose": item.get("purpose"),
        "status": item.get("status"),
        "ok": item.get("ok"),
        "created_at": item.get("created_at"),
        "role": item.get("role"),
        "provider": item.get("provider"),
        "model": item.get("model"),
        "base_url_host": item.get("base_url_host"),
        "network_attempted": item.get("network_attempted"),
    }


def safe_memory_bank_items(store: ProjectStore) -> list[dict[str, Any]]:
    value = store.read_json(store.data_file_path("memory_bank.json"), default={"items": []})
    items = value.get("items") if isinstance(value, dict) and isinstance(value.get("items"), list) else []
    return [item for item in items if isinstance(item, dict)]


def safe_planning_items(store: ProjectStore) -> list[dict[str, Any]]:
    value = store.read_json(store.data_file_path("planning_library.json"), default={})
    return normalize_library(value)["items"]


def planning_item_active(item: dict[str, Any]) -> bool:
    enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
    return bool(enabled and item.get("active"))


def safe_planning_item_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "planning_id": item.get("planning_id") or item.get("id"),
        "title": item.get("title"),
        "item_type": item.get("item_type") or "outline",
        "active": bool(item.get("active")),
        "enabled": item.get("enabled") if isinstance(item.get("enabled"), bool) else True,
        "priority": item.get("priority"),
        "adherence_level": item.get("adherence_level") or "balanced",
        "send_mode": item.get("send_mode") or "reference_text",
        "chapter_range": item.get("chapter_range") or "",
        "text_status": item.get("text_status"),
        "text_chars": len(str(item.get("text") or "")),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def safe_memory_bank_item_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "memory_id": item.get("memory_id") or item.get("id"),
        "entry_type": item.get("entry_type"),
        "status": item.get("status"),
        "source_preview_id": item.get("source_preview_id"),
        "source_task_id": item.get("source_task_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "category_id": item.get("category_id"),
        "priority": item.get("priority"),
        "memory_weight": item.get("memory_weight"),
        "duplicate_risk": item.get("duplicate_risk"),
        "enabled": item.get("enabled") if isinstance(item.get("enabled"), bool) else True,
        "lifecycle_status": item.get("lifecycle_status") or "active",
        "lifecycle_reason_code": item.get("lifecycle_reason_code") or "",
        "text_status": item.get("text_status"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def safe_chapter_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "latest_draft_id": item.get("latest_draft_id"),
        "latest_review_id": item.get("latest_review_id"),
        "latest_review_decision": item.get("latest_review_decision")
        if isinstance(item.get("latest_review_decision"), dict)
        else {},
        "latest_revision_request_id": item.get("latest_revision_request_id"),
        "latest_revision_draft_id": item.get("latest_revision_draft_id"),
        "confirmed_chapter_id": item.get("confirmed_chapter_id"),
        "updated_at": item.get("updated_at"),
        "error_summary": item.get("error_summary") if isinstance(item.get("error_summary"), dict) else {},
    }
