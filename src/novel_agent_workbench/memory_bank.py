from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .chapters import format_chapter_id
from .config import (
    DEFAULT_MEMORY_COMPRESSION_SYSTEM_PROMPT,
    DEFAULT_MEMORY_COMPRESSION_TASK_PROMPT,
    DEFAULT_MEMORY_GENERATION_SYSTEM_PROMPT,
    DEFAULT_MEMORY_GENERATION_TASK_PROMPT,
    memory_prompt_settings,
)
from .drafts import sanitize_provider_draft_text
from .providers import ProviderRequest, generate_with_provider, provider_request_role_or_writer_fallback
from .storage import ProjectStore, utc_stamp


DEFAULT_MEMORY_TARGET_TOKENS = 5000
DEFAULT_MEMORY_AUTO_SUMMARY_CHAPTER_INTERVAL = 5
DEFAULT_MEMORY_GENERATION_TEMPERATURE = 0.2
DEFAULT_MEMORY_GENERATION_TOP_P = 1.0
DEFAULT_MEMORY_GENERATION_MAX_TOKENS = 8000
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


@dataclass(frozen=True, slots=True)
class MemoryBankGenerationResult:
    text: str
    text_chars: int
    provider: str
    model: str
    finish_reason: str
    usage: dict[str, int]
    request_summary: dict[str, Any]

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

    def preview_memory_generation_request(
        self,
        *,
        current_memory: str,
        chapters: list[dict[str, Any]],
        target_token_budget: int | None = None,
    ) -> dict[str, Any]:
        selected_chapters = normalize_memory_generation_chapters(chapters)
        request = build_memory_generation_provider_request(
            self.store,
            current_memory=current_memory,
            chapters=selected_chapters,
            target_token_budget=target_token_budget,
        )
        return memory_generation_request_preview(
            request,
            current_memory=current_memory,
            chapters=selected_chapters,
            target_token_budget=target_token_budget,
        )

    def preview_memory_compression_request(
        self,
        *,
        current_memory: str,
        target_token_budget: int | None = None,
    ) -> dict[str, Any]:
        request = build_memory_compression_provider_request(
            self.store,
            current_memory=current_memory,
            target_token_budget=target_token_budget,
        )
        target_tokens = normalize_memory_target_tokens(target_token_budget)
        existing_memory = str(current_memory or "").strip()
        return {
            "schema_version": 1,
            "provider_request_role": request.role,
            "logical_role": "writer",
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "sampling": {
                "temperature": request.temperature,
                "top_p": request.top_p,
                "max_tokens": request.max_tokens,
                "stream": request.stream,
            },
            "metadata": dict(request.metadata),
            "summary": {
                "prompt_chars": len(request.prompt),
                "system_prompt_chars": len(request.system_prompt or ""),
                "target_token_budget": target_tokens,
                "request_max_tokens": request.max_tokens,
                "source_chapter_count": 0,
                "source_chapter_ids": [],
                "existing_memory_chars": len(existing_memory),
            },
        }

    def auto_summary_candidate(self, *, confirmed_chapters: list[dict[str, Any]], batch_size: int = DEFAULT_MEMORY_AUTO_SUMMARY_CHAPTER_INTERVAL) -> dict[str, Any]:
        return memory_auto_summary_candidate(
            self._read_main_memory_item_or_default(),
            confirmed_chapters,
            batch_size=batch_size,
        )

    def generate_memory_text(
        self,
        *,
        current_memory: str,
        chapters: list[dict[str, Any]],
        target_token_budget: int | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
    ) -> MemoryBankGenerationResult:
        self.store.initialize()
        selected_chapters = normalize_memory_generation_chapters(chapters)
        request = build_memory_generation_provider_request(
            self.store,
            current_memory=current_memory,
            chapters=selected_chapters,
            target_token_budget=target_token_budget,
            stream_callback=stream_callback,
            reasoning_callback=reasoning_callback,
        )
        response = generate_with_provider(self.store, request)
        sanitized = sanitize_provider_draft_text(response.text)
        generated_text = str(sanitized["content"] or "").strip()
        validate_manual_memory_text(generated_text)
        target_tokens = normalize_memory_target_tokens(target_token_budget)
        source_ids = memory_generation_source_chapter_ids(selected_chapters)
        return MemoryBankGenerationResult(
            text=generated_text,
            text_chars=len(generated_text),
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            request_summary={
                "prompt_chars": len(request.prompt),
                "system_prompt_chars": len(request.system_prompt or ""),
                "target_token_budget": target_tokens,
                "request_max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "stream": request.stream,
                "source_chapter_count": len(selected_chapters),
                "source_chapter_ids": source_ids,
                "existing_memory_chars": len(str(current_memory or "").strip()),
                "provider_request_role": request.role,
                "logical_role": "writer",
                "metadata_keys": sorted(str(key) for key in request.metadata),
                "response_sanitizer": sanitized["summary"],
            },
        )

    def generate_memory_compression_text(
        self,
        *,
        current_memory: str,
        target_token_budget: int | None = None,
        stream_callback: Callable[[str], None] | None = None,
        reasoning_callback: Callable[[str], None] | None = None,
    ) -> MemoryBankGenerationResult:
        self.store.initialize()
        if not str(current_memory or "").strip():
            raise MemoryBankError("Current Memory Bank text is empty.")
        request = build_memory_compression_provider_request(
            self.store,
            current_memory=current_memory,
            target_token_budget=target_token_budget,
            stream_callback=stream_callback,
            reasoning_callback=reasoning_callback,
        )
        response = generate_with_provider(self.store, request)
        sanitized = sanitize_provider_draft_text(response.text)
        generated_text = str(sanitized["content"] or "").strip()
        validate_manual_memory_text(generated_text)
        target_tokens = normalize_memory_target_tokens(target_token_budget)
        return MemoryBankGenerationResult(
            text=generated_text,
            text_chars=len(generated_text),
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            request_summary={
                "prompt_chars": len(request.prompt),
                "system_prompt_chars": len(request.system_prompt or ""),
                "target_token_budget": target_tokens,
                "request_max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "stream": request.stream,
                "source_chapter_count": 0,
                "source_chapter_ids": [],
                "existing_memory_chars": len(str(current_memory or "").strip()),
                "provider_request_role": request.role,
                "logical_role": "writer",
                "metadata_keys": sorted(str(key) for key in request.metadata),
                "response_sanitizer": sanitized["summary"],
            },
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

    def _read_main_memory_item_or_default(self) -> dict[str, Any]:
        for item in self._read_memory_bank()["items"]:
            if str(item.get("memory_id") or item.get("id") or "") == self.MAIN_MEMORY_ID:
                return public_memory_item(item, include_text=True)
        return {
            "memory_id": self.MAIN_MEMORY_ID,
            "text": "",
            "text_chars": 0,
            "source_chapter_ids": [],
            "last_updated_chapter_id": "",
            "last_updated_chapter_number": 0,
            "target_token_budget": DEFAULT_MEMORY_TARGET_TOKENS,
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


def memory_auto_summary_candidate(
    memory_item: dict[str, Any],
    confirmed_chapters: list[dict[str, Any]],
    *,
    batch_size: int = DEFAULT_MEMORY_AUTO_SUMMARY_CHAPTER_INTERVAL,
) -> dict[str, Any]:
    safe_batch_size = normalize_auto_summary_batch_size(batch_size)
    last_number = memory_item_progress_number(memory_item)
    has_memory = bool(str(memory_item.get("text") or "").strip()) or safe_nonnegative_int(memory_item.get("text_chars")) > 0
    if last_number <= 0 and has_memory:
        return {
            "ready": False,
            "reason": "manual_progress_missing",
            "batch_size": safe_batch_size,
            "last_updated_chapter_number": 0,
            "source_chapter_ids": [],
            "eligible_chapter_count": 0,
        }
    eligible = chapters_after_progress(confirmed_chapters, last_number)
    selected = eligible[:safe_batch_size]
    ready = len(selected) >= safe_batch_size
    return {
        "ready": ready,
        "reason": "ready" if ready else "waiting_for_batch",
        "batch_size": safe_batch_size,
        "last_updated_chapter_number": last_number,
        "source_chapter_ids": [str(item.get("chapter_id") or "") for item in selected],
        "eligible_chapter_count": len(eligible),
        "remaining_after_batch": max(len(eligible) - len(selected), 0),
        "from_chapter_number": chapter_number_from_id(str(selected[0].get("chapter_id") or "")) if selected else 0,
        "to_chapter_number": chapter_number_from_id(str(selected[-1].get("chapter_id") or "")) if selected else 0,
    }


def normalize_auto_summary_batch_size(value: object) -> int:
    if isinstance(value, bool):
        return DEFAULT_MEMORY_AUTO_SUMMARY_CHAPTER_INTERVAL
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_MEMORY_AUTO_SUMMARY_CHAPTER_INTERVAL
    return parsed if parsed > 0 else DEFAULT_MEMORY_AUTO_SUMMARY_CHAPTER_INTERVAL


def memory_item_progress_number(memory_item: dict[str, Any]) -> int:
    value = memory_item.get("last_updated_chapter_number")
    if isinstance(value, int) and not isinstance(value, bool):
        return max(value, 0)
    if isinstance(value, str) and value.strip().isdigit():
        return max(int(value.strip()), 0)
    chapter_id = str(memory_item.get("last_updated_chapter_id") or "")
    number = chapter_number_from_id(chapter_id)
    return number or 0


def safe_nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, str) and value.strip().isdigit():
        return max(int(value.strip()), 0)
    return 0


def chapters_after_progress(chapters: list[dict[str, Any]], last_number: int) -> list[dict[str, Any]]:
    indexed: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(chapters):
        if not isinstance(item, dict):
            continue
        chapter_id = str(item.get("chapter_id") or "")
        number = chapter_number_from_id(chapter_id)
        if number is None or number <= last_number:
            continue
        indexed.append((number, index, item))
    return [item for _number, _index, item in sorted(indexed, key=lambda value: (value[0], value[1]))]


def validate_memory_reason_code(reason_code: str) -> str:
    value = str(reason_code or "").strip()
    if not value:
        return ""
    if len(value) > 80:
        raise MemoryBankError("reason_code is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise MemoryBankError("reason_code must use ASCII letters, numbers, '_' or '-'.")
    return value


def build_memory_generation_provider_request(
    store: ProjectStore,
    *,
    current_memory: str,
    chapters: list[dict[str, Any]],
    target_token_budget: int | None = None,
    stream_callback: Callable[[str], None] | None = None,
    reasoning_callback: Callable[[str], None] | None = None,
) -> ProviderRequest:
    selected_chapters = normalize_memory_generation_chapters(chapters)
    target_tokens = normalize_memory_target_tokens(target_token_budget)
    source_ids = memory_generation_source_chapter_ids(selected_chapters)
    role = provider_request_role_or_writer_fallback(
        store,
        "writer",
        feature_id="memory_generation",
    )
    metadata = {
        "memory_bank_generation": True,
        "source_chapter_count": len(selected_chapters),
        "source_chapter_ids": source_ids,
        "target_token_budget": target_tokens,
        "existing_memory_chars": len(str(current_memory or "").strip()),
    }
    prompts = memory_prompt_settings(store.read_config())
    return ProviderRequest(
        role=role,
        feature_id="memory_generation",
        system_prompt=prompts["generation_system_prompt"],
        prompt=format_memory_update_prompt(
            current_memory=current_memory,
            chapters=selected_chapters,
            target_tokens=target_tokens,
            template=prompts["generation_task_prompt"],
        ),
        temperature=DEFAULT_MEMORY_GENERATION_TEMPERATURE,
        top_p=DEFAULT_MEMORY_GENERATION_TOP_P,
        max_tokens=memory_generation_max_tokens(target_tokens),
        stream=True,
        metadata=metadata,
        stream_callback=stream_callback,
        reasoning_callback=reasoning_callback,
    )


def build_memory_compression_provider_request(
    store: ProjectStore,
    *,
    current_memory: str,
    target_token_budget: int | None = None,
    stream_callback: Callable[[str], None] | None = None,
    reasoning_callback: Callable[[str], None] | None = None,
) -> ProviderRequest:
    existing_memory = str(current_memory or "").strip()
    if not existing_memory:
        raise MemoryBankError("Current Memory Bank text is empty.")
    target_tokens = normalize_memory_target_tokens(target_token_budget)
    role = provider_request_role_or_writer_fallback(
        store,
        "writer",
        feature_id="memory_compression",
    )
    metadata = {
        "memory_bank_compression": True,
        "target_token_budget": target_tokens,
        "existing_memory_chars": len(existing_memory),
    }
    prompts = memory_prompt_settings(store.read_config())
    return ProviderRequest(
        role=role,
        feature_id="memory_compression",
        system_prompt=prompts["compression_system_prompt"],
        prompt=format_memory_compression_prompt(
            current_memory=existing_memory,
            target_tokens=target_tokens,
            template=prompts["compression_task_prompt"],
        ),
        temperature=DEFAULT_MEMORY_GENERATION_TEMPERATURE,
        top_p=DEFAULT_MEMORY_GENERATION_TOP_P,
        max_tokens=memory_generation_max_tokens(target_tokens),
        stream=True,
        metadata=metadata,
        stream_callback=stream_callback,
        reasoning_callback=reasoning_callback,
    )


def memory_generation_system_prompt(config: object = None) -> str:
    if config is None:
        return DEFAULT_MEMORY_GENERATION_SYSTEM_PROMPT
    return memory_prompt_settings(config)["generation_system_prompt"]


def memory_compression_system_prompt(config: object = None) -> str:
    if config is None:
        return DEFAULT_MEMORY_COMPRESSION_SYSTEM_PROMPT
    return memory_prompt_settings(config)["compression_system_prompt"]


def format_memory_update_prompt(
    *,
    current_memory: str,
    chapters: list[dict[str, Any]] | None = None,
    chapter: dict[str, Any] | None = None,
    target_tokens: int = DEFAULT_MEMORY_TARGET_TOKENS,
    template: str = "",
) -> str:
    selected_chapters = normalize_memory_generation_chapters(chapters or ([] if chapter is None else [chapter]))
    safe_target_tokens = normalize_memory_target_tokens(target_tokens)
    existing_memory = str(current_memory or "").strip()
    if not existing_memory:
        existing_memory = "（当前记忆银行为空，请根据本次发送的定稿章节建立项目长期记忆。）"
    chapter_lines: list[str] = []
    for index, item in enumerate(selected_chapters, start=1):
        chapter_id = safe_memory_prompt_value(item.get("chapter_id")) or format_chapter_id(index)
        title = safe_memory_prompt_value(item.get("title")) or chapter_id
        content = str(item.get("content") or "").strip() or "（本章正文为空或未读取到正文。）"
        chapter_lines.extend(
            [
                f"<<<CHAPTER {index} id={chapter_id} title={title} chars={len(content)}>>>",
                content,
                f"<<<END CHAPTER {index}>>>",
                "",
            ]
        )
    chapters_text = "\n".join(chapter_lines).rstrip()
    return render_memory_prompt_template(
        template or DEFAULT_MEMORY_GENERATION_TASK_PROMPT,
        {
            "target_tokens": str(safe_target_tokens),
            "current_memory": existing_memory,
            "chapter_count": str(len(selected_chapters)),
            "chapters": chapters_text,
        },
        required=("current_memory", "chapters"),
    )


def format_memory_compression_prompt(
    *,
    current_memory: str,
    target_tokens: int = DEFAULT_MEMORY_TARGET_TOKENS,
    template: str = "",
) -> str:
    safe_target_tokens = normalize_memory_target_tokens(target_tokens)
    existing_memory = str(current_memory or "").strip() or "（当前记忆银行为空。）"
    return render_memory_prompt_template(
        template or DEFAULT_MEMORY_COMPRESSION_TASK_PROMPT,
        {
            "target_tokens": str(safe_target_tokens),
            "current_memory": existing_memory,
        },
        required=("current_memory",),
    )


def render_memory_prompt_template(
    template: str,
    values: dict[str, str],
    *,
    required: tuple[str, ...],
) -> str:
    """Render supported fields and never drop required source text from a custom template."""
    rendered = str(template or "")
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    missing = [key for key in required if "{" + key + "}" not in str(template or "")]
    if missing:
        extras = [values[key] for key in missing if str(values.get(key) or "").strip()]
        if extras:
            rendered = rendered.rstrip() + "\n\n" + "\n\n".join(extras)
    return rendered.strip()


def memory_generation_request_preview(
    request: ProviderRequest,
    *,
    current_memory: str,
    chapters: list[dict[str, Any]],
    target_token_budget: int | None = None,
) -> dict[str, Any]:
    target_tokens = normalize_memory_target_tokens(target_token_budget)
    selected_chapters = normalize_memory_generation_chapters(chapters)
    return {
        "schema_version": 1,
        "provider_request_role": request.role,
        "logical_role": "writer",
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.prompt},
        ],
        "sampling": {
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stream": request.stream,
        },
        "metadata": dict(request.metadata),
        "summary": {
            "prompt_chars": len(request.prompt),
            "system_prompt_chars": len(request.system_prompt or ""),
            "target_token_budget": target_tokens,
            "request_max_tokens": request.max_tokens,
            "source_chapter_count": len(selected_chapters),
            "source_chapter_ids": memory_generation_source_chapter_ids(selected_chapters),
            "existing_memory_chars": len(str(current_memory or "").strip()),
        },
    }


