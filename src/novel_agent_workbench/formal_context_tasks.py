from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

from .formal_context import FormalContextPlanService
from .reviews import validate_reason_code
from .storage import ProjectStore, utc_stamp


FORMAL_CONTEXT_TASK_QUEUE_FILENAME = "formal_context_task_queue.json"
FORMAL_CONTEXT_TASK_STATUSES = {"pending", "acknowledged", "skipped"}


class FormalContextTaskQueueError(RuntimeError):
    """Raised when a formal context task queue operation is invalid."""


@dataclass(frozen=True, slots=True)
class FormalContextTaskQueueResult:
    created_count: int
    total_count: int
    items: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FormalContextTaskQueueService:
    """Metadata-only manual task queue for future formal context application."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def queue_path(self):
        return self.store.data_dir / FORMAL_CONTEXT_TASK_QUEUE_FILENAME

    def enqueue_plan_tasks(self, plan_id: str) -> FormalContextTaskQueueResult:
        self.store.initialize()
        with self.store.lock():
            plan = FormalContextPlanService(self.store).read_formal_context_plan(plan_id)
            queue = self._read_queue()
            items = queue["items"]
            known = {
                (str(item.get("plan_id") or ""), str(item.get("category_id") or ""))
                for item in items
                if item.get("plan_id") and item.get("category_id")
            }
            created: list[dict[str, Any]] = []
            categories = plan.get("categories") if isinstance(plan.get("categories"), list) else []
            for category in categories:
                if not isinstance(category, dict):
                    continue
                category_id = str(category.get("category_id") or "")
                if not category_id or (plan_id, category_id) in known:
                    continue
                created_at = utc_stamp()
                item = {
                    "task_id": new_formal_context_task_id(),
                    "plan_id": plan_id,
                    "preview_id": str(plan.get("preview_id") or ""),
                    "update_id": str(plan.get("update_id") or ""),
                    "chapter_id": str(plan.get("chapter_id") or ""),
                    "title": str(plan.get("title") or ""),
                    "category_id": category_id,
                    "priority": category.get("priority"),
                    "target": str(category.get("target") or "memory_bank"),
                    "memory_weight": category.get("memory_weight"),
                    "recommendation": str(category.get("recommendation") or ""),
                    "status": "pending",
                    "created_at": created_at,
                    "updated_at": created_at,
                    "source": "formal_context_plan",
                    "safety": {
                        "prompt_copied": False,
                        "text_copied": False,
                        "secret_copied": False,
                        "provider_called": False,
                        "memory_bank_written": False,
                        "rag_written": False,
                        "export_written": False,
                    },
                }
                items.append(item)
                created.append(item)
                known.add((plan_id, category_id))
            self._write_queue(items)
            return FormalContextTaskQueueResult(created_count=len(created), total_count=len(items), items=created)

    def list_tasks(self, *, status: str = "") -> list[dict[str, Any]]:
        items = self._read_queue()["items"]
        if not status:
            return items
        validate_formal_context_task_status(status)
        return [item for item in items if item.get("status") == status]

    def mark_task(self, task_id: str, *, status: str, reason_code: str = "") -> dict[str, Any]:
        validate_formal_context_task_status(status)
        if reason_code:
            validate_reason_code(reason_code)
        self.store.initialize()
        with self.store.lock():
            queue = self._read_queue()
            updated_items: list[dict[str, Any]] = []
            result: dict[str, Any] | None = None
            for item in queue["items"]:
                if item.get("task_id") == task_id:
                    item = {
                        **item,
                        "status": status,
                        "reason_code": reason_code,
                        "updated_at": utc_stamp(),
                    }
                    result = item
                updated_items.append(item)
            if result is None:
                raise FormalContextTaskQueueError(f"Formal context task not found: {task_id}")
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


def validate_formal_context_task_status(status: str) -> None:
    if status not in FORMAL_CONTEXT_TASK_STATUSES:
        raise FormalContextTaskQueueError(f"Invalid formal context task status: {status!r}")


def new_formal_context_task_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"
