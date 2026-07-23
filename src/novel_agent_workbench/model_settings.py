from __future__ import annotations

from copy import deepcopy
from typing import Any


MODEL_SETTINGS_SCHEMA_VERSION = 2

FEATURE_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("draft_generation", "正文生成", "writer"),
    ("ai_review", "AI 审稿", "scorer"),
    ("ai_refinement", "AI 精修", "reviser"),
    ("memory_generation", "记忆生成", "writer"),
    ("memory_compression", "记忆压缩", "writer"),
)
FEATURE_IDS = {item[0] for item in FEATURE_DEFINITIONS}
ROLE_DEFAULT_FEATURE = {
    "writer": "draft_generation",
    "scorer": "ai_review",
    "reviser": "ai_refinement",
}

BUILTIN_PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "siliconflow": {
        "profile_id": "siliconflow",
        "display_name": "硅基流动",
        "adapter": "siliconflow",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key_ref": "project_secret.provider_siliconflow_api_key",
        "timeout_seconds": 300.0,
        "enabled": True,
        "built_in": True,
    },
    "chutes": {
        "profile_id": "chutes",
        "display_name": "Chutes",
        "adapter": "chutes_openai",
        "base_url": "https://llm.chutes.ai/v1",
        "api_key_ref": "project_secret.provider_chutes_api_key",
        "timeout_seconds": 300.0,
        "enabled": True,
        "built_in": True,
    },
    "openrouter": {
        "profile_id": "openrouter",
        "display_name": "OpenRouter",
        "adapter": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_ref": "project_secret.provider_openrouter_api_key",
        "timeout_seconds": 300.0,
        "enabled": True,
        "built_in": True,
    },
}


def default_model_settings_fields() -> dict[str, Any]:
    return {
        "provider_profiles": deepcopy(BUILTIN_PROVIDER_PROFILES),
        "model_profiles": {},
        "primary_model_ref": "",
        "feature_assignments": {
            feature_id: {"mode": "inherit", "model_ref": ""}
            for feature_id, _label, _role in FEATURE_DEFINITIONS
        },
    }


def make_model_ref(profile_id: str, model_id: str) -> str:
    profile = str(profile_id or "").strip()
    model = str(model_id or "").strip()
    if not profile or not model:
        return ""
    return f"{profile}::{model}"


def split_model_ref(model_ref: str) -> tuple[str, str]:
    value = str(model_ref or "")
    if "::" not in value:
        return "", ""
    profile_id, model_id = value.split("::", 1)
    return profile_id.strip(), model_id.strip()


def normalize_provider_profile(profile_id: str, value: object) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    builtin = BUILTIN_PROVIDER_PROFILES.get(profile_id, {})
    merged = {**deepcopy(builtin), **source}
    merged["profile_id"] = profile_id
    merged["display_name"] = str(merged.get("display_name") or profile_id).strip()
    merged["adapter"] = str(merged.get("adapter") or "openai_compatible").strip()
    merged["base_url"] = str(merged.get("base_url") or "").strip().rstrip("/")
    merged["api_key_ref"] = str(merged.get("api_key_ref") or "").strip()
    try:
        timeout = float(merged.get("timeout_seconds") or 300.0)
    except (TypeError, ValueError):
        timeout = 300.0
    merged["timeout_seconds"] = min(900.0, max(1.0, timeout))
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["built_in"] = bool(builtin) or bool(merged.get("built_in"))
    return merged


def normalize_model_profile(model_ref: str, value: object) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    ref_profile_id, ref_model_id = split_model_ref(model_ref)
    profile_id = str(source.get("provider_profile_id") or ref_profile_id).strip()
    model_id = str(source.get("model_id") or ref_model_id).strip()
    return {
        **source,
        "model_ref": make_model_ref(profile_id, model_id),
        "provider_profile_id": profile_id,
        "model_id": model_id,
        "display_name": str(source.get("display_name") or model_id).strip(),
        "source": str(source.get("source") or "manual").strip(),
        "enabled": bool(source.get("enabled", True)),
    }


