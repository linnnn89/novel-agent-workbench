from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import FORMAL_CONTEXT_PRIORITY_ORDER
from .context_previews import ContextUpdatePreviewService, context_priority_order
from .storage import ProjectStore, safe_filename, utc_stamp


FORMAL_CONTEXT_PLANS_DIRNAME = "formal_context_plans"
FORMAL_CONTEXT_PLANS_INDEX_FILENAME = "formal_context_plans_index.json"


class FormalContextPlanError(RuntimeError):
    """Raised when a formal context extraction plan cannot be created safely."""


@dataclass(frozen=True, slots=True)
class FormalContextPlanResult:
    plan_id: str
    preview_id: str
    chapter_id: str
    status: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FormalContextPlanService:
    """Creates metadata-only formal context extraction plans from context previews."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def plans_dir(self) -> Path:
        return self.store.data_dir / FORMAL_CONTEXT_PLANS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FORMAL_CONTEXT_PLANS_INDEX_FILENAME

    def create_formal_context_plan(self, preview_id: str) -> FormalContextPlanResult:
        self.store.initialize()
        with self.store.lock():
            preview = ContextUpdatePreviewService(self.store).read_context_preview(preview_id)
            if str(preview.get("status") or "") != "preview_ready":
                raise FormalContextPlanError(f"Context preview is not ready: {preview_id}")
            if self._find_plan_by_preview_id(preview_id) is not None:
                raise FormalContextPlanError(f"Context preview already has a formal context plan: {preview_id}")
            chapter_id = str(preview.get("chapter_id") or "")
            if not chapter_id:
                raise FormalContextPlanError(f"Context preview has no chapter_id: {preview_id}")
            created_at = utc_stamp()
            plan_id = new_formal_context_plan_id()
            plan_path = self.plans_dir / f"{safe_filename(chapter_id)}__{plan_id}.json"
            priority_order = context_priority_order(self.store)
            artifact = {
                "schema_version": 1,
                "plan_id": plan_id,
                "preview_id": preview_id,
                "update_id": str(preview.get("update_id") or ""),
                "chapter_id": chapter_id,
                "title": str(preview.get("title") or ""),
                "source_draft_id": str(preview.get("source_draft_id") or ""),
                "confirmed_chapter_id": str(preview.get("confirmed_chapter_id") or chapter_id),
                "status": "plan_ready",
                "created_at": created_at,
                "source": "context_update_preview",
                "priority_order": priority_order,
                "categories": plan_categories(self.store, priority_order),
                "text_stats": preview.get("text_stats") if isinstance(preview.get("text_stats"), dict) else {},
                "safety": {
                    "prompt_copied": False,
                    "text_copied": False,
                    "secret_copied": False,
                    "provider_called": False,
                    "memory_bank_written": False,
                    "rag_written": False,
                    "export_written": False,
                },
                "recommendation": "manual_extraction_required",
            }
            self.store.write_json(plan_path, artifact)
            self._append_index_entry(
                {
                    "plan_id": plan_id,
                    "preview_id": preview_id,
                    "update_id": artifact["update_id"],
                    "chapter_id": chapter_id,
                    "title": artifact["title"],
                    "source_draft_id": artifact["source_draft_id"],
                    "confirmed_chapter_id": artifact["confirmed_chapter_id"],
                    "status": artifact["status"],
                    "created_at": created_at,
                    "path": str(plan_path.relative_to(self.store.root)),
                    "recommendation": artifact["recommendation"],
                    "priority_order": priority_order,
                }
            )
            return FormalContextPlanResult(
                plan_id=plan_id,
                preview_id=preview_id,
                chapter_id=chapter_id,
                status="plan_ready",
                path=str(plan_path),
                created_at=created_at,
            )

    def list_formal_context_plans(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "plans": []})
        if not isinstance(index, dict):
            return []
        items = index.get("plans")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_formal_context_plan(self, plan_id: str) -> dict[str, Any]:
        for item in self.list_formal_context_plans():
            if item.get("plan_id") != plan_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise FormalContextPlanError(f"Formal context plan index entry has no path: {plan_id}")
            value = self.store.read_json(path, default=None)
            if not isinstance(value, dict):
                raise FormalContextPlanError(f"Formal context plan artifact is missing or invalid: {plan_id}")
            return value
        raise FormalContextPlanError(f"Formal context plan not found: {plan_id}")

    def _find_plan_by_preview_id(self, preview_id: str) -> dict[str, Any] | None:
        for item in self.list_formal_context_plans():
            if item.get("preview_id") == preview_id:
                return item
        return None

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "plans": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "plans": []}
        items = index.get("plans") if isinstance(index.get("plans"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "plans": items})


def plan_categories(store: ProjectStore, priority_order: list[str]) -> list[dict[str, Any]]:
    config = store.read_config()
    context_policy = config.get("context_policy") if isinstance(config, dict) else {}
    formal = context_policy.get("formal_context_policy") if isinstance(context_policy, dict) else {}
    raw_categories = formal.get("categories") if isinstance(formal, dict) else {}
    categories: list[dict[str, Any]] = []
    for index, category_id in enumerate(priority_order, start=1):
        raw = raw_categories.get(category_id) if isinstance(raw_categories, dict) else {}
        raw = raw if isinstance(raw, dict) else {}
        categories.append(
            {
                "category_id": category_id,
                "priority": index,
                "label": str(raw.get("label") or default_category_label(category_id)),
                "target": str(raw.get("target") or "memory_bank"),
                "enabled": bool(raw.get("enabled", True)),
                "auto_extract": False,
                "operation": "manual_extract_plan_only",
                "state": "not_started",
            }
        )
    return categories


def default_category_label(category_id: str) -> str:
    labels = {
        "world_building": "World Building",
        "character_relationships": "Character Relationships",
        "chapter_summary": "Chapter Summary",
        "style_memory": "Style Memory",
        "foreshadowing": "Foreshadowing",
    }
    return labels.get(category_id, category_id.replace("_", " ").title())


def new_formal_context_plan_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"


def default_formal_context_priority_order() -> list[str]:
    return list(FORMAL_CONTEXT_PRIORITY_ORDER)
