from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil
from typing import Any

from .config import FORMAL_CONTEXT_PRIORITY_ORDER
from .formal_context import FormalContextPlanService
from .storage import ProjectStore


DEFAULT_CHARS_PER_TOKEN = 4


@dataclass(frozen=True, slots=True)
class ContextAssemblyDryRunResult:
    project_id: str
    mode: str
    token_budget: dict[str, Any]
    provider_api_boundary: dict[str, Any]
    selected: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextAssemblerService:
    """Builds metadata-only previews of future Provider context assembly."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    def dry_run(self, *, max_context_tokens: int | None = None) -> ContextAssemblyDryRunResult:
        self.store.initialize()
        config = self.store.read_config()
        context_policy = config.get("context_policy") if isinstance(config, dict) else {}
        configured_budget = safe_int(context_policy.get("max_context_tokens"), default=32768)
        budget = max_context_tokens if isinstance(max_context_tokens, int) and max_context_tokens > 0 else configured_budget
        candidates = build_candidates(self.store)
        selected: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        used_tokens = 0
        for candidate in sorted(candidates, key=candidate_sort_key):
            if candidate.get("enabled") is False:
                skipped.append({**candidate, "selection_status": "skipped", "skip_reason": "memory_item_disabled"})
                continue
            estimated_tokens = safe_int(candidate.get("estimated_tokens"), default=0)
            if estimated_tokens <= 0:
                skipped.append({**candidate, "selection_status": "skipped", "skip_reason": "empty_or_metadata_only"})
                continue
            if used_tokens + estimated_tokens > budget:
                skipped.append({**candidate, "selection_status": "skipped", "skip_reason": "token_budget_exceeded"})
                continue
            selected.append({**candidate, "selection_status": "selected", "skip_reason": ""})
            used_tokens += estimated_tokens
        return ContextAssemblyDryRunResult(
            project_id=self.store.project_id,
            mode="metadata_only_dry_run",
            token_budget={
                "max_context_tokens": budget,
                "estimated_used_tokens": used_tokens,
                "estimated_remaining_tokens": max(budget - used_tokens, 0),
                "estimator": f"ceil(chars / {DEFAULT_CHARS_PER_TOKEN})",
                "real_tokenizer": "not_implemented",
            },
            provider_api_boundary={
                "llm_api_accepts_priority_fields": False,
                "requires_local_context_assembly": True,
                "output_contains_prompt_text": False,
                "output_contains_chapter_text": False,
                "provider_called": False,
            },
            selected=selected,
            skipped=skipped,
            candidates=candidates,
            warnings=context_warnings(self.store),
        )


def build_candidates(store: ProjectStore) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(formal_context_plan_candidates(store))
    candidates.extend(memory_bank_candidates(store))
    return candidates


def formal_context_plan_candidates(store: ProjectStore) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for plan in FormalContextPlanService(store).list_formal_context_plans():
        plan_id = str(plan.get("plan_id") or "")
        path_value = str(plan.get("path") or "")
        artifact = FormalContextPlanService(store).read_formal_context_plan(plan_id) if plan_id else {}
        text_stats = artifact.get("text_stats") if isinstance(artifact.get("text_stats"), dict) else {}
        char_count = safe_int(text_stats.get("char_count"), default=0)
        categories = artifact.get("categories") if isinstance(artifact.get("categories"), list) else []
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_id = str(category.get("category_id") or "")
            memory_weight = safe_float(category.get("memory_weight"), default=1.0)
            estimated_tokens = ceil((char_count * memory_weight) / DEFAULT_CHARS_PER_TOKEN)
            candidates.append(
                {
                    "source_type": "formal_context_plan",
                    "source_id": plan_id,
                    "source_path": path_value,
                    "chapter_id": str(artifact.get("chapter_id") or plan.get("chapter_id") or ""),
                    "category_id": category_id,
                    "priority": safe_int(category.get("priority"), default=priority_rank(category_id)),
                    "memory_weight": memory_weight,
                    "estimated_tokens": estimated_tokens,
                    "char_count": char_count,
                    "reason": str(category.get("recommendation") or "manual_extract_required"),
                    "contains_text": False,
                    "enabled": True,
                }
            )
    return candidates


def memory_bank_candidates(store: ProjectStore) -> list[dict[str, Any]]:
    path = store.data_file_path("memory_bank.json")
    raw = store.read_json(path, default={"items": []})
    items = raw.get("items") if isinstance(raw, dict) and isinstance(raw.get("items"), list) else []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        category_id = str(item.get("category_id") or item.get("category") or "")
        char_count = item_text_char_count(item)
        memory_weight = safe_float(item.get("memory_weight"), default=1.0)
        enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        candidates.append(
            {
                "source_type": "memory_bank",
                "source_id": str(item.get("memory_id") or item.get("id") or f"memory_{index}"),
                "source_path": "data/memory_bank.json",
                "chapter_id": str(item.get("chapter_id") or ""),
                "category_id": category_id,
                "priority": priority_rank(category_id),
                "memory_weight": memory_weight,
                "estimated_tokens": ceil((char_count * memory_weight) / DEFAULT_CHARS_PER_TOKEN),
                "char_count": char_count,
                "reason": "existing_memory_bank_item" if enabled else "memory_item_disabled",
                "contains_text": False,
                "enabled": enabled,
                "lifecycle_status": item.get("lifecycle_status") or ("active" if enabled else "disabled"),
            }
        )
    return candidates


def item_text_char_count(item: dict[str, Any]) -> int:
    for key in ("text", "content", "summary", "value"):
        value = item.get(key)
        if isinstance(value, str):
            return len(value)
    return safe_int(item.get("char_count"), default=0)


def candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, float, str, str]:
    priority = safe_int(candidate.get("priority"), default=999)
    weight = safe_float(candidate.get("memory_weight"), default=1.0)
    source_type = str(candidate.get("source_type") or "")
    source_id = str(candidate.get("source_id") or "")
    return (priority, -weight, source_type, source_id)


def priority_rank(category_id: str) -> int:
    if category_id in FORMAL_CONTEXT_PRIORITY_ORDER:
        return FORMAL_CONTEXT_PRIORITY_ORDER.index(category_id) + 1
    return 999


def context_warnings(store: ProjectStore) -> list[str]:
    config = store.read_config()
    policy = config.get("context_policy") if isinstance(config, dict) else {}
    warnings: list[str] = [
        "dry_run_only_no_provider_call",
        "real_tokenizer_not_implemented",
        "final_prompt_rendering_not_implemented",
    ]
    if isinstance(policy, dict) and policy.get("world_book_enabled"):
        warnings.append("world_book_enabled_world_building_memory_weight_may_be_reduced")
    return warnings


def safe_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def safe_float(value: Any, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default
