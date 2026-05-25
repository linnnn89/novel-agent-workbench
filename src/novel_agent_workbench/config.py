from __future__ import annotations

from copy import deepcopy
from typing import Any


CURRENT_CONFIG_SCHEMA_VERSION = 4
GLOBAL_SETTINGS_SCHEMA_VERSION = 1
GENERATION_SETTINGS_SCOPE_GLOBAL = "global_fallback"
GENERATION_SETTINGS_SCOPE_PROJECT = "project_override"

DEFAULT_WRITER_SYSTEM_PROMPT = """你是一个专业小说创作助手，擅长长篇小说的连续性、节奏控制、人物一致性和场景推进。
请严格遵守用户提供的总纲、章节计划、世界观、人物设定和上下文记忆。
如果某一类资料没有提供，不要编造该类资料，也不要在正文中解释资料缺失。
输出只写小说正文，不要写分析过程、提纲说明、免责声明或 <think> 内容。"""

DEFAULT_DRAFT_USER_PROMPT = """请根据以下资料继续创作当前章节。
要求：保持人物动机一致，承接前文，优先推进场景和冲突；不要复述设定，不要写成总结。"""

DEFAULT_REVIEW_SYSTEM_PROMPT = (
    "你是一名专业长篇小说审稿编辑。你只输出审稿意见，不续写正文，不暴露推理过程，不输出 <think>。"
)

LEGACY_REVIEW_TASK_PROMPT = """请审稿当前章节：{chapter_heading}。
请根据已提供的总纲、章节计划、人物/世界观资料、上下文记忆和前文，审查当前草稿。
重点检查：剧情连续性、人物动机一致性、场景推进、设定冲突、节奏、可读性、需要保留的亮点。
输出结构：总体判断、主要问题、逐条修改建议、可直接用于精修的指令。
不要重写正文，不要输出免责声明，不要输出 <think>。"""

DEFAULT_REVIEW_TASK_PROMPT = """请审稿当前章节：{chapter_heading}。
你要审查的是“本小说当前草稿”，不是原作设定考据，也不是续写正文。
请以已提供的总纲、章节计划、人物设定、世界观、上下文记忆、前文和本章目标为最高优先级；这些资料共同构成**本小说的人设与规则**。

如果这是同人小说：角色性格、经历、关系和动机允许与原作不同。不得因为“不像原作”判定为人设错误；只有在草稿明显违背**本小说已经给出的设定、前文事实或本章目标**时，才指出人物性格/动机问题。

重点检查：
1. 剧情连续性：是否承接前文与章节计划，是否出现事实矛盾。
2. 人物动机：是否符合本小说已建立的人设、关系、目标和当前情境。
3. 场景推进：本章是否有有效行动、冲突推进或信息变化。
4. 设定冲突：是否与本小说世界观、能力规则、阵营关系冲突。
5. 节奏与可读性：是否拖沓、跳跃、重复解释或缺少情绪落点。
6. 需要保留的亮点：指出不应误删的桥段、氛围、伏笔或人物反应。

输出结构：
1. 总体判断。
2. 主要问题：只列真正影响本小说一致性或阅读体验的问题；不要用原作差异作为打回理由。
3. 逐条修改建议：说明为什么要改、改到什么方向。
4. 可直接用于精修的指令。

不要重写正文，不要输出免责声明，不要输出 <think>。"""

FORMAL_CONTEXT_PRIORITY_ORDER = [
    "world_building",
    "character_relationships",
    "chapter_summary",
    "style_memory",
    "foreshadowing",
]

DATA_FILE_DEFAULTS: dict[str, Any] = {
    "planning_library.json": {
        "schema_version": 1,
        "enabled": True,
        "active_reference_ids": [],
        "items": [],
    },
    "memory_bank.json": {
        "schema_version": 1,
        "enabled": False,
        "updated_to_chapter": 0,
        "items": [],
    },
    "scoring_profile.json": {
        "schema_version": 1,
        "enabled": False,
        "profiles": [],
        "active_profile_id": None,
    },
    "revision_policy.json": {
        "schema_version": 1,
        "enabled": False,
        "max_revision_rounds": 0,
        "pause_on_hard_fail": True,
    },
    "export_settings.json": {
        "schema_version": 1,
        "txt_enabled": True,
        "zip_enabled": True,
        "docx_enabled": False,
        "export_scope": "confirmed_only",
    },
}


