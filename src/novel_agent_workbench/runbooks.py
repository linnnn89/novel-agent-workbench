from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .audit import audit_project
from .drafts import DraftGenerationError, DraftGenerationRequest, DraftGenerationService
from .providers import (
    CHUTES_PROVIDER_ID,
    REAL_GENERATION_BLOCKING_AUDIT_CODES,
    ProviderConfigError,
    ProviderError,
    configure_provider_role,
    validate_secret_name,
)
from .storage import ProjectStore, atomic_write_json_file


DEFAULT_CHUTES_BASE_URL = "https://llm.chutes.ai/v1"
DEFAULT_CHUTES_MODEL = "Qwen/Qwen3-32B-TEE"


@dataclass(frozen=True, slots=True)
class ChutesGenerateOnceRequest:
    chapter_id: str
    prompt: str
    title: str = ""
    system_prompt: str = ""
    model: str = DEFAULT_CHUTES_MODEL
    base_url: str = DEFAULT_CHUTES_BASE_URL
    secret_name: str = "chutes_key"
    secret_value: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    clear_secret_after_run: bool = True


def chutes_generate_once(store: ProjectStore, request: ChutesGenerateOnceRequest) -> dict[str, Any]:
    """Run the controlled Chutes draft-generation workflow with metadata-only output."""

    store.initialize()
    secret_name = validate_secret_name(request.secret_name)
    run_summary: dict[str, Any] = {
        "status": "pending",
        "project_id": store.project_id,
        "role": "writer",
        "provider": CHUTES_PROVIDER_ID,
        "model": request.model,
        "base_url_host": "llm.chutes.ai" if request.base_url == DEFAULT_CHUTES_BASE_URL else safe_host_label(request.base_url),
        "chapter_id": request.chapter_id,
        "steps": [],
        "draft": None,
        "error_type": "",
        "message": "",
        "secret": {"name": secret_name, "provided": bool(request.secret_value), "cleared": False, "has_value_after": False},
        "audits": {},
        "side_effects": {},
    }
    append_step(run_summary, "audit_precheck", "started")
    precheck = audit_project(store)
    run_summary["audits"]["precheck"] = audit_summary(precheck)
    blocking_codes = blocking_audit_codes(precheck)
    if blocking_codes:
        append_step(run_summary, "audit_precheck", "blocked", {"blocking_codes": blocking_codes})
        return error_summary(run_summary, "audit_gate_failed", f"Audit gate failed before runbook: {', '.join(blocking_codes)}")
    append_step(run_summary, "audit_precheck", "ok")

    try:
        append_step(run_summary, "configure_secret", "started")
        if request.secret_value:
            set_project_secret_no_backup(store, secret_name, request.secret_value)
        append_step(run_summary, "configure_secret", "ok", {"provided": bool(request.secret_value)})

        append_step(run_summary, "configure_provider", "started")
        configure_provider_role(
            store,
            "writer",
            provider=CHUTES_PROVIDER_ID,
            model=request.model,
            api_key_ref=f"project_secret.{secret_name}",
            base_url=request.base_url,
        )
        append_step(run_summary, "configure_provider", "ok")

        if not str(store.read_secrets().get(secret_name) or ""):
            return error_summary(run_summary, "missing_secret", "Chutes secret is missing or empty.")

        append_step(run_summary, "generate_draft", "started")
        draft = DraftGenerationService(store).generate_draft(
            DraftGenerationRequest(
                chapter_id=request.chapter_id,
                title=request.title,
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                metadata={"runbook": "chutes_generate_once"},
            )
        )
        run_summary["draft"] = draft.to_dict()
        append_step(run_summary, "generate_draft", "ok")
        run_summary["status"] = "ok"
        run_summary["message"] = "Chutes draft generated. Content is available only through read-draft."
        return run_summary
    except (ProviderError, ProviderConfigError, DraftGenerationError) as exc:
        error_type = getattr(exc, "error_type", exc.__class__.__name__)
        return error_summary(run_summary, str(error_type), str(exc))
    finally:
        if request.clear_secret_after_run:
            append_step(run_summary, "clear_secret", "started")
            clear_project_secret_no_backup(store, secret_name)
            run_summary["secret"]["cleared"] = True
            append_step(run_summary, "clear_secret", "ok")
        run_summary["secret"]["has_value_after"] = bool(str(store.read_secrets().get(secret_name) or ""))
        postcheck = audit_project(store)
        run_summary["audits"]["postcheck"] = audit_summary(postcheck)
        service = DraftGenerationService(store)
        run_summary["side_effects"] = {
            "draft_count": len(service.list_drafts()),
            "confirmed_chapter_count": len(service.list_confirmed_chapters()),
            "exports_exists": (store.root / "exports").exists(),
            "rag_exists": (store.data_dir / "rag").exists(),
        }


def set_project_secret_no_backup(store: ProjectStore, name: str, value: str) -> None:
    secret_name = validate_secret_name(name)
    if not isinstance(value, str) or not value:
        raise ProviderConfigError("secret value cannot be empty.")
    secrets = store.read_secrets()
    secrets[secret_name] = value
    atomic_write_json_file(store.secrets_path, secrets)


def clear_project_secret_no_backup(store: ProjectStore, name: str) -> None:
    secret_name = validate_secret_name(name)
    secrets = store.read_secrets()
    if secret_name in secrets:
        secrets.pop(secret_name)
    atomic_write_json_file(store.secrets_path, secrets)


def append_step(summary: dict[str, Any], name: str, status: str, extra: dict[str, Any] | None = None) -> None:
    entry = {"name": name, "status": status}
    if extra:
        entry.update(extra)
    summary["steps"].append(entry)


def error_summary(summary: dict[str, Any], error_type: str, message: str) -> dict[str, Any]:
    summary["status"] = "error"
    summary["error_type"] = error_type
    summary["message"] = message
    return summary


def audit_summary(result: dict[str, Any]) -> dict[str, Any]:
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    codes = sorted({str(item.get("code")) for item in findings if isinstance(item, dict)})
    return {"ok": bool(result.get("ok")), "finding_count": len(findings), "codes": codes}


def blocking_audit_codes(result: dict[str, Any]) -> list[str]:
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    return sorted(
        {
            str(item.get("code"))
            for item in findings
            if isinstance(item, dict) and str(item.get("code")) in REAL_GENERATION_BLOCKING_AUDIT_CODES
        }
    )


def safe_host_label(base_url: str) -> str:
    from .providers import safe_url_host

    return safe_url_host(base_url)
