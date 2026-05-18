from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .storage import ProjectStore, utc_stamp


MAX_MANUAL_MEMORY_TEXT_CHARS = 1200
SECRET_LIKE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
    re.compile(r"\bcpk_[A-Za-z0-9_.\-]{12,}\b"),
]


class MemoryBankError(RuntimeError):
    """Raised when a Memory Bank manual edit is invalid."""


@dataclass(frozen=True, slots=True)
class MemoryBankUpdateResult:
    memory_id: str
    status: str
    text_chars: int
    checkpoint: dict[str, Any]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MemoryBankLifecycleResult:
    memory_id: str
    enabled: bool
    lifecycle_status: str
    reason_code: str
    checkpoint: dict[str, Any]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryBankService:
    """Manual Memory Bank text fill/edit workflow."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def list_memory_items(self, *, include_text: bool = False) -> list[dict[str, Any]]:
        memory_bank = self._read_memory_bank()
        return [public_memory_item(item, include_text=include_text) for item in memory_bank["items"]]

    def read_memory_item(self, memory_id: str, *, include_text: bool = False) -> dict[str, Any]:
        for item in self.list_memory_items(include_text=include_text):
            if item.get("memory_id") == memory_id or item.get("id") == memory_id:
                return item
        raise MemoryBankError(f"Memory item not found: {memory_id}")

    def set_memory_text(self, memory_id: str, text: str) -> MemoryBankUpdateResult:
        validate_manual_memory_text(text)
        self.store.initialize()
        with self.store.lock():
            memory_bank = self._read_memory_bank()
            if not any(str(item.get("memory_id") or item.get("id") or "") == memory_id for item in memory_bank["items"]):
                raise MemoryBankError(f"Memory item not found: {memory_id}")
            checkpoint = self.store.create_checkpoint(label="pre_memory_text_update")
            updated_items: list[dict[str, Any]] = []
            result_item: dict[str, Any] | None = None
            updated_at = utc_stamp()
            for item in memory_bank["items"]:
                item_id = str(item.get("memory_id") or item.get("id") or "")
                if item_id == memory_id:
                    item = {
                        **item,
                        "text": text.strip(),
                        "status": "ready",
                        "text_status": "manual",
                        "updated_at": updated_at,
                        "safety": {
                            **(item.get("safety") if isinstance(item.get("safety"), dict) else {}),
                            "manual_text": True,
                            "provider_called": False,
                        },
                    }
                    result_item = item
                updated_items.append(item)
            memory_bank["items"] = updated_items
            memory_bank["enabled"] = True
            memory_bank["updated_at"] = updated_at
            self.store.write_json(self.store.data_file_path("memory_bank.json"), memory_bank)
            return MemoryBankUpdateResult(
                memory_id=memory_id,
                status=str(result_item.get("status") or ""),
                text_chars=len(str(result_item.get("text") or "")),
                checkpoint=checkpoint,
                updated_at=updated_at,
            )

    def set_memory_item_enabled(
        self,
        memory_id: str,
        *,
        enabled: bool,
        reason_code: str = "",
    ) -> MemoryBankLifecycleResult:
        safe_reason_code = validate_memory_reason_code(reason_code)
        self.store.initialize()
        with self.store.lock():
            memory_bank = self._read_memory_bank()
            if not any(str(item.get("memory_id") or item.get("id") or "") == memory_id for item in memory_bank["items"]):
                raise MemoryBankError(f"Memory item not found: {memory_id}")
            checkpoint = self.store.create_checkpoint(label="pre_memory_lifecycle_update")
            updated_items: list[dict[str, Any]] = []
            result_item: dict[str, Any] | None = None
            updated_at = utc_stamp()
            for item in memory_bank["items"]:
                item_id = str(item.get("memory_id") or item.get("id") or "")
                if item_id == memory_id:
                    item = {
                        **item,
                        "enabled": enabled,
                        "lifecycle_status": "active" if enabled else "disabled",
                        "lifecycle_reason_code": safe_reason_code,
                        "updated_at": updated_at,
                    }
                    result_item = item
                updated_items.append(item)
            memory_bank["items"] = updated_items
            memory_bank["updated_at"] = updated_at
            self.store.write_json(self.store.data_file_path("memory_bank.json"), memory_bank)
            return MemoryBankLifecycleResult(
                memory_id=memory_id,
                enabled=bool(result_item.get("enabled")),
                lifecycle_status=str(result_item.get("lifecycle_status") or ""),
                reason_code=str(result_item.get("lifecycle_reason_code") or ""),
                checkpoint=checkpoint,
                updated_at=updated_at,
            )

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


def public_memory_item(item: dict[str, Any], *, include_text: bool) -> dict[str, Any]:
    text = str(item.get("text") or "")
    public = {
        "memory_id": item.get("memory_id") or item.get("id"),
        "entry_type": item.get("entry_type"),
        "status": item.get("status"),
        "source": item.get("source"),
        "source_preview_id": item.get("source_preview_id"),
        "source_task_id": item.get("source_task_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "category_id": item.get("category_id"),
        "priority": item.get("priority"),
        "target": item.get("target"),
        "memory_weight": item.get("memory_weight"),
        "duplicate_risk": item.get("duplicate_risk"),
        "enabled": item.get("enabled") if isinstance(item.get("enabled"), bool) else True,
        "lifecycle_status": item.get("lifecycle_status") or "active",
        "lifecycle_reason_code": item.get("lifecycle_reason_code") or "",
        "text_status": item.get("text_status"),
        "text_chars": len(text),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
    if include_text:
        public["text"] = text
    return public


def validate_manual_memory_text(text: str) -> None:
    value = text.strip()
    if not value:
        raise MemoryBankError("Memory text cannot be empty.")
    if len(value) > MAX_MANUAL_MEMORY_TEXT_CHARS:
        raise MemoryBankError(f"Memory text is too long: {len(value)} > {MAX_MANUAL_MEMORY_TEXT_CHARS}")
    for pattern in SECRET_LIKE_PATTERNS:
        if pattern.search(value):
            raise MemoryBankError("Memory text appears to contain a secret-like value.")


def validate_memory_reason_code(reason_code: str) -> str:
    value = str(reason_code or "").strip()
    if not value:
        return ""
    if len(value) > 80:
        raise MemoryBankError("reason_code is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise MemoryBankError("reason_code must use ASCII letters, numbers, '_' or '-'.")
    return value
