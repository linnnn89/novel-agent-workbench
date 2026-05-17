from __future__ import annotations

from typing import Any

from .chapters import ChapterWorkflowService
from .drafts import DraftGenerationService
from .providers import MODEL_ROLES, REAL_GENERATION_FLAG, ProviderConfigError, get_model_role_config
from .storage import ProjectStore


def public_project_state(store: ProjectStore, *, initialize: bool = True) -> dict[str, Any]:
    """Return a UI-safe project summary without prompt, content, or plaintext secrets."""

    if initialize:
        store.initialize()
    draft_service = DraftGenerationService(store)
    chapter_service = ChapterWorkflowService(store)
    drafts = draft_service.list_drafts()
    confirmed = draft_service.list_confirmed_chapters()
    chapters = chapter_service.list_chapters()
    store_state = store.public_state()
    config = store_state.get("config") if isinstance(store_state.get("config"), dict) else {}
    return {
        "project_id": store.project_id,
        "config": {
            "schema_version": config.get("schema_version"),
            "active_workflow_preset_id": config.get("active_workflow_preset_id"),
            "context_policy": config.get("context_policy") if isinstance(config.get("context_policy"), dict) else {},
        },
        "secrets": store_state.get("secrets", {}),
        "draft_count": len(drafts),
        "chapter_count": len(chapters),
        "committed_chapter_count": len(confirmed),
        "latest_chapter": safe_chapter_summary(latest_by(chapters, "updated_at")),
        "latest_draft": safe_draft_summary(latest_by(drafts, "created_at")),
        "latest_committed_chapter": safe_confirmed_summary(latest_by(confirmed, "committed_at")),
        "provider_roles": provider_roles_summary(store),
    }


def provider_roles_summary(store: ProjectStore) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    public_secrets = store.public_state().get("secrets", {})
    for role in sorted(MODEL_ROLES):
        role_config = get_model_role_config(store, role)
        config_error = ""
        try:
            secret_name = role_config.secret_name() if role_config.api_key_ref else ""
        except ProviderConfigError as exc:
            secret_name = ""
            config_error = str(exc)
        secret_state = public_secrets.get(secret_name) if isinstance(public_secrets, dict) and secret_name else {}
        summary[role] = {
            "configured": role_config.is_configured(),
            "provider": role_config.provider,
            "model": role_config.model,
            "has_api_key": bool(secret_state.get("has_value")) if isinstance(secret_state, dict) else False,
            "masked_key": str(secret_state.get("masked") or "") if isinstance(secret_state, dict) else "",
            "real_generation_enabled": bool(role_config.settings.get(REAL_GENERATION_FLAG)),
            "config_error": config_error,
        }
    return summary


def latest_by(items: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    if not items:
        return None
    return max(items, key=lambda item: str(item.get(key) or ""))


def safe_draft_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "draft_id": item.get("draft_id"),
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "committed_at": item.get("committed_at"),
        "committed_chapter_id": item.get("committed_chapter_id"),
        "provider": item.get("provider"),
        "model": item.get("model"),
    }


def safe_confirmed_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "source_draft_id": item.get("source_draft_id"),
        "committed_at": item.get("committed_at"),
        "provider": item.get("provider"),
        "model": item.get("model"),
        "usage": item.get("usage") if isinstance(item.get("usage"), dict) else {},
    }


def safe_chapter_summary(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "chapter_id": item.get("chapter_id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "latest_draft_id": item.get("latest_draft_id"),
        "confirmed_chapter_id": item.get("confirmed_chapter_id"),
        "updated_at": item.get("updated_at"),
        "error_summary": item.get("error_summary") if isinstance(item.get("error_summary"), dict) else {},
    }
