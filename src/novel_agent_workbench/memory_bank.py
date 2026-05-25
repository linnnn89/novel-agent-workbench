from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .storage import ProjectStore, utc_stamp


DEFAULT_MEMORY_TARGET_TOKENS = 5000
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

    MAIN_MEMORY_ID = "main_memory_bank"

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def ensure_main_memory_item(self) -> dict[str, Any]:
        self.store.initialize()
        with self.store.lock():
            memory_bank = self._read_memory_bank()
            for item in memory_bank["items"]:
                if str(item.get("memory_id") or item.get("id") or "") == self.MAIN_MEMORY_ID:
                    return public_memory_item(item, include_text=True)
            now = utc_stamp()
            item = {
                "memory_id": self.MAIN_MEMORY_ID,
                "schema_version": 1,
                "entry_type": "manual_main_memory",
                "status": "manual_text_required",
                "source": "desktop_memory_bank",
                "source_preview_id": "",
                "source_task_id": "",
                "chapter_id": "",
                "title": "记忆银行正文",
                "category_id": "chapter_summary",
                "priority": 3,
                "target": "memory_bank",
                "memory_weight": 1.0,
                "duplicate_risk": "not_applicable",
                "enabled": True,
                "lifecycle_status": "active",
                "lifecycle_reason_code": "",
                "text": "",
                "text_status": "not_extracted",
                "target_token_budget": DEFAULT_MEMORY_TARGET_TOKENS,
                "source_chapter_ids": [],
                "last_updated_chapter_id": "",
                "last_updated_chapter_number": 0,
                "created_at": now,
                "updated_at": now,
                "safety": {
                    "prompt_copied": False,
                    "text_copied": False,
                    "secret_copied": False,
                    "provider_called": False,
                    "manual_text": False,
                },
            }
            memory_bank["items"].append(item)
            memory_bank["enabled"] = True
            memory_bank["updated_at"] = now
            self.store.write_json(self.store.data_file_path("memory_bank.json"), memory_bank)
            return public_memory_item(item, include_text=True)

    def list_memory_items(self, *, include_text: bool = False) -> list[dict[str, Any]]:
        memory_bank = self._read_memory_bank()
        return [public_memory_item(item, include_text=include_text) for item in memory_bank["items"]]

    def read_memory_item(self, memory_id: str, *, include_text: bool = False) -> dict[str, Any]:
        for item in self.list_memory_items(include_text=include_text):
            if item.get("memory_id") == memory_id or item.get("id") == memory_id:
                return item
        raise MemoryBankError(f"Memory item not found: {memory_id}")

    def set_memory_text(
        self,
        memory_id: str,
        text: str,
        *,
        source_chapter_ids: list[str] | None = None,
        target_token_budget: int | None = None,
    ) -> MemoryBankUpdateResult:
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
            source_ids = normalize_source_chapter_ids(source_chapter_ids)
            target_metadata = {}
            if target_token_budget is not None:
                target_metadata["target_token_budget"] = validate_memory_target_tokens(target_token_budget)
            for item in memory_bank["items"]:
                item_id = str(item.get("memory_id") or item.get("id") or "")
                if item_id == memory_id:
                    source_metadata: dict[str, Any] = {}
                    if source_ids:
                        merged_source_ids = merge_chapter_ids(item.get("source_chapter_ids"), source_ids)
                        last_chapter_id = latest_chapter_id(merged_source_ids)
                        source_metadata = {
                            "source_chapter_ids": merged_source_ids,
                            "last_updated_chapter_id": last_chapter_id,
                            "last_updated_chapter_number": chapter_number_from_id(last_chapter_id) or 0,
                        }
                    item = {
                        **item,
                        **source_metadata,
                        **target_metadata,
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
        target_token_budget: int | None = None,
    ) -> MemoryBankLifecycleResult:
        safe_reason_code = validate_memory_reason_code(reason_code)
        target_metadata = {}
        if target_token_budget is not None:
            target_metadata["target_token_budget"] = validate_memory_target_tokens(target_token_budget)
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
                        **target_metadata,
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
        "target_token_budget": normalize_memory_target_tokens(item.get("target_token_budget")),
        "source_chapter_ids": normalize_source_chapter_ids(item.get("source_chapter_ids")),
        "last_updated_chapter_id": item.get("last_updated_chapter_id") or "",
        "last_updated_chapter_number": item.get("last_updated_chapter_number") or 0,
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
    for pattern in SECRET_LIKE_PATTERNS:
        if pattern.search(value):
            raise MemoryBankError("Memory text appears to contain a secret-like value.")


def normalize_memory_target_tokens(value: object) -> int:
    if isinstance(value, bool):
        return DEFAULT_MEMORY_TARGET_TOKENS
    if isinstance(value, int):
        return value if value > 0 else DEFAULT_MEMORY_TARGET_TOKENS
    text = str(value or "").strip()
    if not text:
        return DEFAULT_MEMORY_TARGET_TOKENS
    try:
        parsed = int(text)
    except ValueError:
        return DEFAULT_MEMORY_TARGET_TOKENS
    return parsed if parsed > 0 else DEFAULT_MEMORY_TARGET_TOKENS


def validate_memory_target_tokens(value: object) -> int:
    if isinstance(value, bool):
        raise MemoryBankError("Memory target token budget must be a positive integer.")
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        raise MemoryBankError("Memory target token budget must be a positive integer.") from None
    if parsed <= 0:
        raise MemoryBankError("Memory target token budget must be a positive integer.")
    return parsed


def normalize_source_chapter_ids(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise MemoryBankError(f"Unsafe source chapter id: {value!r}")
        normalized.append(value)
        seen.add(value)
    return normalized


def merge_chapter_ids(existing: object, added: list[str]) -> list[str]:
    return normalize_source_chapter_ids([*normalize_source_chapter_ids(existing), *added])


def chapter_number_from_id(chapter_id: str) -> int | None:
    match = re.search(r"(\d+)$", str(chapter_id or ""))
    if not match:
        return None
    return int(match.group(1))


def latest_chapter_id(chapter_ids: list[str]) -> str:
    if not chapter_ids:
        return ""
    return max(
        chapter_ids,
        key=lambda value: (
            chapter_number_from_id(value) if chapter_number_from_id(value) is not None else -1,
            chapter_ids.index(value),
        ),
    )


def validate_memory_reason_code(reason_code: str) -> str:
    value = str(reason_code or "").strip()
    if not value:
        return ""
    if len(value) > 80:
        raise MemoryBankError("reason_code is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise MemoryBankError("reason_code must use ASCII letters, numbers, '_' or '-'.")
    return value
