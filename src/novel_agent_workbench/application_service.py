from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .audit import audit_project
from .config import (
    GENERATION_SETTINGS_SCOPE_GLOBAL,
    GENERATION_SETTINGS_SCOPE_PROJECT,
    deep_merge,
    default_generation_settings,
    default_global_settings,
    effective_generation_settings,
    effective_layered_generation_settings,
    project_has_generation_settings_override,
)
from .context_previews import ContextUpdatePreviewService
from .chapters import ChapterWorkflowService
from .context_assembler import ContextAssemblerService
from .context_queue import ContextUpdateQueueService
from .corpus_boundaries import CorpusBoundaryService
from .corpus_profiler import profile_corpus
from .corpus_profiles import CorpusProfileArtifactService
from .corpus_samples import CorpusSampleService
from .drafts import (
    DraftGenerationRequest,
    DraftGenerationService,
    render_context_prompt,
    sanitize_provider_draft_text,
    stream_sanitizer_callback,
)
from .final_assembly_gates import FinalAssemblyGateService
from .final_provider_authorizations import FinalProviderAuthorizationService
from .final_provider_execution_attempts import FinalProviderExecutionAttemptService
from .final_provider_execution_preflights import FinalProviderExecutionPreflightService
from .final_provider_real_executions import FinalProviderRealExecutionService
from .final_provider_real_execution_readiness import FinalProviderRealExecutionReadinessService
from .final_provider_runbooks import FinalProviderRunbookService
from .formal_context import FormalContextPlanService
from .formal_context_tasks import FormalContextTaskQueueService
from .exports import TxtManuscriptExportService
from .manual_rewrite import ManualRewriteTaskService
from .manual_rewrite_comparison import ManualRewriteComparisonService
from .memory_apply_preview import MemoryApplyPreviewService
from .memory_bank import MemoryBankService
from .planning_library import PlanningLibraryService
from .project_state import public_project_state
from .project_health import project_health
from .provider_smoke_tests import ProviderSmokeTestService
from .publication import prepublish_check
from .providers import (
    ModelRoleConfig,
    ProviderRequest,
    SECRET_REF_PREFIX,
    get_provider_adapter,
    configure_provider_role,
    generate_with_provider,
    get_model_role_config,
    list_provider_adapters,
    provider_dry_run,
    provider_real_test,
    provider_request_role_or_writer_fallback,
    provider_status,
    set_model_role_config,
    set_project_secret,
    validate_model_role_config,
    validate_secret_name,
)
from .review_handoffs import ReviewHandoffService
from .runbooks import ChutesGenerateOnceRequest, chutes_generate_once
from .reviews import DraftReviewService, is_ai_review, render_context_stats
from .revision_candidates import RevisionCandidateService
from .revisions import RevisionRequestService
from .self_style import SelfStyleBaselineService
from .storage import ProjectRegistry, ProjectStore, atomic_write_json_file


GLOBAL_SETTINGS_FILENAME = "global_settings.json"
GLOBAL_SECRETS_FILENAME = "global_secrets.local.json"


class RuntimeModelSettingsStore:
    """Project store view that reads software-level model settings at runtime."""

    def __init__(self, store: ProjectStore, *, model_roles: dict[str, Any], secrets: dict[str, Any]):
        self._store = store
        self._model_roles = model_roles
        self._secrets = secrets

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def read_config(self) -> dict[str, Any]:
        config = dict(self._store.read_config())
        if self._model_roles:
            config["model_roles"] = self._model_roles
        return config

    def read_secrets(self) -> dict[str, Any]:
        return dict(self._secrets)
AI_REFINEMENT_SYSTEM_PROMPT = (
    "你是一名专业小说改稿编辑。当前任务不是续写新章节，而是根据 AI 审稿意见精修当前草稿。"
    "AI 审稿意见是本次改稿的主要约束；必须逐条落实其中明确指出的问题。"
    "若审稿意见与已给定上下文、前文事实或草稿事实冲突，以保持连续性为最高规则，"
    "但不得无视审稿意见。只输出修订后的小说正文，不输出说明、分析或 <think>。"
)