def default_project_config() -> dict[str, Any]:
    return {
        "schema_version": CURRENT_CONFIG_SCHEMA_VERSION,
        "model_roles": {
            "writer": default_model_role("writer"),
            "scorer": default_model_role("scorer"),
            "reviser": default_model_role("reviser"),
        },
        "workflow_presets": [
            {
                "id": "classic_direct",
                "name": "Classic Direct",
                "save_as_draft": False,
                "auto_confirm_after_generation": True,
                "auto_score_after_generation": False,
                "auto_revise_enabled": False,
                "memory_bank_enabled": False,
            },
            {
                "id": "manual_studio",
                "name": "Manual Studio",
                "save_as_draft": True,
                "auto_confirm_after_generation": False,
                "require_user_confirm": True,
                "output_guard_enabled": True,
                "manual_revise_enabled": True,
                "auto_revise_enabled": False,
                "auto_score_after_generation": False,
            },
            {
                "id": "auto_pipeline",
                "name": "Auto Pipeline",
                "save_as_draft": True,
                "auto_score_after_generation": True,
                "auto_revise_enabled": True,
                "max_revision_rounds": 3,
                "auto_confirm_after_score_passed": True,
                "pause_on_hard_fail": True,
            },
        ],
        "active_workflow_preset_id": "manual_studio",
        "generation_settings_scope": GENERATION_SETTINGS_SCOPE_GLOBAL,
        "generation_settings": default_generation_settings(),
        "context_policy": {
            "recent_confirmed_chapter_count": 2,
            "planning_library_enabled": True,
            "memory_bank_enabled": False,
            "world_book_enabled": False,
            "max_context_tokens": 32768,
            "formal_context_policy": default_formal_context_policy(),
            "style_check_policy": default_style_check_policy(),
        },
    }


def default_generation_settings() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "prompting": {
            "system_prompt": DEFAULT_WRITER_SYSTEM_PROMPT,
            "default_user_prompt": DEFAULT_DRAFT_USER_PROMPT,
            "skip_empty_sections": True,
            "section_format": "chinese_labeled_blocks",
        },
        "sampling": {
            "temperature": 0.75,
            "top_p": 0.9,
            "top_k": 40,
            "min_p": None,
            "max_tokens": 4096,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "repetition_penalty": 1.05,
            "stream": False,
        },
        "context": {
            "max_context_tokens": 32768,
            "recent_confirmed_chapter_count": 2,
            "include_planning_library": True,
            "include_memory_bank": True,
            "include_world_and_character": True,
            "include_recent_chapters": True,
        },
        "review": {
            "scorer_enabled": False,
            "manual_review_when_disabled": True,
            "system_prompt": DEFAULT_REVIEW_SYSTEM_PROMPT,
            "task_prompt": DEFAULT_REVIEW_TASK_PROMPT,
        },
    }


def default_global_settings() -> dict[str, Any]:
    return {
        "schema_version": GLOBAL_SETTINGS_SCHEMA_VERSION,
        "generation_settings": default_generation_settings(),
    }


def effective_generation_settings(config: object) -> dict[str, Any]:
    source = config if isinstance(config, dict) else {}
    return migrate_generation_settings(deep_merge(default_generation_settings(), source.get("generation_settings")))


def project_generation_settings_override(config: object) -> dict[str, Any] | None:
    source = config if isinstance(config, dict) else {}
    scope = str(source.get("generation_settings_scope") or "")
    if scope == GENERATION_SETTINGS_SCOPE_GLOBAL:
        return None
    if scope == GENERATION_SETTINGS_SCOPE_PROJECT:
        return effective_generation_settings(source)
    if _legacy_generation_settings_is_custom(source):
        return effective_generation_settings(source)
    return None


