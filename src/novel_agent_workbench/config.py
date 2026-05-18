from __future__ import annotations

from copy import deepcopy
from typing import Any


CURRENT_CONFIG_SCHEMA_VERSION = 2

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
        "context_policy": {
            "recent_confirmed_chapter_count": 3,
            "planning_library_enabled": True,
            "memory_bank_enabled": False,
            "world_book_enabled": False,
            "max_context_tokens": 32768,
            "formal_context_policy": default_formal_context_policy(),
        },
    }


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
            "max_tokens": None,
            "context_tokens": None,
            "stream": None,
        },
    }


def default_data_file(name: str) -> Any:
    return deepcopy(DATA_FILE_DEFAULTS[name])


def merge_project_config(raw: object) -> tuple[dict[str, Any], bool]:
    source = raw if isinstance(raw, dict) else {}
    merged = deep_merge(default_project_config(), source)
    merged["schema_version"] = CURRENT_CONFIG_SCHEMA_VERSION
    changed = merged != source
    return merged, changed


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