def normalize_memory_generation_chapters(chapters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not chapters:
        raise MemoryBankError("At least one confirmed chapter is required for Memory Bank generation.")
    normalized: list[dict[str, Any]] = []
    non_empty_content = 0
    for index, item in enumerate(chapters, start=1):
        if not isinstance(item, dict):
            raise MemoryBankError("Memory Bank generation chapters must be objects.")
        chapter_id = safe_memory_prompt_value(item.get("chapter_id")) or format_chapter_id(index)
        normalize_source_chapter_ids([chapter_id])
        title = safe_memory_prompt_value(item.get("title")) or chapter_id
        content = str(item.get("content") or "").strip()
        if content:
            non_empty_content += 1
        normalized.append({**item, "chapter_id": chapter_id, "title": title, "content": content})
    if non_empty_content <= 0:
        raise MemoryBankError("Selected chapters do not contain readable content.")
    return normalized


def memory_generation_source_chapter_ids(chapters: list[dict[str, Any]]) -> list[str]:
    return normalize_source_chapter_ids([str(item.get("chapter_id") or "") for item in chapters])


def memory_generation_max_tokens(target_tokens: int) -> int:
    normalize_memory_target_tokens(target_tokens)
    return DEFAULT_MEMORY_GENERATION_MAX_TOKENS


def safe_memory_prompt_value(value: object) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text[:160]