def effective_layered_generation_settings(global_settings: object, project_config: object) -> dict[str, Any]:
    global_effective = deep_merge(default_generation_settings(), global_settings)
    global_effective = migrate_generation_settings(global_effective)
    project_override = project_generation_settings_override(project_config)
    if project_override is None:
        return global_effective
    return migrate_generation_settings(deep_merge(global_effective, project_override))


def project_has_generation_settings_override(config: object) -> bool:
    return project_generation_settings_override(config) is not None


def default_formal_context_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "manual_preview_first",
        "priority_order": list(FORMAL_CONTEXT_PRIORITY_ORDER),
        "categories": {
            "world_building": {
                "label": "World Building",
                "target": "memory_bank",
                "enabled": True,
                "auto_extract": False,
                "memory_weight": 1.0,
                "world_book_overlap_policy": "reduce_memory_when_world_book_enabled",
                "world_book_enabled_memory_weight": 0.35,
            },
            "character_relationships": {
                "label": "Character Relationships",
                "target": "memory_bank",
                "enabled": True,
                "auto_extract": False,
            },
            "chapter_summary": {
                "label": "Chapter Summary",
                "target": "memory_bank",
                "enabled": True,
                "auto_extract": False,
            },
            "style_memory": {
                "label": "Style Memory",
                "target": "memory_bank",
                "enabled": True,
                "auto_extract": False,
            },
            "foreshadowing": {
                "label": "Foreshadowing",
                "target": "memory_bank",
                "enabled": True,
                "auto_extract": False,
            },
        },
    }


def default_style_check_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "enabled": True,
        "calibration_enabled": True,
        "show_hints": True,
        "default_scene_mode": "general",
        "severity_mode": "hint_first",
        "auto_create_revision_request": False,
        "ui_placement": {
            "primary_surface": "draft_review_side_panel",
            "settings_surface": "project_settings_writing_quality",
            "modal_recommended": False,
        },
    }


def default_model_role(role: str) -> dict[str, Any]:
    return {
        "role": role,
        "provider": "",
        "model": "",
        "base_url": "",
        "api_key_ref": "",
        "settings": {
            "temperature": None,
            "top_p": None,
            "top_k": None,
            "min_p": None,
            "max_tokens": None,
            "context_tokens": None,
            "presence_penalty": None,
            "frequency_penalty": None,
            "repetition_penalty": None,
            "stream": None,
            "timeout_seconds": 300,
        },
    }


def default_data_file(name: str) -> Any:
    return deepcopy(DATA_FILE_DEFAULTS[name])


def merge_project_config(raw: object) -> tuple[dict[str, Any], bool]:
    source = raw if isinstance(raw, dict) else {}
    merged = deep_merge(default_project_config(), source)
    if "generation_settings_scope" not in source:
        merged["generation_settings_scope"] = (
            GENERATION_SETTINGS_SCOPE_PROJECT
            if _legacy_generation_settings_is_custom(source)
            else GENERATION_SETTINGS_SCOPE_GLOBAL
        )
    merged["schema_version"] = CURRENT_CONFIG_SCHEMA_VERSION
    changed = merged != source
    return merged, changed


def _legacy_generation_settings_is_custom(source: dict[str, Any]) -> bool:
    if not isinstance(source.get("generation_settings"), dict):
        return False
    return effective_generation_settings(source) != default_generation_settings()


def deep_merge(default: Any, override: Any) -> Any:
    if isinstance(default, dict) and isinstance(override, dict):
        result = deepcopy(default)
        for key, value in override.items():
            if key in result:
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    return deepcopy(override) if override is not None else deepcopy(default)


def migrate_generation_settings(settings: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(settings)
    review = migrated.get("review") if isinstance(migrated.get("review"), dict) else {}
    task_prompt = str(review.get("task_prompt") or "").strip()
    if not task_prompt or task_prompt == LEGACY_REVIEW_TASK_PROMPT:
        review["task_prompt"] = DEFAULT_REVIEW_TASK_PROMPT
    migrated["review"] = review
    return migrated
