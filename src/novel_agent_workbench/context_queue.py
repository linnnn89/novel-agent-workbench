from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from .drafts import DraftGenerationService
from .reviews import validate_reason_code
from .storage import ProjectStore, utc_stamp


CONTEXT_UPDATE_QUEUE_FILENAME = "context_update_queue.json"
CONTEXT_UPDATE_STATUSES = {"pending", "acknowledged", "skipped"}


class ContextUpdateQueueError(RuntimeError):
    """Raised when a context update queue operation is invalid."""


@dataclass(frozen=True, slots=True)
class ContextUpdateQueueResult:
    created_count: int
    total_count: int
    items: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextUpdateQueueService:
    """Metadata-only queue between confirmed chapters and future context updates."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def queue_path(self):
        return self.store.data_dir / CONTEXT_UPDATE_QUEUE_FILENAME

    def enqueue_confirmed_chapters(self) -> ContextUpdateQueueResult:
        self.store.initialize()
        with self.store.lock():
            queue = self._read_queue()
            items = queue["items"]
            known_chapters = {str(item.get("chapter_id") or "") for item in items if item.get("chapter_id")}
            created: list[dict[str, Any]] = []
            draft_service = DraftGenerationService(self.store)
            for confirmed in draft_service.list_confirmed_chapters():
                chapter_id = str(confirmed.get("chapter_id") or "")
                if not chapter_id or chapter_id in known_chapters:
                    continue
                artifact = draft_service.read_confirmed_chapter(chapter_id)
                content = str(artifact.get("content") or "")
                created_at = utc_stamp()
                item = {
                    "update_id": new_context_update_id(),
                    "chapter_id": chapter_id,
                    "title": str(confirmed.get("title") or ""),
                    "source_draft_id": str(confirmed.get("source_draft_id") or ""),
                    "confirmed_chapter_id": chapter_id,
                    "status": "pending",
                    "created_at": created_at,
                    "updated_at": created_at,
                    "source": "confirmed_chapter",
                    "text_stats": {
                        "char_count": len(content),
                        "word_count": len(content.split()),
                        "line_count": count_lines(content),
                    },
                    "targets": {
                        "memory_bank": "manual_pending",
                        "rag": "manual_pending",
                        "export": "not_started",
                    },
                }
                items.append(item)
                created.append(item)
                known_chapters.add(chapter_id)
            self._write_queue(items)
            return ContextUpdateQueueResult(created_count=len(created), total_count=len(items), items=created)

    def list_context_updates(self, *, status: str = "") -> list[dict[str, Any]]:
        items = self._read_queue()["items"]
        if not status:
            return items
        validate_context_update_status(status)
        return [item for item in items if item.get("status") == status]

    def mark_context_update(self, update_id: str, *, status: str, reason_code: str = "") -> dict[str, Any]:
        validate_context_update_status(status)
        if reason_code:
            validate_reason_code(reason_code)
        self.store.initialize()
        with self.store.lock():
            queue = self._read_queue()
            updated_items: list[dict[str, Any]] = []
            result: dict[str, Any] | None = None
            for item in queue["items"]:
                if item.get("update_id") == update_id:
                    item = {
                        **item,
                        "status": status,
                        "reason_code": reason_code,
                        "updated_at": utc_stamp(),
                    }
                    result = item
                updated_items.append(item)
            if result is None:
                raise ContextUpdateQueueError(f"Context update not found: {update_id}")
            self._write_queue(updated_items)
            return result

    def _read_queue(self) -> dict[str, Any]:
        queue = self.store.read_json(self.queue_path, default={"schema_version": 1, "items": []})
        if not isinstance(queue, dict):
            return {"schema_version": 1, "items": []}
        items = queue.get("items")
        if not isinstance(items, list):
            items = []
        return {"schema_version": 1, "items": [item for item in items if isinstance(item, dict)]}

    def _write_queue(self, items: list[dict[str, Any]]) -> None:
        self.store.write_json(self.queue_path, {"schema_version": 1, "items": items})


def validate_context_update_status(status: str) -> None:
    if status not in CONTEXT_UPDATE_STATUSES:
        raise ContextUpdateQueueError(f"Invalid context update status: {status!r}")


def new_context_update_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"


def count_lines(value: str) -> int:
    if not value:
        return 0
    return len(value.splitlines()) or 1