def migrate_global_model_settings(value: object) -> tuple[dict[str, Any], bool]:
    """Return schema-v2 settings while preserving legacy model_roles verbatim."""
    source = deepcopy(value) if isinstance(value, dict) else {}
    changed = int(source.get("schema_version") or 0) < MODEL_SETTINGS_SCHEMA_VERSION
    defaults = default_model_settings_fields()

    raw_profiles = source.get("provider_profiles")
    profiles: dict[str, dict[str, Any]] = deepcopy(BUILTIN_PROVIDER_PROFILES)
    if isinstance(raw_profiles, dict):
        for profile_id, profile in raw_profiles.items():
            clean_id = str(profile_id or "").strip()
            if clean_id:
                profiles[clean_id] = normalize_provider_profile(clean_id, profile)

    raw_models = source.get("model_profiles")
    models: dict[str, dict[str, Any]] = {}
    if isinstance(raw_models, dict):
        for model_ref, model in raw_models.items():
            normalized = normalize_model_profile(str(model_ref), model)
            if normalized["model_ref"]:
                models[normalized["model_ref"]] = normalized

    assignments = deepcopy(defaults["feature_assignments"])
    raw_assignments = source.get("feature_assignments")
    if isinstance(raw_assignments, dict):
        for feature_id in FEATURE_IDS:
            item = raw_assignments.get(feature_id)
            if isinstance(item, dict):
                mode = "model" if str(item.get("mode")) == "model" else "inherit"
                assignments[feature_id] = {
                    "mode": mode,
                    "model_ref": str(item.get("model_ref") or "").strip() if mode == "model" else "",
                }

    primary_model_ref = str(source.get("primary_model_ref") or "").strip()
    roles = source.get("model_roles") if isinstance(source.get("model_roles"), dict) else {}
    if not raw_profiles and roles:
        signature_profiles: dict[tuple[str, str, str], str] = {}
        for role in ("writer", "scorer", "reviser"):
            role_value = roles.get(role) if isinstance(roles.get(role), dict) else {}
            adapter = str(role_value.get("provider") or "").strip()
            model_id = str(role_value.get("model") or "").strip()
            if not adapter or not model_id:
                continue
            base_url = str(role_value.get("base_url") or "").strip().rstrip("/")
            api_key_ref = str(role_value.get("api_key_ref") or "").strip()
            signature = (adapter, base_url, api_key_ref)
            profile_id = signature_profiles.get(signature, "")
            if not profile_id:
                preferred_id = {
                    "siliconflow": "siliconflow",
                    "chutes_openai": "chutes",
                    "openrouter": "openrouter",
                }.get(adapter, "")
                preferred_base = str(profiles.get(preferred_id, {}).get("base_url") or "").rstrip("/")
                if (
                    preferred_id
                    and preferred_id not in signature_profiles.values()
                    and (not preferred_base or preferred_base == base_url)
                ):
                    profile_id = preferred_id
                else:
                    stem = preferred_id or f"migrated_{adapter or 'provider'}"
                    profile_id = stem
                    suffix = 2
                    while profile_id in profiles and (
                        str(profiles[profile_id].get("base_url") or "") != base_url
                        or str(profiles[profile_id].get("api_key_ref") or "") != api_key_ref
                    ):
                        profile_id = f"{stem}_{suffix}"
                        suffix += 1
                display_name = profiles.get(profile_id, {}).get("display_name") or adapter
                profiles[profile_id] = normalize_provider_profile(
                    profile_id,
                    {
                        "display_name": display_name,
                        "adapter": adapter,
                        "base_url": base_url,
                        "api_key_ref": api_key_ref,
                        "timeout_seconds": (role_value.get("settings") or {}).get("timeout_seconds", 300.0)
                        if isinstance(role_value.get("settings"), dict)
                        else 300.0,
                        "built_in": profile_id in BUILTIN_PROVIDER_PROFILES,
                    },
                )
                signature_profiles[signature] = profile_id
            model_ref = make_model_ref(profile_id, model_id)
            models[model_ref] = normalize_model_profile(
                model_ref,
                {
                    "display_name": model_id,
                    "source": "migrated",
                    "enabled": True,
                },
            )
            feature_id = ROLE_DEFAULT_FEATURE[role]
            if role == "writer":
                primary_model_ref = primary_model_ref or model_ref
            elif model_ref != primary_model_ref:
                assignments[feature_id] = {"mode": "model", "model_ref": model_ref}

    source["schema_version"] = MODEL_SETTINGS_SCHEMA_VERSION
    source["provider_profiles"] = {
        profile_id: normalize_provider_profile(profile_id, profile)
        for profile_id, profile in profiles.items()
    }
    source["model_profiles"] = models
    source["primary_model_ref"] = primary_model_ref
    source["feature_assignments"] = assignments
    return source, changed


def effective_model_ref(settings: object, feature_id: str = "", role: str = "writer") -> str:
    source = settings if isinstance(settings, dict) else {}
    resolved_feature = feature_id if feature_id in FEATURE_IDS else ROLE_DEFAULT_FEATURE.get(role, "draft_generation")
    assignments = source.get("feature_assignments") if isinstance(source.get("feature_assignments"), dict) else {}
    assignment = assignments.get(resolved_feature) if isinstance(assignments.get(resolved_feature), dict) else {}
    if str(assignment.get("mode") or "") == "model":
        explicit = str(assignment.get("model_ref") or "").strip()
        if explicit:
            return explicit
    return str(source.get("primary_model_ref") or "").strip()


def resolve_model_role_mapping(
    settings: object,
    *,
    role: str,
    feature_id: str = "",
) -> dict[str, Any] | None:
    source = settings if isinstance(settings, dict) else {}
    model_ref = effective_model_ref(source, feature_id, role)
    models = source.get("model_profiles") if isinstance(source.get("model_profiles"), dict) else {}
    model = models.get(model_ref) if isinstance(models.get(model_ref), dict) else None
    if not model or not bool(model.get("enabled", True)):
        return None
    profile_id = str(model.get("provider_profile_id") or split_model_ref(model_ref)[0]).strip()
    profiles = source.get("provider_profiles") if isinstance(source.get("provider_profiles"), dict) else {}
    profile = profiles.get(profile_id) if isinstance(profiles.get(profile_id), dict) else None
    if not profile or not bool(profile.get("enabled", True)):
        return None
    return {
        "role": role,
        "provider": str(profile.get("adapter") or "openai_compatible"),
        "model": str(model.get("model_id") or split_model_ref(model_ref)[1]),
        "base_url": str(profile.get("base_url") or ""),
        "api_key_ref": str(profile.get("api_key_ref") or ""),
        "settings": {"timeout_seconds": profile.get("timeout_seconds", 300.0)},
    }


def sync_legacy_model_roles(settings: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(settings)
    existing = result.get("model_roles") if isinstance(result.get("model_roles"), dict) else {}
    roles: dict[str, Any] = dict(existing)
    for role, feature_id in ROLE_DEFAULT_FEATURE.items():
        resolved = resolve_model_role_mapping(result, role=role, feature_id=feature_id)
        if resolved:
            roles[role] = resolved
        elif int(result.get("schema_version") or 0) >= MODEL_SETTINGS_SCHEMA_VERSION:
            roles[role] = {
                "role": role,
                "provider": "",
                "model": "",
                "base_url": "",
                "api_key_ref": "",
                "settings": {},
            }
    result["model_roles"] = roles
    return result
