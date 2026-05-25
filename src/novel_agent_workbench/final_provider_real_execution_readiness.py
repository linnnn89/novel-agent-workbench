from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .final_provider_execution_attempts import (
    EXECUTION_ABORTED_STATUS,
    FinalProviderExecutionAttemptService,
)
from .providers import CHUTES_PROVIDER_ID, ProviderConfigError, get_model_role_config
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_PROVIDER_REAL_EXECUTION_READINESS_DIRNAME = "final_provider_real_execution_readiness"
FINAL_PROVIDER_REAL_EXECUTION_READINESS_INDEX_FILENAME = "final_provider_real_execution_readiness_index.json"
REAL_EXECUTION_READY_STATUS = "ready_for_manual_real_llm_authorization"
REAL_EXECUTION_BLOCKED_STATUS = "blocked"


class FinalProviderRealExecutionReadinessError(RuntimeError):
    """Raised when real Provider execution readiness cannot be assessed."""


@dataclass(frozen=True, slots=True)
class FinalProviderRealExecutionReadinessResult:
    readiness_id: str
    attempt_id: str
    preflight_id: str
    authorization_id: str
    runbook_id: str
    gate_id: str
    chapter_id: str
    status: str
    issue_count: int
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalProviderRealExecutionReadinessService:
    """No-network readiness report before any real final Provider execution."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.attempts = FinalProviderExecutionAttemptService(store)

    @property
    def readiness_dir(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_REAL_EXECUTION_READINESS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_REAL_EXECUTION_READINESS_INDEX_FILENAME

    def create_readiness(self, attempt_id: str) -> FinalProviderRealExecutionReadinessResult:
        self.store.initialize()
        with self.store.lock():
            if self._find_by_attempt_id(attempt_id) is not None:
                raise FinalProviderRealExecutionReadinessError(
                    f"Final Provider execution attempt already has a readiness report: {attempt_id}"
                )
            attempt = self.attempts.read_attempt(attempt_id)
            chapter_id = str(attempt.get("chapter_id") or "")
            if not chapter_id:
                raise FinalProviderRealExecutionReadinessError(
                    f"Final Provider execution attempt has no chapter_id: {attempt_id}"
                )
            writer_role = current_writer_role_readiness(self.store)
            checks = build_real_execution_readiness_checks(attempt=attempt, current_writer_role=writer_role)
            issues = [item for item in checks if item.get("passed") is not True]
            status = REAL_EXECUTION_READY_STATUS if not issues else REAL_EXECUTION_BLOCKED_STATUS
            created_at = utc_stamp()
            readiness_id = f"{created_at}_{uuid4().hex[:12]}"
            path = self.readiness_dir / f"{safe_filename(chapter_id)}__{safe_filename(readiness_id)}.json"
            artifact = readiness_artifact(
                readiness_id=readiness_id,
                attempt=attempt,
                current_writer_role=writer_role,
                checks=checks,
                status=status,
                created_at=created_at,
            )
            self.store.write_json(path, artifact)
            self._append_index_entry(readiness_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
            return FinalProviderRealExecutionReadinessResult(
                readiness_id=readiness_id,
                attempt_id=attempt_id,
                preflight_id=str(attempt.get("preflight_id") or ""),
                authorization_id=str(attempt.get("authorization_id") or ""),
                runbook_id=str(attempt.get("runbook_id") or ""),
                gate_id=str(attempt.get("gate_id") or ""),
                chapter_id=chapter_id,
                status=status,
                issue_count=len(issues),
                path=str(path),
                created_at=created_at,
            )

    def list_readiness(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(
            self.index_path,
            default={"schema_version": 1, "final_provider_real_execution_readiness": []},
        )
        if not isinstance(index, dict):
            return []
        items = index.get("final_provider_real_execution_readiness")
        if not isinstance(items, list):
            return []
        readiness = [item for item in items if isinstance(item, dict)]
        if status:
            readiness = [item for item in readiness if item.get("status") == status]
        return readiness

    def read_readiness(self, readiness_id: str) -> dict[str, Any]:
        entry = self._readiness_index_entry(readiness_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalProviderRealExecutionReadinessError(
                f"Final Provider real execution readiness index entry has no path: {readiness_id}"
            )
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalProviderRealExecutionReadinessError(
                f"Final Provider real execution readiness artifact is missing or invalid: {readiness_id}"
            )
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_readiness()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_provider_real_execution_readiness": items})

    def _readiness_index_entry(self, readiness_id: str) -> dict[str, Any]:
        for item in self.list_readiness():
            if item.get("readiness_id") == readiness_id:
                return item
        raise FinalProviderRealExecutionReadinessError(
            f"Final Provider real execution readiness not found: {readiness_id}"
        )

    def _find_by_attempt_id(self, attempt_id: str) -> dict[str, Any] | None:
        for item in self.list_readiness():
            if item.get("attempt_id") == attempt_id:
                return item
        return None


def build_real_execution_readiness_checks(
    *, attempt: dict[str, Any], current_writer_role: dict[str, Any]
) -> list[dict[str, Any]]:
    attempt_role = attempt.get("writer_role") if isinstance(attempt.get("writer_role"), dict) else {}
    attempt_boundary = attempt.get("execution_boundary") if isinstance(attempt.get("execution_boundary"), dict) else {}
    attempt_safety = attempt.get("safety") if isinstance(attempt.get("safety"), dict) else {}
    source_preflight = attempt.get("source_preflight") if isinstance(attempt.get("source_preflight"), dict) else {}
    return [
        check("source_attempt_aborted", attempt.get("status") == EXECUTION_ABORTED_STATUS),
        check("source_abort_reason_policy", attempt.get("abort_reason_code") == "real_llm_disabled_by_policy"),
        check(
            "source_preflight_passed",
            source_preflight.get("status") == "passed_pending_execute_authorization"
            and int(source_preflight.get("issue_count") or 0) == 0,
        ),
        check("source_attempt_provider_not_called", attempt_boundary.get("provider_called") is False),
        check("source_attempt_real_llm_not_called", attempt_safety.get("real_llm_called") is False),
        check("source_attempt_requires_real_authorization", attempt_boundary.get("requires_explicit_real_llm_authorization") is True),
        check("current_provider_model_match", role_pair(attempt_role) == role_pair(current_writer_role)),
        check("current_provider_is_chutes", current_writer_role.get("provider") == CHUTES_PROVIDER_ID),
        check("current_api_key_ref_configured", bool(current_writer_role.get("api_key_ref"))),
        check("current_project_secret_present", current_writer_role.get("has_project_secret") is True),
        check("current_secret_ref_valid", not bool(current_writer_role.get("config_error"))),
    ]


def readiness_artifact(
    *,
    readiness_id: str,
    attempt: dict[str, Any],
    current_writer_role: dict[str, Any],
    checks: list[dict[str, Any]],
    status: str,
    created_at: str,
) -> dict[str, Any]:
    attempt_role = attempt.get("writer_role") if isinstance(attempt.get("writer_role"), dict) else {}
    digests = attempt.get("digests") if isinstance(attempt.get("digests"), dict) else {}
    prompt_summary = attempt.get("prompt_summary") if isinstance(attempt.get("prompt_summary"), dict) else {}
    token_budget = attempt.get("token_budget") if isinstance(attempt.get("token_budget"), dict) else {}
    issues = [item for item in checks if item.get("passed") is not True]
    return {
        "schema_version": 1,
        "readiness_id": readiness_id,
        "attempt_id": str(attempt.get("attempt_id") or ""),
        "preflight_id": str(attempt.get("preflight_id") or ""),
        "authorization_id": str(attempt.get("authorization_id") or ""),
        "runbook_id": str(attempt.get("runbook_id") or ""),
        "gate_id": str(attempt.get("gate_id") or ""),
        "chapter_id": str(attempt.get("chapter_id") or ""),
        "status": status,
        "created_at": created_at,
        "source_attempt": {
            "attempt_id": str(attempt.get("attempt_id") or ""),
            "status": str(attempt.get("status") or ""),
            "abort_reason_code": str(attempt.get("abort_reason_code") or ""),
        },
        "writer_role": {
            "role": "writer",
            "provider": str(attempt_role.get("provider") or ""),
            "model": str(attempt_role.get("model") or ""),
        },
        "current_writer_role": current_writer_role,
        "digests": {
            "authorization_digest": str(digests.get("authorization_digest") or ""),
            "runbook_digest": str(digests.get("runbook_digest") or ""),
            "gate_digest": str(digests.get("gate_digest") or ""),
        },
        "prompt_summary": {
            "prompt_chars": int(prompt_summary.get("prompt_chars") or 0),
            "system_prompt_chars": int(prompt_summary.get("system_prompt_chars") or 0),
            "context_section_count": int(prompt_summary.get("context_section_count") or 0),
            "estimated_total_tokens": int(prompt_summary.get("estimated_total_tokens") or 0),
        },
        "token_budget": {
            "max_context_tokens": int(token_budget.get("max_context_tokens") or 0),
            "estimated_used_tokens": int(token_budget.get("estimated_used_tokens") or 0),
            "estimated_remaining_tokens": int(token_budget.get("estimated_remaining_tokens") or 0),
        },
        "check_results": checks,
        "issue_count": len(issues),
        "issue_codes": [str(item.get("check_id") or "") for item in issues],
        "manual_required_actions": manual_required_actions(current_writer_role=current_writer_role),
        "execution_boundary": {
            "readiness_only": True,
            "execution_started": False,
            "provider_called": False,
            "real_llm_called": False,
            "requires_explicit_real_llm_authorization": True,
            "requires_key_before_execution": True,
            "requires_network_before_execution": True,
            "writes_draft": False,
        },
        "safety": final_provider_real_execution_readiness_safety(),
    }


def readiness_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    writer_role = artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {}
    return {
        "readiness_id": artifact.get("readiness_id"),
        "attempt_id": artifact.get("attempt_id"),
        "preflight_id": artifact.get("preflight_id"),
        "authorization_id": artifact.get("authorization_id"),
        "runbook_id": artifact.get("runbook_id"),
        "gate_id": artifact.get("gate_id"),
        "chapter_id": artifact.get("chapter_id"),
        "status": artifact.get("status"),
        "created_at": artifact.get("created_at"),
        "path": path,
        "provider": writer_role.get("provider"),
        "model": writer_role.get("model"),
        "issue_count": artifact.get("issue_count"),
        "issue_codes": artifact.get("issue_codes") if isinstance(artifact.get("issue_codes"), list) else [],
        "safety": artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {},
    }


def current_writer_role_readiness(store: ProjectStore) -> dict[str, Any]:
    role_config = get_model_role_config(store, "writer")
    config_error = ""
    secret_name = ""
    if role_config.api_key_ref:
        try:
            secret_name = role_config.secret_name()
        except ProviderConfigError as exc:
            config_error = str(exc)
    public_secrets = store.public_state().get("secrets", {})
    secret_state = public_secrets.get(secret_name) if isinstance(public_secrets, dict) and secret_name else {}
    return {
        "role": "writer",
        "provider": role_config.provider,
        "model": role_config.model,
        "base_url_host": safe_base_url_host(role_config.base_url),
        "api_key_ref": role_config.api_key_ref,
        "secret_name": secret_name,
        "has_project_secret": bool(secret_state.get("has_value")) if isinstance(secret_state, dict) else False,
        "config_error": config_error,
    }


def manual_required_actions(*, current_writer_role: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "action_id": "confirm_real_llm_network_call",
            "required": True,
            "blocking_next_step": True,
            "status": "manual_authorization_required",
        },
        {
            "action_id": "provide_or_confirm_chutes_key",
            "required": True,
            "blocking_next_step": current_writer_role.get("has_project_secret") is not True,
            "status": "project_secret_present" if current_writer_role.get("has_project_secret") is True else "missing_project_secret",
        },
        {
            "action_id": "reprovide_prompt_and_context_inputs_for_digest_match",
            "required": True,
            "blocking_next_step": True,
            "status": "manual_input_required",
        },
        {
            "action_id": "authorize_draft_write_after_provider_response",
            "required": True,
            "blocking_next_step": True,
            "status": "manual_policy_required",
        },
    ]


def final_provider_real_execution_readiness_safety() -> dict[str, bool]:
    return {
        "provider_called": False,
        "real_llm_called": False,
        "secret_value_read": False,
        "prompt_text_stored": False,
        "context_text_stored": False,
        "chapter_text_stored": False,
        "secret_text_stored": False,
        "writes_draft": False,
        "auto_commit": False,
        "memory_bank_touched": False,
        "rag_touched": False,
        "exports_touched": False,
        "ui_touched": False,
        "docx_touched": False,
    }


def check(check_id: str, passed: bool) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed)}


def role_pair(value: dict[str, Any]) -> tuple[str, str]:
    return (str(value.get("provider") or ""), str(value.get("model") or ""))


def safe_base_url_host(base_url: str) -> str:
    if not base_url:
        return ""
    without_scheme = base_url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0].split("@")[-1]
