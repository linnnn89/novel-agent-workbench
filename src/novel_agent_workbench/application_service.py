from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .drafts import DraftGenerationRequest, DraftGenerationService
from .project_state import public_project_state
from .providers import set_model_role_config
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

    def configure_mock_writer(self, project_id: str, *, model: str = "mock-writer") -> dict[str, Any]:
        store = self._open_store(project_id)
        role_config = set_model_role_config(store, "writer", {"provider": "mock", "model": model})
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

    def list_confirmed_chapters(self, project_id: str) -> list[dict[str, Any]]:
        return DraftGenerationService(self._open_store(project_id)).list_confirmed_chapters()

    def read_confirmed_chapter(self, project_id: str, chapter_id: str) -> dict[str, Any]:
        return DraftGenerationService(self._open_store(project_id)).read_confirmed_chapter(chapter_id)

    def _open_store(self, project_id: str) -> ProjectStore:
        return self.registry.open_project(project_id)
