from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audit import audit_project
from .context_previews import ContextUpdatePreviewService
from .chapters import ChapterWorkflowService
from .context_assembler import ContextAssemblerService
from .context_queue import ContextUpdateQueueService
from .drafts import DraftGenerationRequest, DraftGenerationService
from .formal_context import FormalContextPlanService
from .formal_context_tasks import FormalContextTaskQueueService
from .memory_apply_preview import MemoryApplyPreviewService
from .memory_bank import MemoryBankService
from .project_state import public_project_state
from .providers import (
    ProviderRequest,
    configure_provider_role,
    list_provider_adapters,
    provider_dry_run,
    provider_real_test,
    provider_status,
    set_real_generation_enabled,
    set_model_role_config,
    set_project_secret,
)
from .runbooks import ChutesGenerateOnceRequest, chutes_generate_once
from .reviews import DraftReviewService
from .revision_candidates import RevisionCandidateService
from .revisions import RevisionRequestService
from .storage import ProjectRegistry, ProjectStore


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

    def project_state(self, project_id: str) -> dict[str, Any]:
        return public_project_state(self._open_store(project_id))

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
    ) -> dict[str, Any]:
        store = self._open_store(project_id)
        role_config = configure_provider_role(
            store,
            role,
            provider=provider,
            model=model,
            api_key_ref=api_key_ref,
            base_url=base_url,
        )
        return role_config.to_dict()

    def set_project_secret(self, project_id: str, name: str, value: str) -> dict[str, Any]:
        return set_project_secret(self._open_store(project_id), name, value)

    def enable_real_provider(self, project_id: str, role: str, *, provider: str) -> dict[str, Any]:
        role_config = set_real_generation_enabled(self._open_store(project_id), role, provider=provider, enabled=True)
        return role_config.to_dict()

    def disable_real_provider(self, project_id: str, role: str, *, provider: str = "chutes_openai") -> dict[str, Any]:
        role_config = set_real_generation_enabled(self._open_store(project_id), role, provider=provider, enabled=False)
        return role_config.to_dict()

    def generate_draft(
        self,
        project_id: str,
        *,
        chapter_id: str,
        prompt: str,
        title: str = "",
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = self._open_store(project_id)
        service = DraftGenerationService(store)
        result = service.generate_draft(
            DraftGenerationRequest(
                chapter_id=chapter_id,
                title=title,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata or {},
            )
        )
        return result.to_dict()

    def list_drafts(self, project_id: str) -> list[dict[str, Any]]:
        return DraftGenerationService(self._open_store(project_id)).list_drafts()

    def read_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).read_draft(draft_id)

    def commit_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        result = DraftGenerationService(self._open_store(project_id)).commit_draft(draft_id)
        return result.to_dict()

    def review_draft(self, project_id: str, draft_id: str) -> dict[str, Any]:
        result = DraftReviewService(self._open_store(project_id)).review_draft(draft_id)
        return result.to_dict()

    def list_reviews(self, project_id: str) -> list[dict[str, Any]]:
        return DraftReviewService(self._open_store(project_id)).list_reviews()

    def read_review(self, project_id: str, review_id: str) -> dict[str, Any]:
        return DraftReviewService(self._open_store(project_id)).read_review(review_id)

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
        result = RevisionRequestService(self._open_store(project_id)).generate_revision_draft(revision_request_id)
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
        return ContextAssemblerService(self._open_store(project_id)).dry_run(
            max_context_tokens=max_context_tokens,
        ).to_dict()

    def context_package_preview(
        self,
        project_id: str,
        *,
        max_context_tokens: int | None = None,
        include_text: bool = False,
    ) -> dict[str, Any]:
        return ContextAssemblerService(self._open_store(project_id)).package_preview(
            max_context_tokens=max_context_tokens,
            include_text=include_text,
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

    def read_memory_item(self, project_id: str, memory_id: str, *, include_text: bool = False) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).read_memory_item(memory_id, include_text=include_text)

    def set_memory_text(self, project_id: str, memory_id: str, text: str) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).set_memory_text(memory_id, text).to_dict()

    def set_memory_item_enabled(
        self,
        project_id: str,
        memory_id: str,
        *,
        enabled: bool,
        reason_code: str = "",
    ) -> dict[str, Any]:
        return MemoryBankService(self._open_store(project_id)).set_memory_item_enabled(
            memory_id,
            enabled=enabled,
            reason_code=reason_code,
        ).to_dict()

    def list_confirmed_chapters(self, project_id: str) -> list[dict[str, Any]]:
        return DraftGenerationService(self._open_store(project_id)).list_confirmed_chapters()

    def read_confirmed_chapter(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).read_confirmed_chapter(chapter_id)

    def audit_project(self, project_id: str) -> dict[str, Any]:
        return audit_project(self._open_store(project_id))

    def provider_status(self, project_id: str, role: str) -> dict[str, Any]:
        return provider_status(self._open_store(project_id), role).to_dict()

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
            self._open_store(project_id),
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
            self._open_store(project_id),
            ProviderRequest(
                role=role,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata or {},
            ),
        ).to_dict()

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
        allow_network: bool = False,
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
                allow_network=allow_network,
                clear_secret_after_run=clear_secret_after_run,
            ),
        )

    def list_provider_adapters(self) -> list[dict[str, Any]]:
        return list_provider_adapters()

    def _open_store(self, project_id: str) -> ProjectStore:
        return self.registry.open_project(project_id)
