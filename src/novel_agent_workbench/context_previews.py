from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .context_queue import ContextUpdateQueueService
from .drafts import DraftGenerationService
from .storage import ProjectStore, safe_filename, utc_stamp


CONTEXT_UPDATE_PREVIEWS_DIRNAME = "context_update_previews"
CONTEXT_UPDATE_PREVIEWS_INDEX_FILENAME = "context_update_previews_index.json"


class ContextUpdatePreviewError(RuntimeError):
    """Raised when a context update preview cannot be created safely."""


@dataclass(frozen=True, slots=True)
class ContextUpdatePreviewResult:
    preview_id: str
    update_id: str
    chapter_id: str
    status: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextUpdatePreviewService:
    """Creates metadata-only preview artifacts for queued context work."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def previews_dir(self) -> Path:
        return self.store.data_dir / CONTEXT_UPDATE_PREVIEWS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / CONTEXT_UPDATE_PREVIEWS_INDEX_FILENAME

    def create_context_preview(self, update_id: str) -> ContextUpdatePreviewResult:
        self.store.initialize()
        with self.store.lock():
            update = self._queue_item(update_id)
            if str(update.get("status") or "") == "skipped":
                raise ContextUpdatePreviewError(f"Context update is skipped: {update_id}")
            if self._find_preview_by_update_id(update_id) is not None:
                raise ContextUpdatePreviewError(f"Context update already has a preview: {update_id}")
            chapter_id = str(update.get("chapter_id") or "")
            if not chapter_id:
                raise ContextUpdatePreviewError(f"Context update has no chapter_id: {update_id}")
            confirmed = DraftGenerationService(self.store).read_confirmed_chapter(chapter_id)
            text = str(confirmed.get("content") or "")
            created_at = utc_stamp()
            preview_id = new_context_preview_id()
            preview_path = self.previews_dir / f"{safe_filename(chapter_id)}__{preview_id}.json"
            artifact = {
                "schema_version": 1,
                "preview_id": preview_id,
                "update_id": update_id,
                "chapter_id": chapter_id,
                "title": str(update.get("title") or confirmed.get("title") or ""),
                "source_draft_id": str(update.get("source_draft_id") or confirmed.get("source_draft_id") or ""),
                "confirmed_chapter_id": str(update.get("confirmed_chapter_id") or chapter_id),
                "status": "preview_ready",
                "created_at": created_at,
                "source": "context_update_queue",
                "text_stats": {
                    "char_count": len(text),
                    "word_count": len(text.split()),
                    "line_count": count_lines(text),
                },
                "target_plan": {
                    "memory_bank": {"operation": "manual_extract_required", "state": "not_started"},
                    "rag": {"operation": "manual_index_plan_required", "state": "not_started"},
                    "export": {"operation": "not_in_scope", "state": "not_started"},
                },
                "safety": {
                    "prompt_copied": False,
                    "text_copied": False,
                    "secret_copied": False,
                    "provider_called": False,
                },
                "recommendation": "manual_review_required",
            }
            self.store.write_json(preview_path, artifact)
            self._append_index_entry(
                {
                    "preview_id": preview_id,
                    "update_id": update_id,
                    "chapter_id": chapter_id,
                    "title": artifact["title"],
                    "source_draft_id": artifact["source_draft_id"],
                    "confirmed_chapter_id": artifact["confirmed_chapter_id"],
                    "status": artifact["status"],
                    "created_at": created_at,
                    "path": str(preview_path.relative_to(self.store.root)),
                    "recommendation": artifact["recommendation"],
                }
            )
            return ContextUpdatePreviewResult(
                preview_id=preview_id,
                update_id=update_id,
                chapter_id=chapter_id,
                status="preview_ready",
                path=str(preview_path),
                created_at=created_at,
            )

    def list_context_previews(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "previews": []})
        if not isinstance(index, dict):
            return []
        items = index.get("previews")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_context_preview(self, preview_id: str) -> dict[str, Any]:
        for item in self.list_context_previews():
            if item.get("preview_id") != preview_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise ContextUpdatePreviewError(f"Context preview index entry has no path: {preview_id}")
            value = self.store.read_json(path, default=None)
            if not isinstance(value, dict):
                raise ContextUpdatePreviewError(f"Context preview artifact is missing or invalid: {preview_id}")
            return value
        raise ContextUpdatePreviewError(f"Context preview not found: {preview_id}")

    def _queue_item(self, update_id: str) -> dict[str, Any]:
        for item in ContextUpdateQueueService(self.store).list_context_updates():
            if item.get("update_id") == update_id:
                return item
        raise ContextUpdatePreviewError(f"Context update not found: {update_id}")

    def _find_preview_by_update_id(self, update_id: str) -> dict[str, Any] | None:
        for item in self.list_context_previews():
            if item.get("update_id") == update_id:
                return item
        return None

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "previews": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "previews": []}
        items = index.get("previews") if isinstance(index.get("previews"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "previews": items})


def new_context_preview_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"


def count_lines(value: str) -> int:
    if not value:
        return 0
    return len(value.splitlines()) or 1
