from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from math import ceil
from typing import Any

from .config import FORMAL_CONTEXT_PRIORITY_ORDER, effective_generation_settings
from .drafts import DraftGenerationService
from .formal_context import FormalContextPlanService
from .planning_library import item_id as planning_item_id
from .planning_library import normalize_library
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


@dataclass(frozen=True, slots=True)
class ContextPackagePreviewResult:
    project_id: str
    mode: str
    token_budget: dict[str, Any]
    provider_api_boundary: dict[str, Any]
    include_text: bool
    sections: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PromptRenderDryRunResult:
    project_id: str
    mode: str
    provider_api_boundary: dict[str, Any]
    include_prompt_text: bool
    include_context_text: bool
    prompt_summary: dict[str, Any]
    context_package: dict[str, Any]
    rendered_messages: list[dict[str, Any]]
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
                skipped.append({**candidate, "selection_status": "skipped", "skip_reason": disabled_skip_reason(candidate)})
                continue
            if candidate.get("active") is False:
                skipped.append({**candidate, "selection_status": "skipped", "skip_reason": "planning_item_inactive"})
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

    def package_preview(
        self,
        *,
        max_context_tokens: int | None = None,
        chapter_id: str = "",
        include_text: bool = False,
    ) -> ContextPackagePreviewResult:
        self.store.initialize()
        config = self.store.read_config()
        context_policy = config.get("context_policy") if isinstance(config, dict) else {}
        configured_budget = safe_int(context_policy.get("max_context_tokens"), default=32768)
        budget = max_context_tokens if isinstance(max_context_tokens, int) and max_context_tokens > 0 else configured_budget
        package_items = planning_library_package_candidates(self.store, chapter_id=chapter_id, include_text=include_text)
        package_items.extend(memory_bank_package_candidates(self.store, include_text=include_text))
        package_items.extend(
            recent_confirmed_chapter_package_candidates(
                self.store,
                chapter_id=chapter_id,
                include_text=include_text,
            )
        )
        sections: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        used_tokens = 0
        for item in sorted(package_items, key=candidate_sort_key):
            estimated_tokens = safe_int(item.get("estimated_tokens"), default=0)
            if item.get("enabled") is False:
                skipped.append({**item, "selection_status": "skipped", "skip_reason": disabled_skip_reason(item)})
                continue
            if item.get("active") is False:
                skipped.append({**item, "selection_status": "skipped", "skip_reason": "planning_item_inactive"})
                continue
            if not item.get("ready"):
                skipped.append({**item, "selection_status": "skipped", "skip_reason": missing_text_skip_reason(item)})
                continue
            if estimated_tokens <= 0:
                skipped.append({**item, "selection_status": "skipped", "skip_reason": "empty_or_metadata_only"})
                continue
            if used_tokens + estimated_tokens > budget:
                skipped.append({**item, "selection_status": "skipped", "skip_reason": "token_budget_exceeded"})
                continue
            sections.append({**item, "selection_status": "selected", "skip_reason": ""})
            used_tokens += estimated_tokens
        return ContextPackagePreviewResult(
            project_id=self.store.project_id,
            mode="context_package_preview",
            token_budget={
                "max_context_tokens": budget,
                "estimated_used_tokens": used_tokens,
                "estimated_remaining_tokens": max(budget - used_tokens, 0),
                "estimator": f"ceil(chars / {DEFAULT_CHARS_PER_TOKEN})",
                "real_tokenizer": "not_implemented",
            },
            provider_api_boundary={
                "provider_called": False,
                "output_contains_prompt_text": False,
                "output_contains_chapter_text": False,
                "output_contains_plaintext_secrets": False,
                "final_prompt_rendering": "dry_run_only",
            },
            include_text=include_text,
            sections=sections,
            skipped=skipped,
            warnings=context_warnings(self.store)
            + [
                "preview_only_no_provider_call",
                "manual_planning_and_memory_text_only",
            ],
        )

    def prompt_render_dry_run(
        self,
        *,
        prompt: str,
        system_prompt: str = "",
        max_context_tokens: int | None = None,
        chapter_id: str = "",
        include_prompt_text: bool = False,
        include_context_text: bool = False,
    ) -> PromptRenderDryRunResult:
        self.store.initialize()
        generation_settings = effective_generation_settings(self.store.read_config())
        prompting = generation_settings.get("prompting") if isinstance(generation_settings.get("prompting"), dict) else {}
        context_package = self.package_preview(
            max_context_tokens=max_context_tokens,
            chapter_id=chapter_id,
            include_text=include_context_text,
        ).to_dict()
        prompt_value = str(prompt or "")
        system_prompt_value = str(system_prompt or "").strip() or str(prompting.get("system_prompt") or "")
        target_chapter_value = target_chapter_prompt(chapter_id)
        context_chars = sum(safe_int(item.get("char_count"), default=0) for item in context_package["sections"])
        rendered_messages = [
            rendered_message(
                role="system",
                content=system_prompt_value,
                include_text=include_prompt_text,
                label="system_prompt",
            ),
            rendered_message(
                role="user",
                content=target_chapter_value,
                include_text=include_prompt_text,
                label="target_chapter",
            ),
            {
                "role": "context",
                "label": "generation_context",
                "section_count": len(context_package["sections"]),
                "content_chars": context_chars,
                "content_redacted": not include_context_text,
                "content_source": "active_planning_memory_and_recent_confirmed_chapters",
                "sections": context_package["sections"],
            },
            rendered_message(
                role="user",
                content=prompt_value,
                include_text=include_prompt_text,
                label="draft_prompt",
            ),
        ]
        return PromptRenderDryRunResult(
            project_id=self.store.project_id,
            mode="prompt_render_dry_run",
            provider_api_boundary={
                "provider_called": False,
                "writes_project_files": False,
                "final_prompt_for_provider": False,
                "output_contains_prompt_text": include_prompt_text,
                "output_contains_context_text": include_context_text,
                "output_contains_chapter_text": False,
                "output_contains_plaintext_secrets": False,
            },
            include_prompt_text=include_prompt_text,
            include_context_text=include_context_text,
            prompt_summary={
                "prompt_chars": len(prompt_value),
                "system_prompt_chars": len(system_prompt_value),
                "context_section_count": len(context_package["sections"]),
                "context_chars": context_chars,
                "target_chapter_id": chapter_id,
                "target_chapter_chars": len(target_chapter_value),
                "recent_confirmed_chapter_count": selected_recent_chapter_count(context_package["sections"]),
                "estimated_total_chars": len(prompt_value) + len(system_prompt_value) + len(target_chapter_value) + context_chars,
                "estimated_total_tokens": ceil(
                    (len(prompt_value) + len(system_prompt_value) + len(target_chapter_value) + context_chars)
                    / DEFAULT_CHARS_PER_TOKEN
                ),
            },
            context_package=context_package,
            rendered_messages=rendered_messages,
            warnings=context_package["warnings"]
            + [
                "dry_run_only_no_provider_call",
                "dry_run_output_is_not_logged_by_service",
            ],
        )