@dataclass(frozen=True, slots=True)
class WorkbenchApplicationService:
    """Stable backend facade for future CLI, HTTP, or UI layers."""

    registry: ProjectRegistry

    @classmethod
    def default(cls) -> "WorkbenchApplicationService":
        return cls(ProjectRegistry.default())

    @classmethod
    def open(cls, projects_root: str | Path) -> "WorkbenchApplicationService":
        return cls(ProjectRegistry.open(projects_root))

    def create_project(self, project_id: str, *, title: str = "") -> dict[str, Any]:
        store = self.registry.create_project(project_id, title=title)
        return {
            "project_id": project_id,
            "title": store.read_project_meta().get("title"),
            "path": str(store.root),
            "state": public_project_state(store),
        }

    def list_projects(self) -> list[dict[str, Any]]:
        return self.registry.list_projects()

    def delete_project(self, project_id: str) -> dict[str, Any]:
        return self.registry.delete_project(project_id)

    def clear_trash(self) -> dict[str, Any]:
        return self.registry.clear_trash()

    def prepublish_check(self, *, repo_root: str | Path | None = None) -> dict[str, Any]:
        root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[2]
        return prepublish_check(root, projects_root=self.registry.projects_root)

    def project_health(self, project_id: str, *, repo_root: str | Path | None = None) -> dict[str, Any]:
        return project_health(self._runtime_store(project_id), repo_root=repo_root).to_dict()

    def profile_corpus(self, path: str | Path, *, max_name_candidates: int = 20) -> dict[str, Any]:
        return profile_corpus(path, max_name_candidates=max_name_candidates).to_dict()

    def save_corpus_profile(
        self,
        project_id: str,
        path: str | Path,
        *,
        max_name_candidates: int = 20,
    ) -> dict[str, Any]:
        return CorpusProfileArtifactService(self._open_store(project_id)).save_corpus_profile(
            path,
            max_name_candidates=max_name_candidates,
        ).to_dict()

    def list_corpus_profiles(self, project_id: str) -> list[dict[str, Any]]:
        return CorpusProfileArtifactService(self._open_store(project_id)).list_corpus_profiles()

    def read_corpus_profile(self, project_id: str, profile_id: str) -> dict[str, Any]:
        return CorpusProfileArtifactService(self._open_store(project_id)).read_corpus_profile(profile_id)

    def save_corpus_boundaries(self, project_id: str, path: str | Path) -> dict[str, Any]:
        return CorpusBoundaryService(self._open_store(project_id)).save_corpus_boundaries(path).to_dict()

    def list_corpus_boundaries(self, project_id: str) -> list[dict[str, Any]]:
        return CorpusBoundaryService(self._open_store(project_id)).list_corpus_boundaries()

    def read_corpus_boundaries(self, project_id: str, boundary_id: str) -> dict[str, Any]:
        return CorpusBoundaryService(self._open_store(project_id)).read_corpus_boundaries(boundary_id)

    def create_corpus_sample(
        self,
        project_id: str,
        boundary_id: str,
        source_path: str | Path,
        *,
        ordinal: int,
        max_chars: int = 800,
    ) -> dict[str, Any]:
        return CorpusSampleService(self._open_store(project_id)).create_corpus_sample(
            boundary_id,
            source_path,
            ordinal=ordinal,
            max_chars=max_chars,
        ).to_dict()

    def list_corpus_samples(self, project_id: str) -> list[dict[str, Any]]:
        return CorpusSampleService(self._open_store(project_id)).list_corpus_samples()

    def read_corpus_sample(self, project_id: str, sample_id: str, *, include_text: bool = False) -> dict[str, Any]:
        return CorpusSampleService(self._open_store(project_id)).read_corpus_sample(sample_id, include_text=include_text)

    def create_self_style_baseline(self, project_id: str) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).create_baseline().to_dict()

    def list_self_style_baselines(self, project_id: str) -> list[dict[str, Any]]:
        return SelfStyleBaselineService(self._open_store(project_id)).list_baselines()

    def read_self_style_baseline(self, project_id: str, baseline_id: str) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).read_baseline(baseline_id)

    def check_draft_style(
        self,
        project_id: str,
        draft_id: str,
        *,
        baseline_id: str = "",
        scene_mode: str = "general",
        enabled: bool | None = None,
        calibration_enabled: bool | None = None,
        show_hints: bool | None = None,
    ) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).check_draft_against_baseline(
            draft_id,
            baseline_id=baseline_id,
            scene_mode=scene_mode,
            enabled=enabled,
            calibration_enabled=calibration_enabled,
            show_hints=show_hints,
        ).to_dict()

    def list_draft_style_checks(self, project_id: str) -> list[dict[str, Any]]:
        return SelfStyleBaselineService(self._open_store(project_id)).list_style_checks()

    def read_draft_style_check(self, project_id: str, check_id: str) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).read_style_check(check_id)

    def create_style_suggestion(self, project_id: str, check_id: str) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).create_style_suggestion(check_id).to_dict()

    def list_style_suggestions(self, project_id: str) -> list[dict[str, Any]]:
        return SelfStyleBaselineService(self._open_store(project_id)).list_style_suggestions()

    def read_style_suggestion(self, project_id: str, suggestion_id: str) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).read_style_suggestion(suggestion_id)

    def decide_style_suggestion(
        self,
        project_id: str,
        suggestion_id: str,
        *,
        decision: str,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return SelfStyleBaselineService(self._open_store(project_id)).decide_style_suggestion(
            suggestion_id,
            decision=decision,
            reason_code=reason_code,
        ).to_dict()

    def create_manual_rewrite_task(self, project_id: str, suggestion_id: str) -> dict[str, Any]:
        return ManualRewriteTaskService(self._open_store(project_id)).create_task_from_style_suggestion(
            suggestion_id,
        ).to_dict()

    def list_manual_rewrite_tasks(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return ManualRewriteTaskService(self._open_store(project_id)).list_tasks(status=status)

    def read_manual_rewrite_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        return ManualRewriteTaskService(self._open_store(project_id)).read_task(task_id)

    def mark_manual_rewrite_task(
        self,
        project_id: str,
        task_id: str,
        *,
        status: str,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return ManualRewriteTaskService(self._open_store(project_id)).mark_task(
            task_id,
            status=status,
            reason_code=reason_code,
        ).to_dict()

    def submit_manual_rewrite_draft(self, project_id: str, task_id: str, *, text: str) -> dict[str, Any]:
        return ManualRewriteTaskService(self._open_store(project_id)).submit_manual_rewrite_draft(
            task_id,
            text=text,
        ).to_dict()

    def compare_manual_rewrite_candidate(self, project_id: str, task_id: str) -> dict[str, Any]:
        return ManualRewriteComparisonService(self._open_store(project_id)).create_comparison(task_id).to_dict()

    def list_manual_rewrite_comparisons(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return ManualRewriteComparisonService(self._open_store(project_id)).list_comparisons(status=status)

    def read_manual_rewrite_comparison(self, project_id: str, comparison_id: str) -> dict[str, Any]:
        return ManualRewriteComparisonService(self._open_store(project_id)).read_comparison(comparison_id)

    def decide_manual_rewrite_comparison(
        self,
        project_id: str,
        comparison_id: str,
        *,
        decision: str,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return ManualRewriteComparisonService(self._open_store(project_id)).decide_comparison(
            comparison_id,
            decision=decision,
            reason_code=reason_code,
        ).to_dict()

    def create_review_handoff_from_manual_comparison(self, project_id: str, comparison_id: str) -> dict[str, Any]:
        return ReviewHandoffService(self._open_store(project_id)).create_from_manual_comparison(comparison_id).to_dict()

    def list_review_handoffs(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return ReviewHandoffService(self._open_store(project_id)).list_handoffs(status=status)

    def read_review_handoff(self, project_id: str, handoff_id: str) -> dict[str, Any]:
        return ReviewHandoffService(self._open_store(project_id)).read_handoff(handoff_id)

    def project_state(self, project_id: str) -> dict[str, Any]:
        return public_project_state(self._runtime_store(project_id))

    def global_generation_settings(self) -> dict[str, Any]:
        return effective_generation_settings(self._read_global_settings())

    def update_global_generation_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        updated = deep_merge(self.global_generation_settings(), settings)
        global_settings = self._read_global_settings()
        global_settings["schema_version"] = 1
        global_settings["generation_settings"] = updated
        self._write_global_settings(global_settings)
        return updated

    def reset_global_generation_settings(self) -> dict[str, Any]:
        defaults = default_generation_settings()
        global_settings = self._read_global_settings()
        global_settings["schema_version"] = 1
        global_settings["generation_settings"] = defaults
        self._write_global_settings(global_settings)
        return defaults

    def generation_settings(self, project_id: str) -> dict[str, Any]:
        store = self._open_store(project_id)
        store.initialize()
        settings, _ = self._effective_project_generation_settings(store)
        return settings

    def project_generation_settings_state(self, project_id: str) -> dict[str, Any]:
        store = self._open_store(project_id)
        store.initialize()
        settings, has_override = self._effective_project_generation_settings(store)
        return {
            "project_id": project_id,
            "source": "project" if has_override else "global",
            "has_project_override": has_override,
            "settings": settings,
            "project_config_path": str(store.config_path),
            "global_settings_path": str(self._global_settings_path()),
        }

    def update_generation_settings(self, project_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        store = self._open_store(project_id)
        store.initialize()
        with store.lock():
            config = store.read_config()
            current, _ = self._effective_project_generation_settings(store, config=config)
            updated = deep_merge(current, settings)
            config["generation_settings"] = updated
            config["generation_settings_scope"] = GENERATION_SETTINGS_SCOPE_PROJECT
            context_settings = updated.get("context") if isinstance(updated.get("context"), dict) else {}
            context_policy = config.get("context_policy") if isinstance(config.get("context_policy"), dict) else {}
            if isinstance(context_settings.get("max_context_tokens"), int):
                context_policy["max_context_tokens"] = context_settings["max_context_tokens"]
            if isinstance(context_settings.get("recent_confirmed_chapter_count"), int):
                context_policy["recent_confirmed_chapter_count"] = context_settings["recent_confirmed_chapter_count"]
            config["context_policy"] = context_policy
            config["model_roles"] = merged_writer_sampling_settings(config.get("model_roles"), updated)
            store.write_config(config)
            return effective_generation_settings(config)

    def reset_generation_settings(self, project_id: str) -> dict[str, Any]:
        return self.clear_project_generation_settings(project_id)

    def clear_project_generation_settings(self, project_id: str) -> dict[str, Any]:
        store = self._open_store(project_id)
        store.initialize()
        with store.lock():
            config = store.read_config()
            global_settings = self.global_generation_settings()
            self._apply_generation_settings_to_config(
                config,
                global_settings,
                scope=GENERATION_SETTINGS_SCOPE_GLOBAL,
            )
            store.write_config(config)
            return global_settings

    def create_planning_item(
        self,
        project_id: str,
        planning_id: str,
        *,
        text: str,
        title: str = "",
        item_type: str = "outline",
        active: bool = False,
        enabled: bool = True,
        priority: int = 10,
        adherence_level: str = "balanced",
        send_mode: str = "reference_text",
        chapter_range: str = "",
    ) -> dict[str, Any]:
        return PlanningLibraryService(self._open_store(project_id)).create_planning_item(
            planning_id,
            text=text,
            title=title,
            item_type=item_type,
            active=active,
            enabled=enabled,
            priority=priority,
            adherence_level=adherence_level,
            send_mode=send_mode,
            chapter_range=chapter_range,
        ).to_dict()

    def update_planning_item(
        self,
        project_id: str,
        planning_id: str,
        *,
        text: str,
        title: str = "",
        item_type: str = "outline",
        active: bool = False,
        enabled: bool = True,
        priority: int = 10,
        adherence_level: str = "balanced",
        send_mode: str = "reference_text",
        chapter_range: str = "",
    ) -> dict[str, Any]:
        return PlanningLibraryService(self._open_store(project_id)).update_planning_item(
            planning_id,
            text=text,
            title=title,
            item_type=item_type,
            active=active,
            enabled=enabled,
            priority=priority,
            adherence_level=adherence_level,
            send_mode=send_mode,
            chapter_range=chapter_range,
        ).to_dict()

    def list_planning_items(self, project_id: str, *, include_text: bool = False) -> list[dict[str, Any]]:
        return PlanningLibraryService(self._open_store(project_id)).list_planning_items(include_text=include_text)

    def read_planning_item(
        self,
        project_id: str,
        planning_id: str,
        *,
        include_text: bool = False,
    ) -> dict[str, Any]:
        return PlanningLibraryService(self._open_store(project_id)).read_planning_item(
            planning_id,
            include_text=include_text,
        )

    def set_planning_item_active(self, project_id: str, planning_id: str, *, active: bool) -> dict[str, Any]:
        return PlanningLibraryService(self._open_store(project_id)).set_planning_item_active(
            planning_id,
            active=active,
        ).to_dict()

    def set_planning_item_enabled(self, project_id: str, planning_id: str, *, enabled: bool) -> dict[str, Any]:
        return PlanningLibraryService(self._open_store(project_id)).set_planning_item_enabled(
            planning_id,
            enabled=enabled,
        ).to_dict()

    def mark_chapter_planned(self, project_id: str, chapter_id: str, *, title: str = "") -> dict[str, Any]:
        return ChapterWorkflowService(self._open_store(project_id)).mark_planned(chapter_id, title=title)

    def list_chapters(self, project_id: str) -> list[dict[str, Any]]:
        return ChapterWorkflowService(self._open_store(project_id)).list_chapters()

    def chapter_status(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        return ChapterWorkflowService(self._open_store(project_id)).get_chapter(chapter_id)

    def configure_mock_writer(self, project_id: str, *, model: str = "mock-writer") -> dict[str, Any]:
        store = self._open_store(project_id)
        role_config = set_model_role_config(store, "writer", {"provider": "mock", "model": model})
        return role_config.to_dict()

    def configure_provider_role(
        self,
        project_id: str,
        role: str,
        *,
        provider: str,
        model: str,
        api_key_ref: str = "",
        base_url: str = "",
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = self._open_store(project_id)
        role_config = configure_provider_role(
            store,
            role,
            provider=provider,
            model=model,
            api_key_ref=api_key_ref,
            base_url=base_url,
            settings=settings,
        )
        return role_config.to_dict()

    def model_role_config(self, project_id: str, role: str) -> dict[str, Any]:
        return get_model_role_config(self._runtime_store(project_id), role).to_dict()

    def global_model_role_config(self, role: str) -> dict[str, Any]:
        return ModelRoleConfig.from_mapping(role, self._global_model_roles().get(role)).to_dict()

    def configure_global_provider_role(
        self,
        role: str,
        *,
        provider: str,
        model: str,
        api_key_ref: str = "",
        base_url: str = "",
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = str(provider or "").strip()
        model = str(model or "").strip()
        if not provider:
            raise ValueError("provider is required.")
        if not model:
            raise ValueError("model is required.")
        adapter = get_provider_adapter(provider)
        if adapter is None:
            raise ValueError(f"Provider adapter is not registered: {provider!r}")
        updates: dict[str, Any] = {"provider": provider, "model": model, "base_url": str(base_url or "").strip()}
        if api_key_ref:
            updates["api_key_ref"] = str(api_key_ref).strip()
        if settings:
            updates["settings"] = dict(settings)
        role_config = ModelRoleConfig.from_mapping(role, updates)
        if adapter.requires_secret and not role_config.api_key_ref:
            raise ValueError(f"Provider {provider!r} requires api_key_ref.")
        validate_model_role_config(role_config, self._read_global_secrets(), require_secret_value=False)
        global_settings = self._read_global_settings()
        roles = global_settings.get("model_roles") if isinstance(global_settings.get("model_roles"), dict) else {}
        global_settings["schema_version"] = 1
        global_settings["model_roles"] = {**roles, role: role_config.to_dict()}
        self._write_global_settings(global_settings)
        return role_config.to_dict()

    def set_global_secret(self, name: str, value: str) -> dict[str, Any]:
        secret_name = validate_secret_name(name)
        if not isinstance(value, str) or not value:
            raise ValueError("secret value cannot be empty.")
        secrets = self._read_global_secrets()
        secrets[secret_name] = value
        self._write_global_secrets(secrets)
        return {"name": secret_name, "has_value": True}

    def copy_project_secret_to_global(self, project_id: str, api_key_ref: str, target_name: str) -> dict[str, Any]:
        if not api_key_ref.startswith(SECRET_REF_PREFIX):
            raise ValueError("api_key_ref must use project_secret.<name>.")
        source_name = validate_secret_name(api_key_ref[len(SECRET_REF_PREFIX) :])
        target_secret_name = validate_secret_name(target_name)
        secrets = self._open_store(project_id).read_secrets()
        value = str(secrets.get(source_name) or "")
        if not value:
            raise ValueError(f"Project secret is missing or empty: {source_name}")
        return self.set_global_secret(target_secret_name, value)

    def set_project_secret(self, project_id: str, name: str, value: str) -> dict[str, Any]:
        return set_project_secret(self._open_store(project_id), name, value)

    def generate_draft(
        self,
        project_id: str,
        *,
        chapter_id: str,
        prompt: str,
        title: str = "",
        system_prompt: str = "",
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        repetition_penalty: float | None = None,
        stream: bool | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = self._runtime_store(project_id)
        service = DraftGenerationService(store)
        result = service.generate_draft(
            DraftGenerationRequest(
                chapter_id=chapter_id,
                title=title,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                min_p=min_p,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                repetition_penalty=repetition_penalty,
                stream=stream,
                stream_callback=stream_callback,
                reasoning_callback=reasoning_callback,
                metadata=metadata or {},
            )
        )
        return result.to_dict()

    def generate_context_draft(
        self,
        project_id: str,
        *,
        chapter_id: str,
        prompt: str,
        title: str = "",
        system_prompt: str = "",
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        repetition_penalty: float | None = None,
        stream: bool | None = None,
        max_context_tokens: int | None = None,
        final_assembly_gate_id: str = "",
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = self._runtime_store(project_id)
        service = DraftGenerationService(store)
        result = service.generate_context_draft(
            DraftGenerationRequest(
                chapter_id=chapter_id,
                title=title,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                min_p=min_p,
                max_tokens=max_tokens,
                presence_penalty=presence_penalty,
                frequency_penalty=frequency_penalty,
                repetition_penalty=repetition_penalty,
                stream=stream,
                stream_callback=stream_callback,
                reasoning_callback=reasoning_callback,
                metadata=metadata or {},
            ),
            max_context_tokens=max_context_tokens,
            final_assembly_gate_id=final_assembly_gate_id,
        )
        return result.to_dict()

    def list_drafts(self, project_id: str) -> list[dict[str, Any]]:
        return DraftGenerationService(self._open_store(project_id)).list_drafts()

    def read_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).read_draft(draft_id)

    def verify_draft_index_entry(self, project_id: str, draft_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).verify_draft_index_entry(draft_id)

    def remove_missing_draft_index_entries(self, project_id: str, draft_ids: list[str]) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).remove_missing_draft_index_entries(draft_ids)

    def delete_chapter_drafts(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).delete_chapter_drafts(chapter_id)

    def update_draft_content(self, project_id: str, draft_id: str, *, text: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).update_draft_content(draft_id, text=text)

    def commit_draft(self, project_id: str, draft_id: str, *, replace_existing: bool = False) -> dict[str, Any]:
        result = DraftGenerationService(self._open_store(project_id)).commit_draft(
            draft_id,
            replace_existing=replace_existing,
        )
        return result.to_dict()

    def review_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        result = DraftReviewService(self._runtime_store(project_id)).review_draft(draft_id)
        return result.to_dict()

    def ai_review_draft(
        self,
        project_id: str,
        draft_id: str,
        *,
        max_context_tokens: int | None = None,
        stream: bool | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
        extra_instruction: str = "",
    ) -> dict[str, Any]:
        result = DraftReviewService(self._runtime_store(project_id)).ai_review_draft(
            draft_id,
            max_context_tokens=max_context_tokens,
            stream=stream,
            stream_callback=stream_callback,
            reasoning_callback=reasoning_callback,
            extra_instruction=extra_instruction,
        )
        return result.to_dict()

    def accept_draft_manually(
        self,
        project_id: str,
        draft_id: str,
        *,
        reason_code: str = "desktop_confirm",
    ) -> dict[str, Any]:
        result = DraftReviewService(self._open_store(project_id)).accept_draft_manually(
            draft_id,
            reason_code=reason_code,
        )
        return result.to_dict()

    def list_reviews(self, project_id: str) -> list[dict[str, Any]]:
        return DraftReviewService(self._open_store(project_id)).list_reviews()

    def read_review(self, project_id: str, review_id: str) -> dict[str, Any]:
        return DraftReviewService(self._open_store(project_id)).read_review(review_id)

    def find_review_for_draft(self, project_id: str, draft_id: str) -> dict[str, Any] | None:
        return DraftReviewService(self._open_store(project_id)).find_review_for_draft(draft_id)

    def find_ai_review_for_draft(self, project_id: str, draft_id: str) -> dict[str, Any] | None:
        return DraftReviewService(self._open_store(project_id)).find_ai_review_for_draft(draft_id)

    def decide_review(self, project_id: str, review_id: str, *, decision: str, reason_code: str = "") -> dict[str, Any]:
        result = DraftReviewService(self._open_store(project_id)).decide_review(
            review_id,
            decision=decision,
            reason_code=reason_code,
        )
        return result.to_dict()

    def create_revision_request(self, project_id: str, review_id: str) -> dict[str, Any]:
        result = RevisionRequestService(self._open_store(project_id)).create_revision_request(review_id)
        return result.to_dict()

    def list_revision_requests(self, project_id: str) -> list[dict[str, Any]]:
        return RevisionRequestService(self._open_store(project_id)).list_revision_requests()

    def read_revision_request(self, project_id: str, revision_request_id: str) -> dict[str, Any]:
        return RevisionRequestService(self._open_store(project_id)).read_revision_request(revision_request_id)

    def generate_revision_draft(self, project_id: str, revision_request_id: str) -> dict[str, Any]:
        result = RevisionRequestService(self._runtime_store(project_id)).generate_revision_draft(revision_request_id)
        return result.to_dict()

    def refine_draft_from_ai_review(
        self,
        project_id: str,
        draft_id: str,
        *,
        review_id: str = "",
        instruction: str = "",
        max_context_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        max_tokens: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        repetition_penalty: float | None = None,
        stream: bool | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        store = self._runtime_store(project_id)
        draft_service = DraftGenerationService(store)
        review_service = DraftReviewService(store)
        draft = draft_service.read_draft(draft_id)
        review = review_service.read_review(review_id) if review_id else review_service.find_ai_review_for_draft(draft_id)
        if not isinstance(review, dict) or not review:
            raise RuntimeError("Current draft has no AI review; local/manual review cannot drive AI refinement.")
        if str(review.get("draft_id") or "") != draft_id or not is_ai_review(review):
            raise RuntimeError("Only an AI review for this exact draft can drive AI refinement.")
        chapter_id = str(draft.get("chapter_id") or "")
        title = str(draft.get("title") or "")
        settings, _ = self._effective_project_generation_settings(store)
        prompting = settings.get("prompting") if isinstance(settings.get("prompting"), dict) else {}
        system_prompt = ai_refinement_system_prompt(str(prompting.get("system_prompt") or ""))
        task_prompt = ai_refinement_task_prompt(
            chapter_id=chapter_id,
            title=title,
            instruction=instruction,
        )
        render = ContextAssemblerService(store).prompt_render_dry_run(
            prompt=task_prompt,
            system_prompt=system_prompt,
            max_context_tokens=max_context_tokens,
            chapter_id=chapter_id,
            include_prompt_text=True,
            include_context_text=True,
        ).to_dict()
        provider_prompt = render_ai_refinement_prompt(render, draft=draft, review=review, instruction=instruction)
        request_role = provider_request_role_or_writer_fallback(store, "reviser")
        safe_stream_callback = stream_sanitizer_callback(stream_callback, reasoning_callback)
        try:
            response = generate_with_provider(
                store,
                ProviderRequest(
                    role=request_role,
                    prompt=provider_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    min_p=min_p,
                    max_tokens=max_tokens,
                    presence_penalty=presence_penalty,
                    frequency_penalty=frequency_penalty,
                    repetition_penalty=repetition_penalty,
                    stream=stream,
                    stream_callback=safe_stream_callback,
                    metadata={
                        "ai_review_refinement": True,
                        "chapter_id": chapter_id,
                        "draft_id": draft_id,
                        "review_id": str(review.get("review_id") or ""),
                        "context_aware_refinement": True,
                    },
                ),
            )
        except Exception as exc:
            ChapterWorkflowService(store).record_error(
                chapter_id,
                title=title,
                stage="ai_review_refine_draft",
                error_type=getattr(exc, "error_type", exc.__class__.__name__),
                message=str(exc),
            )
            raise
        context_stats = render_context_stats(render)
        source_sanitized = sanitize_provider_draft_text(str(draft.get("content") or ""))
        result = draft_service.save_provider_draft_version(
            chapter_id=chapter_id,
            title=title,
            content=response.text,
            provider_role="reviser",
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            request_summary={
                "prompt_chars": len(provider_prompt),
                "system_prompt_chars": len(system_prompt),
                "review_chars": len(str(review.get("comment") or "")),
                "source_draft_chars": len(str(draft.get("content") or "")),
                "provider_source_draft_chars": len(source_sanitized["content"]),
                "provider_request_role": request_role,
                "logical_role": "reviser",
                "metadata_keys": [
                    "ai_review_refinement",
                    "chapter_id",
                    "context_aware_refinement",
                    "draft_id",
                    "review_id",
                ],
                "source_draft_sanitizer": source_sanitized["summary"],
                **context_stats,
            },
            artifact_metadata={
                "revision": {
                    "mode": "ai_review_refinement",
                    "source_draft_id": draft_id,
                    "source_review_id": str(review.get("review_id") or ""),
                    "source_review_type": str(review.get("review_type") or ""),
                    "source_draft_status": str(draft.get("status") or ""),
                    "instruction": str(instruction or "").strip(),
                }
            },
        )
        return result.to_dict()

    def list_revision_candidates(self, project_id: str, revision_request_id: str) -> dict[str, Any]:
        return RevisionCandidateService(self._open_store(project_id)).list_revision_candidates(revision_request_id)

    def compare_revision_candidate(
        self, project_id: str, revision_request_id: str, candidate_draft_id: str
    ) -> dict[str, Any]:
        result = RevisionCandidateService(self._open_store(project_id)).compare_revision_candidate(
            revision_request_id,
            candidate_draft_id,
        )
        return result.to_dict()

    def enqueue_context_updates(self, project_id: str) -> dict[str, Any]:
        return ContextUpdateQueueService(self._open_store(project_id)).enqueue_confirmed_chapters().to_dict()

    def list_context_updates(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return ContextUpdateQueueService(self._open_store(project_id)).list_context_updates(status=status)

    def mark_context_update(
        self, project_id: str, update_id: str, *, status: str, reason_code: str = ""
    ) -> dict[str, Any]:
        return ContextUpdateQueueService(self._open_store(project_id)).mark_context_update(
            update_id,
            status=status,
            reason_code=reason_code,
        )

    def create_context_preview(self, project_id: str, update_id: str) -> dict[str, Any]:
        return ContextUpdatePreviewService(self._open_store(project_id)).create_context_preview(update_id).to_dict()

    def list_context_previews(self, project_id: str) -> list[dict[str, Any]]:
        return ContextUpdatePreviewService(self._open_store(project_id)).list_context_previews()

    def read_context_preview(self, project_id: str, preview_id: str) -> dict[str, Any]:
        return ContextUpdatePreviewService(self._open_store(project_id)).read_context_preview(preview_id)

    def create_formal_context_plan(self, project_id: str, preview_id: str) -> dict[str, Any]:
        return FormalContextPlanService(self._open_store(project_id)).create_formal_context_plan(preview_id).to_dict()

    def list_formal_context_plans(self, project_id: str) -> list[dict[str, Any]]:
        return FormalContextPlanService(self._open_store(project_id)).list_formal_context_plans()

    def read_formal_context_plan(self, project_id: str, plan_id: str) -> dict[str, Any]:
        return FormalContextPlanService(self._open_store(project_id)).read_formal_context_plan(plan_id)

    def context_assembly_dry_run(self, project_id: str, *, max_context_tokens: int | None = None) -> dict[str, Any]:
        return ContextAssemblerService(self._sync_project_generation_settings_for_runtime(project_id)).dry_run(
            max_context_tokens=max_context_tokens,
        ).to_dict()

    def context_package_preview(
        self,
        project_id: str,
        *,
        max_context_tokens: int | None = None,
        chapter_id: str = "",
        include_text: bool = False,
    ) -> dict[str, Any]:
        return ContextAssemblerService(self._sync_project_generation_settings_for_runtime(project_id)).package_preview(
            max_context_tokens=max_context_tokens,
            chapter_id=chapter_id,
            include_text=include_text,
        ).to_dict()

    def prompt_render_dry_run(
        self,
        project_id: str,
        *,
        prompt: str,
        system_prompt: str = "",
        max_context_tokens: int | None = None,
        chapter_id: str = "",
        include_prompt_text: bool = False,
        include_context_text: bool = False,
    ) -> dict[str, Any]:
        return ContextAssemblerService(self._sync_project_generation_settings_for_runtime(project_id)).prompt_render_dry_run(
            prompt=prompt,
            system_prompt=system_prompt,
            max_context_tokens=max_context_tokens,
            chapter_id=chapter_id,
            include_prompt_text=include_prompt_text,
            include_context_text=include_context_text,
        ).to_dict()

    def create_final_assembly_gate(
        self,
        project_id: str,
        *,
        chapter_id: str,
        prompt: str,
        system_prompt: str = "",
        max_context_tokens: int | None = None,
    ) -> dict[str, Any]:
        return FinalAssemblyGateService(self._sync_project_generation_settings_for_runtime(project_id)).create_gate(
            chapter_id=chapter_id,
            prompt=prompt,
            system_prompt=system_prompt,
            max_context_tokens=max_context_tokens,
        ).to_dict()

    def approve_final_assembly_gate(
        self,
        project_id: str,
        gate_id: str,
        *,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return FinalAssemblyGateService(self._open_store(project_id)).approve_gate(
            gate_id,
            reason_code=reason_code,
        ).to_dict()

    def list_final_assembly_gates(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalAssemblyGateService(self._open_store(project_id)).list_gates(status=status)

    def read_final_assembly_gate(self, project_id: str, gate_id: str) -> dict[str, Any]:
        return FinalAssemblyGateService(self._open_store(project_id)).read_gate(gate_id)

    def create_final_provider_runbook(self, project_id: str, gate_id: str) -> dict[str, Any]:
        return FinalProviderRunbookService(self._open_store(project_id)).create_runbook(gate_id).to_dict()

    def list_final_provider_runbooks(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalProviderRunbookService(self._open_store(project_id)).list_runbooks(status=status)

    def read_final_provider_runbook(self, project_id: str, runbook_id: str) -> dict[str, Any]:
        return FinalProviderRunbookService(self._open_store(project_id)).read_runbook(runbook_id)

    def authorize_final_provider_runbook(
        self,
        project_id: str,
        runbook_id: str,
        *,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return FinalProviderAuthorizationService(self._open_store(project_id)).authorize_runbook(
            runbook_id,
            reason_code=reason_code,
        ).to_dict()

    def list_final_provider_authorizations(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalProviderAuthorizationService(self._open_store(project_id)).list_authorizations(status=status)

    def read_final_provider_authorization(self, project_id: str, authorization_id: str) -> dict[str, Any]:
        return FinalProviderAuthorizationService(self._open_store(project_id)).read_authorization(authorization_id)

    def create_final_provider_execution_preflight(self, project_id: str, authorization_id: str) -> dict[str, Any]:
        return FinalProviderExecutionPreflightService(self._open_store(project_id)).create_preflight(
            authorization_id,
        ).to_dict()

    def list_final_provider_execution_preflights(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalProviderExecutionPreflightService(self._open_store(project_id)).list_preflights(status=status)

    def read_final_provider_execution_preflight(self, project_id: str, preflight_id: str) -> dict[str, Any]:
        return FinalProviderExecutionPreflightService(self._open_store(project_id)).read_preflight(preflight_id)

    def attempt_final_provider_execution(self, project_id: str, preflight_id: str) -> dict[str, Any]:
        return FinalProviderExecutionAttemptService(self._open_store(project_id)).create_attempt(preflight_id).to_dict()

    def list_final_provider_execution_attempts(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalProviderExecutionAttemptService(self._open_store(project_id)).list_attempts(status=status)

    def read_final_provider_execution_attempt(self, project_id: str, attempt_id: str) -> dict[str, Any]:
        return FinalProviderExecutionAttemptService(self._open_store(project_id)).read_attempt(attempt_id)

    def create_final_provider_real_execution_readiness(self, project_id: str, attempt_id: str) -> dict[str, Any]:
        return FinalProviderRealExecutionReadinessService(self._open_store(project_id)).create_readiness(
            attempt_id,
        ).to_dict()

    def list_final_provider_real_execution_readiness(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalProviderRealExecutionReadinessService(self._open_store(project_id)).list_readiness(status=status)

    def read_final_provider_real_execution_readiness(self, project_id: str, readiness_id: str) -> dict[str, Any]:
        return FinalProviderRealExecutionReadinessService(self._open_store(project_id)).read_readiness(readiness_id)

    def execute_final_provider_real(
        self,
        project_id: str,
        readiness_id: str,
        *,
        prompt: str,
        system_prompt: str = "",
        title: str = "",
        max_context_tokens: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return FinalProviderRealExecutionService(self._open_store(project_id)).execute(
            readiness_id,
            prompt=prompt,
            system_prompt=system_prompt,
            title=title,
            max_context_tokens=max_context_tokens,
            temperature=temperature,
            max_tokens=max_tokens,
            reason_code=reason_code,
        ).to_dict()

    def list_final_provider_real_executions(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FinalProviderRealExecutionService(self._open_store(project_id)).list_executions(status=status)

    def read_final_provider_real_execution(self, project_id: str, execution_id: str) -> dict[str, Any]:
        return FinalProviderRealExecutionService(self._open_store(project_id)).read_execution(execution_id)

    def postcheck_final_provider_real_execution(self, project_id: str, execution_id: str) -> dict[str, Any]:
        return FinalProviderRealExecutionService(self._open_store(project_id)).postcheck_execution(
            execution_id,
        ).to_dict()

    def enqueue_formal_context_tasks(self, project_id: str, plan_id: str) -> dict[str, Any]:
        return FormalContextTaskQueueService(self._open_store(project_id)).enqueue_plan_tasks(plan_id).to_dict()

    def list_formal_context_tasks(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return FormalContextTaskQueueService(self._open_store(project_id)).list_tasks(status=status)

    def mark_formal_context_task(
        self, project_id: str, task_id: str, *, status: str, reason_code: str = ""
    ) -> dict[str, Any]:
        return FormalContextTaskQueueService(self._open_store(project_id)).mark_task(
            task_id,
            status=status,
            reason_code=reason_code,
        )

    def create_memory_apply_preview(self, project_id: str, *, status: str = "pending") -> dict[str, Any]:
        return MemoryApplyPreviewService(self._open_store(project_id)).create_memory_apply_preview(
            status=status,
        ).to_dict()

    def list_memory_apply_previews(self, project_id: str) -> list[dict[str, Any]]:
        return MemoryApplyPreviewService(self._open_store(project_id)).list_memory_apply_previews()

    def read_memory_apply_preview(self, project_id: str, preview_id: str) -> dict[str, Any]:
        return MemoryApplyPreviewService(self._open_store(project_id)).read_memory_apply_preview(preview_id)

    def commit_memory_apply_preview(self, project_id: str, preview_id: str) -> dict[str, Any]:
        return MemoryApplyPreviewService(self._open_store(project_id)).commit_memory_apply_preview(preview_id).to_dict()

    def list_memory_items(self, project_id: str, *, include_text: bool = False) -> list[dict[str, Any]]:
        return MemoryBankService(self._open_store(project_id)).list_memory_items(include_text=include_text)

    def ensure_main_memory_item(self, project_id: str) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).ensure_main_memory_item()

    def read_memory_item(self, project_id: str, memory_id: str, *, include_text: bool = False) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).read_memory_item(memory_id, include_text=include_text)

    def set_memory_text(
        self,
        project_id: str,
        memory_id: str,
        text: str,
        *,
        source_chapter_ids: list[str] | None = None,
        target_token_budget: int | None = None,
    ) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).set_memory_text(
            memory_id,
            text,
            source_chapter_ids=source_chapter_ids,
            target_token_budget=target_token_budget,
        ).to_dict()

    def set_memory_item_enabled(
        self,
        project_id: str,
        memory_id: str,
        *,
        enabled: bool,
        reason_code: str = "",
        target_token_budget: int | None = None,
    ) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).set_memory_item_enabled(
            memory_id,
            enabled=enabled,
            reason_code=reason_code,
            target_token_budget=target_token_budget,
        ).to_dict()

    def preview_memory_generation_request(
        self,
        project_id: str,
        *,
        current_memory: str,
        chapters: list[dict[str, Any]],
        target_token_budget: int | None = None,
    ) -> dict[str, Any]:
        return MemoryBankService(self._runtime_store(project_id)).preview_memory_generation_request(
            current_memory=current_memory,
            chapters=chapters,
            target_token_budget=target_token_budget,
        )

    def generate_memory_bank_text(
        self,
        project_id: str,
        *,
        current_memory: str,
        chapters: list[dict[str, Any]],
        target_token_budget: int | None = None,
    ) -> dict[str, Any]:
        return MemoryBankService(self._runtime_store(project_id)).generate_memory_text(
            current_memory=current_memory,
            chapters=chapters,
            target_token_budget=target_token_budget,
        ).to_dict()

    def list_confirmed_chapters(self, project_id: str) -> list[dict[str, Any]]:
        return DraftGenerationService(self._open_store(project_id)).list_confirmed_chapters()

    def read_confirmed_chapter(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).read_confirmed_chapter(chapter_id)

    def export_confirmed_chapters_txt(self, project_id: str, output_path: str | Path) -> dict[str, Any]:
        return TxtManuscriptExportService(self._open_store(project_id)).export_confirmed_chapters(output_path).to_dict()

    def audit_project(self, project_id: str) -> dict[str, Any]:
        return audit_project(self._runtime_store(project_id))

    def provider_status(self, project_id: str, role: str) -> dict[str, Any]:
        return provider_status(self._runtime_store(project_id), role).to_dict()

    def provider_dry_run(
        self,
        project_id: str,
        role: str,
        *,
        prompt: str,
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return provider_dry_run(
            self._runtime_store(project_id),
            ProviderRequest(
                role=role,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata or {},
            ),
        ).to_dict()

    def provider_real_test(
        self,
        project_id: str,
        role: str,
        *,
        prompt: str = "Return exactly OK.",
        system_prompt: str = "",
        temperature: float | None = 0,
        max_tokens: int | None = 16,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return provider_real_test(
            self._runtime_store(project_id),
            ProviderRequest(
                role=role,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata or {},
            ),
        ).to_dict()

    def run_provider_smoke_test(
        self,
        project_id: str,
        role: str = "writer",
        *,
        prompt: str = "Return exactly OK.",
        system_prompt: str = "",
        temperature: float | None = 0,
        max_tokens: int | None = 16,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return ProviderSmokeTestService(self._runtime_store(project_id)).run_smoke_test(
            role=role,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            reason_code=reason_code,
        ).to_dict()

    def list_provider_smoke_tests(self, project_id: str, *, status: str = "") -> list[dict[str, Any]]:
        return ProviderSmokeTestService(self._open_store(project_id)).list_smoke_tests(status=status)

    def read_provider_smoke_test(self, project_id: str, smoke_test_id: str) -> dict[str, Any]:
        return ProviderSmokeTestService(self._open_store(project_id)).read_smoke_test(smoke_test_id)

    def chutes_generate_once(
        self,
        project_id: str,
        *,
        chapter_id: str,
        prompt: str,
        title: str = "",
        system_prompt: str = "",
        model: str = "Qwen/Qwen3-32B-TEE",
        base_url: str = "https://llm.chutes.ai/v1",
        secret_name: str = "chutes_key",
        secret_value: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        clear_secret_after_run: bool = True,
    ) -> dict[str, Any]:
        return chutes_generate_once(
            self._open_store(project_id),
            ChutesGenerateOnceRequest(
                chapter_id=chapter_id,
                title=title,
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                base_url=base_url,
                secret_name=secret_name,
                secret_value=secret_value,
                temperature=temperature,
                max_tokens=max_tokens,
                clear_secret_after_run=clear_secret_after_run,
            ),
        )

    def list_provider_adapters(self) -> list[dict[str, Any]]:
        return list_provider_adapters()

    def _global_settings_path(self) -> Path:
        return self.registry.projects_root / GLOBAL_SETTINGS_FILENAME

    def _global_secrets_path(self) -> Path:
        return self.registry.projects_root / GLOBAL_SECRETS_FILENAME

    def _read_global_settings(self) -> dict[str, Any]:
        self.registry.initialize()
        path = self._global_settings_path()
        if not path.exists():
            return default_global_settings()
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default_global_settings()
        value = json.loads(text)
        if not isinstance(value, dict):
            return default_global_settings()
        return deep_merge(default_global_settings(), value)

    def _write_global_settings(self, settings: dict[str, Any]) -> None:
        self.registry.initialize()
        atomic_write_json_file(self._global_settings_path(), settings)

    def _read_global_secrets(self) -> dict[str, Any]:
        self.registry.initialize()
        path = self._global_secrets_path()
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        value = json.loads(text)
        return value if isinstance(value, dict) else {}

    def _write_global_secrets(self, secrets: dict[str, Any]) -> None:
        self.registry.initialize()
        atomic_write_json_file(self._global_secrets_path(), secrets)

    def _global_model_roles(self) -> dict[str, Any]:
        settings = self._read_global_settings()
        roles = settings.get("model_roles") if isinstance(settings.get("model_roles"), dict) else {}
        return roles

    def _runtime_store(self, project_id: str) -> RuntimeModelSettingsStore | ProjectStore:
        store = self._sync_project_generation_settings_for_runtime(project_id)
        global_roles = self._global_model_roles()
        config = store.read_config()
        settings, _ = self._effective_project_generation_settings(store, config=config)
        if model_roles_have_config(global_roles):
            runtime_roles = merged_writer_sampling_settings(global_roles, settings)
            runtime_secrets = self._read_global_secrets()
        else:
            legacy_roles = config.get("model_roles") if isinstance(config.get("model_roles"), dict) else {}
            runtime_roles = merged_writer_sampling_settings(legacy_roles, settings)
            runtime_secrets = store.read_secrets()
        return RuntimeModelSettingsStore(store, model_roles=runtime_roles, secrets=runtime_secrets)

    def _effective_project_generation_settings(
        self,
        store: ProjectStore,
        *,
        config: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        source_config = config if config is not None else store.read_config()
        global_settings = self.global_generation_settings()
        has_override = project_has_generation_settings_override(source_config)
        settings = effective_layered_generation_settings(global_settings, source_config)
        if not has_override and config is None:
            synced = dict(source_config)
            self._apply_generation_settings_to_config(
                synced,
                settings,
                scope=GENERATION_SETTINGS_SCOPE_GLOBAL,
            )
            if synced != source_config:
                store.write_config(synced)
        return settings, has_override

    def _sync_project_generation_settings_for_runtime(self, project_id: str) -> ProjectStore:
        store = self._open_store(project_id)
        store.initialize()
        self._effective_project_generation_settings(store)
        return store

    def _apply_generation_settings_to_config(
        self,
        config: dict[str, Any],
        settings: dict[str, Any],
        *,
        scope: str,
    ) -> None:
        config["generation_settings"] = settings
        config["generation_settings_scope"] = scope
        context_settings = settings.get("context") if isinstance(settings.get("context"), dict) else {}
        context_policy = config.get("context_policy") if isinstance(config.get("context_policy"), dict) else {}
        if isinstance(context_settings.get("max_context_tokens"), int):
            context_policy["max_context_tokens"] = context_settings["max_context_tokens"]
        if isinstance(context_settings.get("recent_confirmed_chapter_count"), int):
            context_policy["recent_confirmed_chapter_count"] = context_settings["recent_confirmed_chapter_count"]
        config["context_policy"] = context_policy
        config["model_roles"] = merged_writer_sampling_settings(config.get("model_roles"), settings)

    def _open_store(self, project_id: str) -> ProjectStore:
        return self.registry.open_project(project_id)


def ai_refinement_system_prompt(project_system_prompt: str = "") -> str:
    project_prompt = str(project_system_prompt or "").strip()
    base_prompt = AI_REFINEMENT_SYSTEM_PROMPT.strip()
    if not project_prompt or project_prompt == base_prompt:
        return base_prompt
    return "\n\n".join(
        [
            base_prompt,
            "【项目通用写作规则】",
            project_prompt,
            "以上通用规则不得覆盖本次 AI 审稿意见；若存在冲突，优先保持既有事实连续性并落实审稿指出的问题。",
        ]
    )


def ai_refinement_task_prompt(*, chapter_id: str, title: str = "", instruction: str = "") -> str:
    heading = f"{chapter_id}"
    if title:
        heading = f"{heading}（{title}）"
    user_instruction = str(instruction or "").strip()
    lines = [
        f"请根据 AI 审稿意见精修当前章节：{heading}。",
        "必须优先解决审稿指出的问题；不要只做泛泛润色，也不要另起炉灶重写成新章节。",
        "保持主线、人物动机、已有设定、前文事实和关键场景连续。",
        "输出必须是修订后的小说正文，不要写分析过程、修改说明、免责声明或 <think>。",
    ]
    if user_instruction:
        lines.append(f"额外精修要求：{user_instruction}")
    return "\n".join(lines)


def render_ai_refinement_prompt(
    render: dict[str, Any],
    *,
    draft: dict[str, Any],
    review: dict[str, Any],
    instruction: str = "",
) -> str:
    context_text = render_context_prompt(render)
    draft_text = sanitize_provider_draft_text(str(draft.get("content") or ""))["content"]
    review_text = str(review.get("comment") or "").strip()
    chapter_id = str(draft.get("chapter_id") or "")
    title = str(draft.get("title") or "")
    version_label = str(draft.get("version_label") or "")
    lines = [
        "【精修任务】",
        "你将根据 AI 审稿意见，把当前草稿改成一个新的修订版。",
        "AI 审稿意见是本次精修的主要执行清单；必须优先落实，不要只做普通续写或表层润色。",
        "只输出小说正文，不要输出修改说明。",
        "",
        "【目标章节】",
        f"章节 ID：{chapter_id}",
        f"标题：{title or chapter_id}",
        f"源草稿版本：{version_label or '-'}",
        "",
        "【上下文与资料】",
        context_text or "无额外上下文。",
        "",
        "【必须落实的 AI 审稿意见】",
        review_text or "（无审稿意见）",
        "",
        "【落实规则】",
        "1. 优先修复上方审稿意见明确指出的问题。",
        "2. 保留未被审稿意见否定的主线、人物关系、信息量和关键场景。",
        "3. 如果某条审稿意见与上下文或草稿事实冲突，用正文方式化解冲突，不要在输出中解释。",
        "",
        "【当前草稿正文】",
        draft_text or "（空草稿）",
    ]
    if str(instruction or "").strip():
        lines.extend(["", "【用户额外要求】", str(instruction or "").strip()])
    lines.extend(
        [
            "",
            "【输出要求】",
            "直接输出精修后的完整章节正文。",
            "正文应体现 AI 审稿意见已被落实，但不要列出修改清单。",
            "不要输出审稿、分析、提纲、说明、免责声明或 <think>。",
        ]
    )
    return "\n".join(lines).strip()


def merged_writer_sampling_settings(model_roles: object, generation_settings: dict[str, Any]) -> dict[str, Any]:
    roles = model_roles if isinstance(model_roles, dict) else {}
    writer = roles.get("writer") if isinstance(roles.get("writer"), dict) else {}
    writer_settings = writer.get("settings") if isinstance(writer.get("settings"), dict) else {}
    sampling = generation_settings.get("sampling") if isinstance(generation_settings.get("sampling"), dict) else {}
    mapped = {
        key: sampling.get(key)
        for key in (
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "max_tokens",
            "presence_penalty",
            "frequency_penalty",
            "repetition_penalty",
            "stream",
        )
        if key in sampling
    }
    return {
        **roles,
        "writer": {
            **writer,
            "settings": {
                **writer_settings,
                **mapped,
            },
        },
    }


def model_roles_have_config(model_roles: object) -> bool:
    roles = model_roles if isinstance(model_roles, dict) else {}
    for role in ("writer", "scorer", "reviser"):
        config = roles.get(role)
        if not isinstance(config, dict):
            continue
        if str(config.get("provider") or "").strip() and str(config.get("model") or "").strip():
            return True
    return False
