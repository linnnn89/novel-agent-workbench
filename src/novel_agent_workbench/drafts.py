from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from .providers import ProviderRequest, generate_with_provider
from .storage import ProjectStore, safe_filename, utc_stamp


DRAFTS_DIRNAME = "drafts"
DRAFTS_INDEX_FILENAME = "drafts_index.json"


class DraftGenerationError(RuntimeError):
    """Raised when draft generation cannot safely produce a draft."""


@dataclass(frozen=True, slots=True)
class DraftGenerationRequest:
    chapter_id: str
    prompt: str
    title: str = ""
    system_prompt: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chapter_id.strip():
            raise DraftGenerationError("chapter_id cannot be empty.")
        if not self.prompt.strip():
            raise DraftGenerationError("prompt cannot be empty.")

    def to_provider_request(self) -> ProviderRequest:
        metadata = {
            **self.metadata,
            "chapter_id": self.chapter_id,
            "draft_generation": True,
        }
        return ProviderRequest(
            role="writer",
            prompt=self.prompt,
            system_prompt=self.system_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DraftGenerationResult:
    draft_id: str
    chapter_id: str
    title: str
    path: str
    provider: str
    model: str
    usage: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DraftGenerationService:
    """Backend-only service that writes provider output as draft artifacts."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def drafts_dir(self) -> Path:
        return self.store.data_dir / DRAFTS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / DRAFTS_INDEX_FILENAME

    def generate_draft(self, request: DraftGenerationRequest) -> DraftGenerationResult:
        self.store.initialize()
        with self.store.lock():
            response = generate_with_provider(self.store, request.to_provider_request())
            draft_id = new_draft_id()
            created_at = utc_stamp()
            title = request.title.strip()
            draft_path = self.drafts_dir / f"{safe_filename(request.chapter_id)}__{draft_id}.json"
            artifact = {
                "schema_version": 1,
                "status": "draft",
                "draft_id": draft_id,
                "chapter_id": request.chapter_id,
                "title": title,
                "created_at": created_at,
                "content": response.text,
                "provider": {
                    "role": "writer",
                    "provider": response.provider,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                },
                "request_summary": {
                    "prompt_chars": len(request.prompt),
                    "system_prompt_chars": len(request.system_prompt or ""),
                    "metadata_keys": sorted(str(key) for key in request.metadata),
                },
            }
            self.store.write_json(draft_path, artifact)
            self._append_index_entry(
                {
                    "draft_id": draft_id,
                    "chapter_id": request.chapter_id,
                    "title": title,
                    "created_at": created_at,
                    "status": "draft",
                    "path": str(draft_path.relative_to(self.store.root)),
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage,
                }
            )
            return DraftGenerationResult(
                draft_id=draft_id,
                chapter_id=request.chapter_id,
                title=title,
                path=str(draft_path),
                provider=response.provider,
                model=response.model,
                usage=response.usage,
            )

    def list_drafts(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        if not isinstance(index, dict):
            return []
        drafts = index.get("drafts")
        if not isinstance(drafts, list):
            return []
        return [item for item in drafts if isinstance(item, dict)]

    def read_draft(self, draft_id: str) -> dict[str, Any]:
        for item in self.list_drafts():
            if item.get("draft_id") != draft_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise DraftGenerationError(f"Draft index entry has no path: {draft_id}")
            draft = self.store.read_json(path, default=None)
            if not isinstance(draft, dict):
                raise DraftGenerationError(f"Draft artifact is missing or invalid: {draft_id}")
            return draft
        raise DraftGenerationError(f"Draft not found: {draft_id}")

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "drafts": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "drafts": []}
        drafts = index.get("drafts") if isinstance(index.get("drafts"), list) else []
        drafts.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "drafts": drafts})


def new_draft_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"