def build_candidates(store: ProjectStore) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(planning_library_candidates(store))
    candidates.extend(formal_context_plan_candidates(store))
    candidates.extend(memory_bank_candidates(store))
    return candidates


def planning_library_candidates(store: ProjectStore) -> list[dict[str, Any]]:
    raw = store.read_json(store.data_file_path("planning_library.json"), default={})
    library = normalize_library(raw)
    if library.get("enabled") is False:
        return []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(library["items"], start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        active = bool(item.get("active"))
        send_mode = str(item.get("send_mode") or "reference_text")
        char_count = len(text) if send_mode == "reference_text" else 0
        candidates.append(
            {
                "source_type": "planning_library",
                "source_id": planning_item_id(item) or f"planning_{index}",
                "source_path": "data/planning_library.json",
                "chapter_id": "",
                "category_id": str(item.get("item_type") or "outline"),
                "title": item.get("title"),
                "priority": safe_int(item.get("priority"), default=10),
                "memory_weight": adherence_weight(str(item.get("adherence_level") or "balanced")),
                "estimated_tokens": ceil(char_count / DEFAULT_CHARS_PER_TOKEN),
                "char_count": char_count,
                "reason": "active_planning_reference" if active else "planning_item_inactive",
                "contains_text": False,
                "enabled": enabled,
                "active": active,
                "send_mode": send_mode,
                "adherence_level": item.get("adherence_level") or "balanced",
                "ready": bool(active and enabled and char_count > 0),
            }
        )
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


def memory_bank_package_candidates(store: ProjectStore, *, include_text: bool) -> list[dict[str, Any]]:
    path = store.data_file_path("memory_bank.json")
    raw = store.read_json(path, default={"items": []})
    items = raw.get("items") if isinstance(raw, dict) and isinstance(raw.get("items"), list) else []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        category_id = str(item.get("category_id") or item.get("category") or "")
        enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        ready = bool(enabled and text.strip() and str(item.get("status") or "") == "ready")
        memory_weight = safe_float(item.get("memory_weight"), default=1.0)
        public = {
            "source_type": "memory_bank",
            "source_id": str(item.get("memory_id") or item.get("id") or f"memory_{index}"),
            "source_path": "data/memory_bank.json",
            "chapter_id": str(item.get("chapter_id") or ""),
            "title": item.get("title"),
            "category_id": category_id,
            "section_label": "上下文记忆",
            "section_order": 40,
            "priority": priority_rank(category_id),
            "memory_weight": memory_weight,
            "estimated_tokens": ceil((len(text) * memory_weight) / DEFAULT_CHARS_PER_TOKEN),
            "char_count": len(text),
            "text_status": item.get("text_status"),
            "ready": ready,
            "enabled": enabled,
            "lifecycle_status": item.get("lifecycle_status") or ("active" if enabled else "disabled"),
            "contains_text": include_text and ready,
        }
        if include_text and ready:
            public["text"] = text
        candidates.append(public)
    return candidates


def recent_confirmed_chapter_package_candidates(
    store: ProjectStore,
    *,
    chapter_id: str = "",
    include_text: bool,
) -> list[dict[str, Any]]:
    config = store.read_config()
    generation_settings = effective_generation_settings(config)
    generation_context = (
        generation_settings.get("context") if isinstance(generation_settings.get("context"), dict) else {}
    )
    if generation_context.get("include_recent_chapters") is False:
        return []
    policy = config.get("context_policy") if isinstance(config.get("context_policy"), dict) else {}
    count = safe_int(
        generation_context.get("recent_confirmed_chapter_count"),
        default=safe_int(policy.get("recent_confirmed_chapter_count"), default=2),
    )
    if count <= 0:
        return []
    service = DraftGenerationService(store)
    entries = service.list_confirmed_chapters()
    selected_entries = recent_confirmed_entries(entries, chapter_id=chapter_id, count=count)
    candidates: list[dict[str, Any]] = []
    for index, entry in enumerate(selected_entries, start=1):
        confirmed_id = str(entry.get("chapter_id") or "")
        text = ""
        if confirmed_id:
            try:
                chapter = service.read_confirmed_chapter(confirmed_id)
            except Exception:
                chapter = {}
            text = str(chapter.get("content") or "") if isinstance(chapter, dict) else ""
        ready = bool(text.strip())
        public = {
            "source_type": "recent_confirmed_chapter",
            "source_id": confirmed_id or f"recent_chapter_{index}",
            "source_path": str(entry.get("path") or "data/confirmed_chapters"),
            "chapter_id": confirmed_id,
            "title": entry.get("title"),
            "category_id": "recent_chapters",
            "section_label": f"往前 {count} 章的上文",
            "section_order": 80,
            "priority": 80 + index,
            "memory_weight": 1.0,
            "estimated_tokens": ceil(len(text) / DEFAULT_CHARS_PER_TOKEN),
            "char_count": len(text),
            "text_status": "confirmed_chapter",
            "ready": ready,
            "enabled": True,
            "active": True,
            "contains_text": include_text and ready,
        }
        if include_text and ready:
            public["text"] = text
        candidates.append(public)
    return candidates


def recent_confirmed_entries(entries: list[dict[str, Any]], *, chapter_id: str, count: int) -> list[dict[str, Any]]:
    safe_entries = [item for item in entries if isinstance(item, dict)]
    if chapter_id:
        for index, item in enumerate(safe_entries):
            if item.get("chapter_id") == chapter_id:
                return safe_entries[max(index - count, 0) : index]
    return safe_entries[-count:]


def planning_library_package_candidates(
    store: ProjectStore,
    *,
    chapter_id: str = "",
    include_text: bool,
) -> list[dict[str, Any]]:
    raw = store.read_json(store.data_file_path("planning_library.json"), default={})
    library = normalize_library(raw)
    if library.get("enabled") is False:
        return []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(library["items"], start=1):
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("item_type") or "outline")
        text = str(item.get("text") or "")
        original_char_count = len(text)
        chapter_plan_extract_status = ""
        if item_type == "chapter_plan" and chapter_id:
            extracted = extract_target_chapter_plan(text, chapter_id)
            if extracted:
                text = extracted
                chapter_plan_extract_status = "target_chapter_extracted"
            else:
                chapter_plan_extract_status = "target_chapter_not_found_full_plan_used"
        enabled = item.get("enabled") if isinstance(item.get("enabled"), bool) else True
        active = bool(item.get("active"))
        send_mode = str(item.get("send_mode") or "reference_text")
        char_count = len(text) if send_mode == "reference_text" else 0
        ready = bool(active and enabled and char_count > 0)
        public = {
            "source_type": "planning_library",
            "source_id": planning_item_id(item) or f"planning_{index}",
            "source_path": "data/planning_library.json",
            "chapter_id": chapter_id if item_type == "chapter_plan" and chapter_plan_extract_status else "",
            "title": item.get("title"),
            "category_id": item_type,
            "section_label": planning_section_label(item_type),
            "section_order": planning_section_order(item_type),
            "priority": safe_int(item.get("priority"), default=10),
            "memory_weight": adherence_weight(str(item.get("adherence_level") or "balanced")),
            "estimated_tokens": ceil(char_count / DEFAULT_CHARS_PER_TOKEN),
            "char_count": char_count,
            "original_char_count": original_char_count,
            "chapter_plan_extract_status": chapter_plan_extract_status,
            "text_status": item.get("text_status"),
            "ready": ready,
            "enabled": enabled,
            "active": active,
            "adherence_level": item.get("adherence_level") or "balanced",
            "send_mode": send_mode,
            "contains_text": include_text and ready,
        }
        if include_text and ready:
            public["text"] = text
        candidates.append(public)
    return candidates


