from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .formal_context_tasks import FormalContextTaskQueueService
from .storage import ProjectStore, utc_stamp


MEMORY_APPLY_PREVIEWS_DIRNAME = "memory_apply_previews"
MEMORY_APPLY_PREVIEWS_INDEX_FILENAME = "memory_apply_previews_index.json"


class MemoryApplyPreviewError(RuntimeError):
    """Raised when a Memory Bank apply preview cannot be created safely."""


@dataclass(frozen=True, slots=True)
class MemoryApplyPreviewResult:
    preview_id: str
    status: str
    task_count: int
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MemoryApplyCommitResult:
    preview_id: str
    status: str
    created_count: int
    skipped_count: int
    checkpoint: dict[str, Any]
    committed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryApplyPreviewService:
    """Creates metadata-only previews before any Memory Bank write exists."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def previews_dir(self) -> Path:
        return self.store.data_dir / MEMORY_APPLY_PREVIEWS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / MEMORY_APPLY_PREVIEWS_INDEX_FILENAME

    def create_memory_apply_preview(self, *, status: str = "pending") -> MemoryApplyPreviewResult:
        self.store.initialize()
        with self.store.lock():
            if status not in {"pending", "acknowledged", "skipped", ""}:
                raise MemoryApplyPreviewError(f"Invalid task status filter: {status!r}")
            task_service = FormalContextTaskQueueService(self.store)
            tasks = task_service.list_tasks(status=status) if status else task_service.list_tasks()
            created_at = utc_stamp()
            preview_id = new_memory_apply_preview_id()
            preview_path = self.previews_dir / f"{preview_id}.json"
            config = self.store.read_config()
            context_policy = config.get("context_policy") if isinstance(config, dict) else {}
            world_book_enabled = bool(context_policy.get("world_book_enabled")) if isinstance(context_policy, dict) else False
            items = [preview_item_from_task(task, world_book_enabled=world_book_enabled) for task in tasks]
            artifact = {
                "schema_version": 1,
                "preview_id": preview_id,
                "status": "preview_ready",
                "created_at": created_at,
                "source": "formal_context_task_queue",
                "task_status_filter": status,
                "task_count": len(items),
                "world_book_enabled": world_book_enabled,
                "items": items,
                "summary": {
                    "candidate_count": len(items),
                    "would_write_memory_bank": False,
                    "requires_manual_text_entry": True,
                    "provider_called": False,
                },
                "safety": {
                    "prompt_copied": False,
                    "text_copied": False,
                    "secret_copied": False,
                    "provider_called": False,
                    "memory_bank_written": False,
                    "world_book_written": False,
                    "rag_written": False,
                    "export_written": False,
                },
                "recommendation": "manual_apply_preview_only",
            }
            self.store.write_json(preview_path, artifact)
            self._append_index_entry(
                {
                    "preview_id": preview_id,
                    "status": artifact["status"],
                    "created_at": created_at,
                    "task_status_filter": status,
                    "task_count": len(items),
                    "path": str(preview_path.relative_to(self.store.root)),
                    "recommendation": artifact["recommendation"],
                }
            )
            return MemoryApplyPreviewResult(
                preview_id=preview_id,
                status="preview_ready",
                task_count=len(items),
                path=str(preview_path),
                created_at=created_at,
            )

    def list_memory_apply_previews(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "previews": []})
        if not isinstance(index, dict):
            return []
        items = index.get("previews")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_memory_apply_preview(self, preview_id: str) -> dict[str, Any]:
        for item in self.list_memory_apply_previews():
            if item.get("preview_id") != preview_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise MemoryApplyPreviewError(f"Memory apply preview index entry has no path: {preview_id}")
            value = self.store.read_json(path, default=None)
            if not isinstance(value, dict):
                raise MemoryApplyPreviewError(f"Memory apply preview artifact is missing or invalid: {preview_id}")
            return value
        raise MemoryApplyPreviewError(f"Memory apply preview not found: {preview_id}")

    def commit_memory_apply_preview(self, preview_id: str) -> MemoryApplyCommitResult:
        self.store.initialize()
        with self.store.lock():
            preview = self.read_memory_apply_preview(preview_id)
            if str(preview.get("status") or "") != "preview_ready":
                raise MemoryApplyPreviewError(f"Memory apply preview is not ready: {preview_id}")
            items = preview.get("items") if isinstance(preview.get("items"), list) else []
            checkpoint = self.store.create_checkpoint(label="pre_memory_apply")
            memory_bank = self._read_memory_bank()
            existing_keys = {
                memory_item_key(item)
                for item in memory_bank["items"]
                if isinstance(item, dict) and memory_item_key(item)
            }
            created: list[dict[str, Any]] = []
            skipped_count = 0
            committed_at = utc_stamp()
            for item in items:
                if not isinstance(item, dict):
                    continue
                entry = memory_entry_from_preview_item(item, preview_id=preview_id, created_at=committed_at)
                key = memory_item_key(entry)
                if not key or key in existing_keys:
                    skipped_count += 1
                    continue
                memory_bank["items"].append(entry)
                existing_keys.add(key)
                created.append(entry)
            memory_bank["enabled"] = True
            memory_bank["updated_at"] = committed_at
            memory_bank["last_apply_preview_id"] = preview_id
            self.store.write_json(self.store.data_file_path("memory_bank.json"), memory_bank)
            return MemoryApplyCommitResult(
                preview_id=preview_id,
                status="committed" if created else "no_new_items",
                created_count=len(created),
                skipped_count=skipped_count,
                checkpoint=checkpoint,
                committed_at=committed_at,
            )

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "previews": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "previews": []}
        items = index.get("previews") if isinstance(index.get("previews"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "previews": items})

    def _read_memory_bank(self) -> dict[str, Any]:
        value = self.store.read_json(
            self.store.data_file_path("memory_bank.json"),
            default={"schema_version": 1, "enabled": False, "updated_to_chapter": 0, "items": []},
        )
        if not isinstance(value, dict):
            value = {"schema_version": 1, "enabled": False, "updated_to_chapter": 0, "items": []}
        items = value.get("items")
        if not isinstance(items, list):
            items = []
        return {
            **value,
            "schema_version": int(value.get("schema_version") or 1),
            "items": [item for item in items if isinstance(item, dict)],
        }


def preview_item_from_task(task: dict[str, Any], *, world_book_enabled: bool) -> dict[str, Any]:
    category_id = str(task.get("category_id") or "")
    return {
        "task_id": str(task.get("task_id") or ""),
        "plan_id": str(task.get("plan_id") or ""),
        "preview_id": str(task.get("preview_id") or ""),
        "update_id": str(task.get("update_id") or ""),
        "chapter_id": str(task.get("chapter_id") or ""),
        "title": str(task.get("title") or ""),
        "category_id": category_id,
        "priority": task.get("priority"),
        "target": str(task.get("target") or "memory_bank"),
        "memory_weight": task.get("memory_weight"),
        "source_task_status": str(task.get("status") or ""),
        "proposed_action": "manual_memory_bank_candidate",
        "duplicate_risk": duplicate_risk(category_id, world_book_enabled=world_book_enabled),
        "recommendation": str(task.get("recommendation") or "manual_apply_required"),
        "safety": {
            "prompt_copied": False,
            "text_copied": False,
            "secret_copied": False,
            "provider_called": False,
            "memory_bank_written": False,
            "world_book_written": False,
        },
    }


def duplicate_risk(category_id: str, *, world_book_enabled: bool) -> str:
    if category_id == "world_building" and world_book_enabled:
        return "world_book_overlap_review_required"
    return "not_detected_in_metadata"


def new_memory_apply_preview_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"


def memory_entry_from_preview_item(item: dict[str, Any], *, preview_id: str, created_at: str) -> dict[str, Any]:
    category_id = str(item.get("category_id") or "")
    chapter_id = str(item.get("chapter_id") or "")
    task_id = str(item.get("task_id") or "")
    return {
        "memory_id": f"{preview_id}_{task_id}".strip("_"),
        "schema_version": 1,
        "entry_type": "formal_context_placeholder",
        "status": "manual_text_required",
        "source": "memory_apply_preview",
        "source_preview_id": preview_id,
        "source_task_id": task_id,
        "chapter_id": chapter_id,
        "title": str(item.get("title") or ""),
        "category_id": category_id,
        "priority": item.get("priority"),
        "target": str(item.get("target") or "memory_bank"),
        "memory_weight": item.get("memory_weight"),
        "duplicate_risk": str(item.get("duplicate_risk") or ""),
        "text": "",
        "text_status": "not_extracted",
        "created_at": created_at,
        "updated_at": created_at,
        "safety": {
            "prompt_copied": False,
            "text_copied": False,
            "secret_copied": False,
            "provider_called": False,
        },
    }


def memory_item_key(item: dict[str, Any]) -> str:
    source_task_id = str(item.get("source_task_id") or "")
    category_id = str(item.get("category_id") or "")
    chapter_id = str(item.get("chapter_id") or "")
    if source_task_id:
        return f"task:{source_task_id}"
    if chapter_id and category_id:
        return f"chapter_category:{chapter_id}:{category_id}"
    return ""
