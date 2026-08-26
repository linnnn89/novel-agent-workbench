from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .audit import audit_project
from .project_state import public_project_state
from .publication import REQUIRED_GITIGNORE_PATTERNS, prepublish_check, project_audit_severity
from .storage import ProjectStore, utc_stamp


@dataclass(frozen=True, slots=True)
class ProjectHealthResult:
    project_id: str
    generated_at: str
    status: str
    next_gate: str
    summary: dict[str, Any]
    provider: dict[str, Any]
    drafts: dict[str, Any]
    smoke_tests: dict[str, Any]
    audit: dict[str, Any]
    upload_readiness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_health(store: ProjectStore, *, repo_root: str | Path | None = None) -> ProjectHealthResult:
    """Return a compact metadata-only health summary for operators."""

    store.initialize()
    state = public_project_state(store)
    audit = audit_project(store)
    audit_summary = summarize_audit(audit)
    upload_summary = summarize_upload_readiness(store, repo_root=repo_root)
    status = health_status(audit_summary, upload_summary)
    return ProjectHealthResult(
        project_id=store.project_id,
        generated_at=utc_stamp(),
        status=status,
        next_gate=next_gate(status),
        summary={
            "chapter_count": state.get("chapter_count"),
            "draft_count": state.get("draft_count"),
            "review_count": state.get("review_count"),
            "committed_chapter_count": state.get("committed_chapter_count"),
            "provider_smoke_test_count": state.get("provider_smoke_test_count"),
        },
        provider=summarize_provider(state),
        drafts=summarize_drafts(state),
        smoke_tests=summarize_smoke_tests(state, audit_summary),
        audit=audit_summary,
        upload_readiness=upload_summary,
    )


def summarize_provider(state: dict[str, Any]) -> dict[str, Any]:
    roles = state.get("provider_roles") if isinstance(state.get("provider_roles"), dict) else {}
    summary: dict[str, dict[str, Any]] = {}
    for role in ("writer", "scorer", "reviser"):
        role_state = roles.get(role) if isinstance(roles.get(role), dict) else {}
        summary[role] = {
            "configured": bool(role_state.get("configured")),
            "provider": role_state.get("provider") or "",
            "model": role_state.get("model") or "",
            "base_url_host": role_state.get("base_url_host") or "",
            "api_key_ref": role_state.get("api_key_ref") or "",
            "has_api_key": bool(role_state.get("has_api_key")),
            "config_error": role_state.get("config_error") or "",
        }
    return summary


def summarize_drafts(state: dict[str, Any]) -> dict[str, Any]:
    latest_chapter = state.get("latest_chapter") if isinstance(state.get("latest_chapter"), dict) else {}
    latest_draft = state.get("latest_draft") if isinstance(state.get("latest_draft"), dict) else {}
    latest_review = state.get("latest_review") if isinstance(state.get("latest_review"), dict) else {}
    latest_decision = latest_chapter.get("latest_review_decision") if isinstance(latest_chapter.get("latest_review_decision"), dict) else {}
    return {
        "count": state.get("draft_count"),
        "committed_chapter_count": state.get("committed_chapter_count"),
        "latest_draft_id": latest_draft.get("draft_id") or "",
        "latest_draft_status": latest_draft.get("status") or "",
        "latest_chapter_status": latest_chapter.get("status") or "",
        "latest_review_id": latest_review.get("review_id") or "",
        "latest_review_decision": latest_decision.get("decision") or "",
        "latest_review_reason_code": latest_decision.get("reason_code") or "",
    }


def summarize_smoke_tests(state: dict[str, Any], audit_summary: dict[str, Any]) -> dict[str, Any]:
    latest = state.get("latest_provider_smoke_test") if isinstance(state.get("latest_provider_smoke_test"), dict) else {}
    return {
        "count": state.get("provider_smoke_test_count"),
        "latest_smoke_test_id": latest.get("smoke_test_id") or "",
        "latest_status": latest.get("status") or "",
        "latest_ok": latest.get("ok"),
        "latest_network_attempted": latest.get("network_attempted"),
        "provider": latest.get("provider") or "",
        "model": latest.get("model") or "",
        "config_drift": "provider_smoke_test_config_drift" in set(audit_summary.get("finding_codes") or []),
    }


def summarize_audit(audit: dict[str, Any]) -> dict[str, Any]:
    findings = [item for item in audit.get("findings", []) if isinstance(item, dict)]
    blocker_codes = [
        str(item.get("code") or "")
        for item in findings
        if project_audit_severity(str(item.get("code") or "")) == "blocker"
    ]
    warning_codes = [
        str(item.get("code") or "")
        for item in findings
        if project_audit_severity(str(item.get("code") or "")) == "warning"
    ]
    return {
        "ok": bool(audit.get("ok")),
        "finding_count": len(findings),
        "blocker_count": len(blocker_codes),
        "warning_count": len(warning_codes),
        "finding_codes": [str(item.get("code") or "") for item in findings],
        "blocker_codes": blocker_codes,
        "warning_codes": warning_codes,
    }


def summarize_upload_readiness(store: ProjectStore, *, repo_root: str | Path | None) -> dict[str, Any]:
    if repo_root is None:
        return {
            "checked": False,
            "repo_root": "",
            "prepublish_ok": None,
            "blocker_count": None,
            "warning_count": None,
            "gitignore_required_patterns": REQUIRED_GITIGNORE_PATTERNS,
            "ignored_runtime_paths": upload_ignore_targets(),
            "message": "Pass repo_root to include prepublish readiness.",
        }
    result = prepublish_check(Path(repo_root), projects_root=store.projects_root)
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    return {
        "checked": True,
        "repo_root": str(result.get("repo_root") or ""),
        "projects_root": str(result.get("projects_root") or ""),
        "prepublish_ok": bool(result.get("ok")),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "warning_count": int(summary.get("warning_count") or 0),
        "gitignore_required_patterns": REQUIRED_GITIGNORE_PATTERNS,
        "ignored_runtime_paths": upload_ignore_targets(),
    }


def upload_ignore_targets() -> list[str]:
    return [
        "workspace_projects/",
        "secrets.local.json",
        "*.local.json",
        ".env",
        ".env.*",
        "exports/",
        "backups/",
        "run_logs/",
        "usage_logs/",
        "*.log",
        "build/",
        "dist/",
        "*.egg-info/",
        ".coverage",
        "htmlcov/",
    ]


def health_status(audit_summary: dict[str, Any], upload_summary: dict[str, Any]) -> str:
    if int(audit_summary.get("blocker_count") or 0) > 0:
        return "blocked"
    if upload_summary.get("checked") and int(upload_summary.get("blocker_count") or 0) > 0:
        return "blocked"
    if int(audit_summary.get("warning_count") or 0) > 0:
        return "warning"
    if upload_summary.get("checked") and int(upload_summary.get("warning_count") or 0) > 0:
        return "warning"
    return "ok"


def next_gate(status: str) -> str:
    if status == "blocked":
        return "resolve_blockers_before_upload_or_execution"
    if status == "warning":
        return "manual_review_warnings"
    return "ready_for_next_operator_decision"
