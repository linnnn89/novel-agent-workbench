from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .final_provider_execution_preflights import (
    PREFLIGHT_PASSED_STATUS,
    FinalProviderExecutionPreflightService,
)
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_PROVIDER_EXECUTION_ATTEMPTS_DIRNAME = "final_provider_execution_attempts"
FINAL_PROVIDER_EXECUTION_ATTEMPTS_INDEX_FILENAME = "final_provider_execution_attempts_index.json"
EXECUTION_ABORTED_STATUS = "aborted_real_llm_disabled"


class FinalProviderExecutionAttemptError(RuntimeError):
    """Raised when a final Provider execution attempt cannot safely proceed."""


@dataclass(frozen=True, slots=True)
class FinalProviderExecutionAttemptResult:
    attempt_id: str
    preflight_id: str
    authorization_id: str
    runbook_id: str
    gate_id: str
    chapter_id: str
    status: str
    abort_reason_code: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalProviderExecutionAttemptService:
    """Fail-closed execution stub for future final Provider calls."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.preflights = FinalProviderExecutionPreflightService(store)

    @property
    def attempts_dir(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_EXECUTION_ATTEMPTS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_EXECUTION_ATTEMPTS_INDEX_FILENAME

    def create_attempt(self, preflight_id: str) -> FinalProviderExecutionAttemptResult:
        self.store.initialize()
        with self.store.lock():
            if self._find_by_preflight_id(preflight_id) is not None:
                raise FinalProviderExecutionAttemptError(f"Final Provider execution preflight already has an attempt: {preflight_id}")
            preflight = self.preflights.read_preflight(preflight_id)
            if str(preflight.get("status") or "") != PREFLIGHT_PASSED_STATUS:
                raise FinalProviderExecutionAttemptError(
                    f"Final Provider execution attempt requires a passed preflight: {preflight_id}"
                )
            if int(preflight.get("issue_count") or 0) != 0:
                raise FinalProviderExecutionAttemptError(
                    f"Final Provider execution attempt requires a zero-issue preflight: {preflight_id}"
                )
            chapter_id = str(preflight.get("chapter_id") or "")
            if not chapter_id:
                raise FinalProviderExecutionAttemptError(f"Final Provider execution preflight has no chapter_id: {preflight_id}")
            created_at = utc_stamp()
            attempt_id = f"{created_at}_{uuid4().hex[:12]}"
            path = self.attempts_dir / f"{safe_filename(chapter_id)}__{safe_filename(attempt_id)}.json"
            artifact = attempt_artifact(attempt_id=attempt_id, preflight=preflight, created_at=created_at)
            self.store.write_json(path, artifact)
            self._append_index_entry(attempt_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
            return FinalProviderExecutionAttemptResult(
                attempt_id=attempt_id,
                preflight_id=preflight_id,
                authorization_id=str(preflight.get("authorization_id") or ""),
                runbook_id=str(preflight.get("runbook_id") or ""),
                gate_id=str(preflight.get("gate_id") or ""),
                chapter_id=chapter_id,
                status=EXECUTION_ABORTED_STATUS,
                abort_reason_code="real_llm_disabled_by_policy",
                path=str(path),
                created_at=created_at,
            )

    def list_attempts(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(
            self.index_path,
            default={"schema_version": 1, "final_provider_execution_attempts": []},
        )
        if not isinstance(index, dict):
            return []
        items = index.get("final_provider_execution_attempts")
        if not isinstance(items, list):
            return []
        attempts = [item for item in items if isinstance(item, dict)]
        if status:
            attempts = [item for item in attempts if item.get("status") == status]
        return attempts

    def read_attempt(self, attempt_id: str) -> dict[str, Any]:
        entry = self._attempt_index_entry(attempt_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalProviderExecutionAttemptError(f"Final Provider execution attempt index entry has no path: {attempt_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalProviderExecutionAttemptError(f"Final Provider execution attempt artifact is missing or invalid: {attempt_id}")
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_attempts()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_provider_execution_attempts": items})

    def _attempt_index_entry(self, attempt_id: str) -> dict[str, Any]:
        for item in self.list_attempts():
            if item.get("attempt_id") == attempt_id:
                return item
        raise FinalProviderExecutionAttemptError(f"Final Provider execution attempt not found: {attempt_id}")

    def _find_by_preflight_id(self, preflight_id: str) -> dict[str, Any] | None:
        for item in self.list_attempts():
            if item.get("preflight_id") == preflight_id:
                return item
        return None


def attempt_artifact(*, attempt_id: str, preflight: dict[str, Any], created_at: str) -> dict[str, Any]:
    writer_role = preflight.get("writer_role") if isinstance(preflight.get("writer_role"), dict) else {}
    digests = preflight.get("digests") if isinstance(preflight.get("digests"), dict) else {}
    prompt_summary = preflight.get("prompt_summary") if isinstance(preflight.get("prompt_summary"), dict) else {}
    token_budget = preflight.get("token_budget") if isinstance(preflight.get("token_budget"), dict) else {}
    return {
        "schema_version": 1,
        "attempt_id": attempt_id,
        "preflight_id": str(preflight.get("preflight_id") or ""),
        "authorization_id": str(preflight.get("authorization_id") or ""),
        "runbook_id": str(preflight.get("runbook_id") or ""),
        "gate_id": str(preflight.get("gate_id") or ""),
        "chapter_id": str(preflight.get("chapter_id") or ""),
        "status": EXECUTION_ABORTED_STATUS,
        "abort_reason_code": "real_llm_disabled_by_policy",
        "created_at": created_at,
        "source_preflight": {
            "preflight_id": str(preflight.get("preflight_id") or ""),
            "status": str(preflight.get("status") or ""),
            "issue_count": int(preflight.get("issue_count") or 0),
        },
        "writer_role": {
            "role": "writer",
            "provider": str(writer_role.get("provider") or ""),
            "model": str(writer_role.get("model") or ""),
        },
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
        "execution_boundary": {
            "stub_only": True,
            "execution_started": False,
            "execution_aborted": True,
            "provider_called": False,
            "requires_explicit_real_llm_authorization": True,
        },
        "safety": final_provider_execution_attempt_safety(),
    }


def attempt_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    writer_role = artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {}
    return {
        "attempt_id": artifact.get("attempt_id"),
        "preflight_id": artifact.get("preflight_id"),
        "authorization_id": artifact.get("authorization_id"),
        "runbook_id": artifact.get("runbook_id"),
        "gate_id": artifact.get("gate_id"),
        "chapter_id": artifact.get("chapter_id"),
        "status": artifact.get("status"),
        "abort_reason_code": artifact.get("abort_reason_code"),
        "created_at": artifact.get("created_at"),
        "path": path,
        "provider": writer_role.get("provider"),
        "model": writer_role.get("model"),
        "safety": artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {},
    }


def final_provider_execution_attempt_safety() -> dict[str, bool]:
    return {
        "provider_called": False,
        "real_llm_called": False,
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