def planning_section_label(item_type: str) -> str:
    labels = {
        "outline": "用户提供的总纲",
        "beat_sheet": "用户提供的节拍表",
        "chapter_plan": "用户提供的目前章节大纲",
        "character_plan": "世界书和人物设定",
        "world_plan": "世界书和人物设定",
        "constraint": "写作约束",
        "other": "其他补充资料",
    }
    return labels.get(item_type, "其他补充资料")


def planning_section_order(item_type: str) -> int:
    order = {
        "outline": 10,
        "beat_sheet": 20,
        "chapter_plan": 30,
        "memory_bank": 40,
        "world_plan": 50,
        "character_plan": 50,
        "constraint": 70,
        "other": 90,
    }
    return order.get(item_type, 90)


def rendered_message(*, role: str, content: str, include_text: bool, label: str) -> dict[str, Any]:
    message = {
        "role": role,
        "label": label,
        "content_chars": len(content),
        "content_redacted": not include_text,
    }
    if include_text:
        message["content"] = content
    return message


def target_chapter_prompt(chapter_id: str) -> str:
    value = str(chapter_id or "").strip()
    if not value:
        return ""
    return (
        f"当前必须创作章节：{value}。\n"
        "只写这个目标章节的正文；不要跳到其他章节，不要提前使用后续章节事件。"
    )


