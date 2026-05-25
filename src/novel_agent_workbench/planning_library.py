from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .storage import ProjectStore, utc_stamp


MAX_PLANNING_TEXT_CHARS = 20000
PLANNING_ITEM_TYPES = {
    "outline",
    "beat_sheet",
    "chapter_plan",
    "character_plan",
    "world_plan",
    "constraint",
    "other",
}
ADHERENCE_LEVELS = {"soft", "balanced", "strict"}
SEND_MODES = {"reference_text", "metadata_only"}
SECRET_LIKE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
    re.compile(r"\bcpk[_-][A-Za-z0-9_.\-]{12,}\b"),
]


class PlanningLibraryError(RuntimeError):
    """Raised when a Planning Library operation is invalid."""


@dataclass(frozen=True, slots=True)
class PlanningLibraryItemResult:
    planning_id: str
    active: bool
    enabled: bool
    text_chars: int
    checkpoint: dict[str, Any]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlanningLibraryService:
    """Manual planning-reference storage for local context assembly."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def list_planning_items(self, *, include_text: bool = False) -> list[dict[str, Any]]:
        library = self._read_library()
        return [public_planning_item(item, include_text=include_text) for item in library["items"]]

    def read_planning_item(self, planning_id: str, *, include_text: bool = False) -> dict[str, Any]:
        for item in self.list_planning_items(include_text=include_text):
            if item.get("planning_id") == planning_id or item.get("id") == planning_id:
                return item
        raise PlanningLibraryError(f"Planning item not found: {planning_id}")

    def create_planning_item(
        self,
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
    ) -> PlanningLibraryItemResult:
        safe_id = validate_planning_id(planning_id)
        safe_text = validate_planning_text(text)
        safe_title = validate_short_text(title, field_name="title", max_chars=160)
        safe_type = validate_choice(item_type, PLANNING_ITEM_TYPES, "item_type")
        safe_adherence = validate_choice(adherence_level, ADHERENCE_LEVELS, "adherence_level")
        safe_send_mode = validate_choice(send_mode, SEND_MODES, "send_mode")
        safe_chapter_range = validate_short_text(chapter_range, field_name="chapter_range", max_chars=80)
        safe_priority = validate_priority(priority)
        self.store.initialize()
        with self.store.lock():
            library = self._read_library()
            if any(item_id(item) == safe_id for item in library["items"]):
                raise PlanningLibraryError(f"Planning item already exists: {safe_id}")
            checkpoint = self.store.create_checkpoint(label="pre_planning_library_update")
            now = utc_stamp()
            item = {
                "planning_id": safe_id,
                "title": safe_title,
                "item_type": safe_type,
                "text": safe_text,
                "text_status": "manual",
                "active": bool(active),
                "enabled": bool(enabled),
                "priority": safe_priority,
                "adherence_level": safe_adherence,
                "send_mode": safe_send_mode,
                "chapter_range": safe_chapter_range,
                "created_at": now,
                "updated_at": now,
                "safety": {
                    "manual_text": True,
                    "provider_called": False,
                    "auto_commit": False,
                    "writes_draft": False,
                },
            }
            library["items"].append(item)
            library["enabled"] = True
            library["updated_at"] = now
            write_library(self.store, library)
            return PlanningLibraryItemResult(
                planning_id=safe_id,
                active=bool(item["active"]),
                enabled=bool(item["enabled"]),
                text_chars=len(safe_text),
                checkpoint=checkpoint,
                updated_at=now,
            )

    def update_planning_item(
        self,
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
    ) -> PlanningLibraryItemResult:
        safe_id = validate_planning_id(planning_id)
        safe_text = validate_planning_text(text)
        safe_title = validate_short_text(title, field_name="title", max_chars=160)
        safe_type = validate_choice(item_type, PLANNING_ITEM_TYPES, "item_type")
        safe_adherence = validate_choice(adherence_level, ADHERENCE_LEVELS, "adherence_level")
        safe_send_mode = validate_choice(send_mode, SEND_MODES, "send_mode")
        safe_chapter_range = validate_short_text(chapter_range, field_name="chapter_range", max_chars=80)
        safe_priority = validate_priority(priority)
        self.store.initialize()
        with self.store.lock():
            library = self._read_library()
            if not any(item_id(item) == safe_id for item in library["items"]):
                raise PlanningLibraryError(f"Planning item not found: {safe_id}")
            checkpoint = self.store.create_checkpoint(label="pre_planning_library_update")
            now = utc_stamp()
            result_item: dict[str, Any] | None = None
            updated_items: list[dict[str, Any]] = []
            for item in library["items"]:
                if item_id(item) == safe_id:
                    item = {
                        **item,
                        "title": safe_title,
                        "item_type": safe_type,
                        "text": safe_text,
                        "text_status": "manual",
                        "active": bool(active),
                        "enabled": bool(enabled),
                        "priority": safe_priority,
                        "adherence_level": safe_adherence,
                        "send_mode": safe_send_mode,
                        "chapter_range": safe_chapter_range,
                        "updated_at": now,
                        "safety": {
                            **(item.get("safety") if isinstance(item.get("safety"), dict) else {}),
                            "manual_text": True,
                            "provider_called": False,
                            "auto_commit": False,
                            "writes_draft": False,
                        },
                    }
                    result_item = item
                updated_items.append(item)
            library["items"] = updated_items
            library["enabled"] = True
            library["updated_at"] = now
            write_library(self.store, library)
            assert result_item is not None
            return PlanningLibraryItemResult(
                planning_id=safe_id,
                active=bool(result_item["active"]),
                enabled=bool(result_item["enabled"]),
                text_chars=len(safe_text),
                checkpoint=checkpoint,
                updated_at=now,
            )

    def set_planning_item_active(self, planning_id: str, *, active: bool) -> PlanningLibraryItemResult:
        return self._update_flags(planning_id, active=bool(active), enabled=None)

    def set_planning_item_enabled(self, planning_id: str, *, enabled: bool) -> PlanningLibraryItemResult:
        return self._update_flags(planning_id, active=None, enabled=bool(enabled))

    def _update_flags(
        self,
        planning_id: str,
        *,
        active: bool | None,
        enabled: bool | None,
    ) -> PlanningLibraryItemResult:
        safe_id = validate_planning_id(planning_id)
        self.store.initialize()
        with self.store.lock():
            library = self._read_library()
            if not any(item_id(item) == safe_id for item in library["items"]):
                raise PlanningLibraryError(f"Planning item not found: {safe_id}")
            checkpoint = self.store.create_checkpoint(label="pre_planning_library_update")
            now = utc_stamp()
            result_item: dict[str, Any] | None = None
            updated_items: list[dict[str, Any]] = []
            for item in library["items"]:
                if item_id(item) == safe_id:
                    item = dict(item)
                    if active is not None:
                        item["active"] = active
                    if enabled is not None:
                        item["enabled"] = enabled
                    item["updated_at"] = now
                    result_item = item
                updated_items.append(item)
            library["items"] = updated_items
            library["updated_at"] = now
            write_library(self.store, library)
            assert result_item is not None
            return PlanningLibraryItemResult(
                planning_id=safe_id,
                active=bool(result_item.get("active")),
                enabled=bool(result_item.get("enabled")),
                text_chars=len(str(result_item.get("text") or "")),
                checkpoint=checkpoint,
                updated_at=now,
            )

    def _read_library(self) -> dict[str, Any]:
        value = self.store.read_json(self.store.data_file_path("planning_library.json"), default=default_library())
        return normalize_library(value)


def default_library() -> dict[str, Any]:
    return {"schema_version": 1, "enabled": True, "active_reference_ids": [], "items": []}


def normalize_library(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = default_library()
    items = value.get("items")
    if not isinstance(items, list):
        items = []
    normalized_items = [item for item in items if isinstance(item, dict)]
    return {
        **value,
        "schema_version": int(value.get("schema_version") or 1),
        "enabled": value.get("enabled") if isinstance(value.get("enabled"), bool) else True,
        "active_reference_ids": active_reference_ids(normalized_items),
        "items": normalized_items,
    }


def write_library(store: ProjectStore, library: dict[str, Any]) -> None:
    normalized = normalize_library(library)
    normalized["active_reference_ids"] = active_reference_ids(normalized["items"])
    store.write_json(store.data_file_path("planning_library.json"), normalized)


def active_reference_ids(items: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for item in items:
        planning_id = item_id(item)
        if not planning_id:
            continue
        enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        if enabled and bool(item.get("active")):
            ids.append(planning_id)
    return ids


def public_planning_item(item: dict[str, Any], *, include_text: bool) -> dict[str, Any]:
    text = str(item.get("text") or "")
    public = {
        "planning_id": item_id(item),
        "title": item.get("title"),
        "item_type": item.get("item_type") or "outline",
        "active": bool(item.get("active")),
        "enabled": item.get("enabled") if isinstance(item.get("enabled"), bool) else True,
        "priority": item.get("priority"),
        "adherence_level": item.get("adherence_level") or "balanced",
        "send_mode": item.get("send_mode") or "reference_text",
        "chapter_range": item.get("chapter_range") or "",
        "text_status": item.get("text_status"),
        "text_chars": len(text),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "safety": item.get("safety") if isinstance(item.get("safety"), dict) else {},
    }
    if include_text:
        public["text"] = text
    return public


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("planning_id") or item.get("id") or "")


def validate_planning_id(value: str) -> str:
    safe = str(value or "").strip()
    if not safe:
        raise PlanningLibraryError("planning_id cannot be empty.")
    if len(safe) > 80:
        raise PlanningLibraryError("planning_id is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in safe):
        raise PlanningLibraryError("planning_id must use ASCII letters, numbers, '_' or '-'.")
    return safe


def validate_short_text(value: str, *, field_name: str, max_chars: int) -> str:
    safe = str(value or "").strip()
    if len(safe) > max_chars:
        raise PlanningLibraryError(f"{field_name} is too long: {len(safe)} > {max_chars}")
    return safe


def validate_planning_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        raise PlanningLibraryError("Planning text cannot be empty.")
    if len(value) > MAX_PLANNING_TEXT_CHARS:
        raise PlanningLibraryError(f"Planning text is too long: {len(value)} > {MAX_PLANNING_TEXT_CHARS}")
    for pattern in SECRET_LIKE_PATTERNS:
        if pattern.search(value):
            raise PlanningLibraryError("Planning text appears to contain a secret-like value.")
    return value


def validate_choice(value: str, choices: set[str], field_name: str) -> str:
    defaults = {
        "item_type": "outline",
        "adherence_level": "balanced",
        "send_mode": "reference_text",
    }
    safe = str(value or "").strip() or defaults.get(field_name, "")
    if safe not in choices:
        raise PlanningLibraryError(f"{field_name} must be one of: {', '.join(sorted(choices))}")
    return safe


def validate_priority(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PlanningLibraryError("priority must be an integer.")
    if value < 1 or value > 999:
        raise PlanningLibraryError("priority must be between 1 and 999.")
    return value