CHAPTER_PLAN_HEADING_PATTERN = re.compile(
    r"(?m)^\s{0,3}#{1,6}\s*(?:章节|第)\s*(?P<number>[0-9]{1,4}|[一二三四五六七八九十两]+)\s*(?:章)?[：:、\s].*$"
)


def extract_target_chapter_plan(text: str, chapter_id: str) -> str:
    target = chapter_number_from_id(chapter_id)
    if target is None:
        return ""
    matches: list[tuple[int, int]] = []
    for match in CHAPTER_PLAN_HEADING_PATTERN.finditer(text):
        number = parse_chapter_number(match.group("number"))
        if number is not None:
            matches.append((match.start(), number))
    for index, (start, number) in enumerate(matches):
        if number != target:
            continue
        end = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        return text[start:end].strip()
    return ""


def chapter_number_from_id(chapter_id: str) -> int | None:
    match = re.search(r"(\d+)$", str(chapter_id or ""))
    if not match:
        return None
    return int(match.group(1))


def parse_chapter_number(value: str) -> int | None:
    value = value.strip()
    if value.isdigit():
        return int(value)
    return parse_chinese_number(value)


def parse_chinese_number(value: str) -> int | None:
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    value = value.strip()
    if not value:
        return None
    if value == "十":
        return 10
    if "十" in value:
        head, _, tail = value.partition("十")
        tens = digits.get(head, 1 if not head else 0)
        ones = digits.get(tail, 0) if tail else 0
        number = tens * 10 + ones
        return number if number > 0 else None
    return digits.get(value)


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


def disabled_skip_reason(item: dict[str, Any]) -> str:
    if item.get("source_type") == "planning_library":
        return "planning_item_disabled"
    return "memory_item_disabled"


def missing_text_skip_reason(item: dict[str, Any]) -> str:
    if item.get("source_type") == "planning_library":
        if item.get("send_mode") == "metadata_only":
            return "planning_item_metadata_only"
        return "planning_text_missing"
    return "manual_text_missing"


def adherence_weight(value: str) -> float:
    if value == "strict":
        return 1.15
    if value == "soft":
        return 0.85
    return 1.0


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


def selected_recent_chapter_count(sections: list[dict[str, Any]]) -> int:
    return sum(1 for item in sections if isinstance(item, dict) and item.get("source_type") == "recent_confirmed_chapter")


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
