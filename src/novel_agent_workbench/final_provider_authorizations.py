from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .final_assembly_gates import validate_reason_code
from .final_provider_runbooks import FINAL_PROVIDER_RUNBOOK_STATUS, FinalProviderRunbookService
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_PROVIDER_AUTHORIZATIONS_DIRNAME = "final_provider_authorizations"
FINAL_PROVIDER_AUTHORIZATIONS_INDEX_FILENAME = "final_provider_authorizations_index.json"
FINAL_PROVIDER_AUTHORIZATION_STATUS = "authorized_pending_execution"


class FinalProviderAuthorizationError(RuntimeError):
    """Raised when a final Provider authorization cannot be recorded safely."""


@dataclass(frozen=True, slots=True)
class FinalProviderAuthorizationResult:
    authorization_id: str
    runbook_id: str
    gate_id: str
    chapter_id: str
    status: str
    provider: str
    model: str
    checkpoint_id: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalProviderAuthorizationService:
    """Metadata-only authorization record before any future final Provider execution."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.runbooks = FinalProviderRunbookService(store)

    @property
    def authorizations_dir(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_AUTHORIZATIONS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_AUTHORIZATIONS_INDEX_FILENAME

    def authorize_runbook(self, runbook_id: str, *, reason_code: str = "") -> FinalProviderAuthorizationResult:
        safe_reason = validate_reason_code(reason_code)
        self.store.initialize()
        with self.store.lock():
            if self._find_by_runbook_id(runbook_id) is not None:
                raise FinalProviderAuthorizationError(f"Final provider runbook is already authorized: {runbook_id}")
            runbook = self.runbooks.read_runbook(runbook_id)
            if str(runbook.get("status") or "") != FINAL_PROVIDER_RUNBOOK_STATUS:
                raise FinalProviderAuthorizationError(
                    f"Final provider authorization requires a pending operator runbook: {runbook_id}"
                )
            source_gate = runbook.get("source_gate") if isinstance(runbook.get("source_gate"), dict) else {}
            if str(source_gate.get("status") or "") != "approved":
                raise FinalProviderAuthorizationError(
                    f"Final provider authorization requires an approved source gate: {runbook_id}"
                )
            chapter_id = str(runbook.get("chapter_id") or "")
            if not chapter_id:
                raise FinalProviderAuthorizationError(f"Final provider runbook has no chapter_id: {runbook_id}")
            created_at = utc_stamp()
            authorization_id = f"{created_at}_{uuid4().hex[:12]}"
            checkpoint = self.store.create_checkpoint(label="pre_final_provider_authorization")
            path = self.authorizations_dir / f"{safe_filename(chapter_id)}__{safe_filename(authorization_id)}.json"
            artifact = authorization_artifact(
                authorization_id=authorization_id,
                runbook=runbook,
                checkpoint=checkpoint,
                reason_code=safe_reason,
                created_at=created_at,
            )
            self.store.write_json(path, artifact)
            self._append_index_entry(authorization_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
            writer_role = artifact["writer_role"] if isinstance(artifact.get("writer_role"), dict) else {}
            checkpoint_summary = artifact["checkpoint"] if isinstance(artifact.get("checkpoint"), dict) else {}
            return FinalProviderAuthorizationResult(
                authorization_id=authorization_id,
                runbook_id=str(runbook.get("runbook_id") or runbook_id),
                gate_id=str(runbook.get("gate_id") or ""),
                chapter_id=chapter_id,
                status=FINAL_PROVIDER_AUTHORIZATION_STATUS,
                provider=str(writer_role.get("provider") or ""),
                model=str(writer_role.get("model") or ""),
                checkpoint_id=str(checkpoint_summary.get("checkpoint_id") or ""),
                path=str(path),
                created_at=created_at,
            )

    def list_authorizations(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(
            self.index_path,
            default={"schema_version": 1, "final_provider_authorizations": []},
        )
        if not isinstance(index, dict):
            return []
        items = index.get("final_provider_authorizations")
        if not isinstance(items, list):
            return []
        authorizations = [item for item in items if isinstance(item, dict)]
        if status:
            authorizations = [item for item in authorizations if item.get("status") == status]
        return authorizations

    def read_authorization(self, authorization_id: str) -> dict[str, Any]:
        entry = self._authorization_index_entry(authorization_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalProviderAuthorizationError(
                f"Final provider authorization index entry has no path: {authorization_id}"
            )
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalProviderAuthorizationError(
                f"Final provider authorization artifact is missing or invalid: {authorization_id}"
            )
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_authorizations()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_provider_authorizations": items})

    def _authorization_index_entry(self, authorization_id: str) -> dict[str, Any]:
        for item in self.list_authorizations():
            if item.get("authorization_id") == authorization_id:
                return item
        raise FinalProviderAuthorizationError(f"Final provider authorization not found: {authorization_id}")

    def _find_by_runbook_id(self, runbook_id: str) -> dict[str, Any] | None:
        for item in self.list_authorizations():
            if item.get("runbook_id") == runbook_id:
                return item
        return None


def authorization_artifact(
    *,
    authorization_id: str,
    runbook: dict[str, Any],
    checkpoint: dict[str, Any],
    reason_code: str,
    created_at: str,
) -> dict[str, Any]:
    writer_role = runbook.get("writer_role") if isinstance(runbook.get("writer_role"), dict) else {}
    digests = runbook.get("digests") if isinstance(runbook.get("digests"), dict) else {}
    prompt_summary = runbook.get("prompt_summary") if isinstance(runbook.get("prompt_summary"), dict) else {}
    token_budget = runbook.get("token_budget") if isinstance(runbook.get("token_budget"), dict) else {}
    context_plan = runbook.get("context_plan") if isinstance(runbook.get("context_plan"), dict) else {}
    source_gate = runbook.get("source_gate") if isinstance(runbook.get("source_gate"), dict) else {}
    checkpoint_files = checkpoint.get("files") if isinstance(checkpoint.get("files"), list) else []
    safety = final_provider_authorization_safety()
    artifact = {
        "schema_version": 1,
        "authorization_id": authorization_id,
        "runbook_id": str(runbook.get("runbook_id") or ""),
        "gate_id": str(runbook.get("gate_id") or ""),
        "chapter_id": str(runbook.get("chapter_id") or ""),
        "status": FINAL_PROVIDER_AUTHORIZATION_STATUS,
        "created_at": created_at,
        "reason_code": reason_code,
        "source_gate": {
            "gate_id": str(source_gate.get("gate_id") or ""),
            "status": str(source_gate.get("status") or ""),
            "approved_at": str(source_gate.get("approved_at") or ""),
        },
        "source_runbook": {
            "runbook_id": str(runbook.get("runbook_id") or ""),
            "status": str(runbook.get("status") or ""),
            "created_at": str(runbook.get("created_at") or ""),
        },
        "writer_role": {
            "role": "writer",
            "provider": str(writer_role.get("provider") or ""),
            "model": str(writer_role.get("model") or ""),
        },
        "digests": {
            "prompt_digest": str(digests.get("prompt_digest") or ""),
            "system_prompt_digest": str(digests.get("system_prompt_digest") or ""),
            "context_digest": str(digests.get("context_digest") or ""),
            "gate_digest": str(digests.get("gate_digest") or ""),
            "runbook_digest": sha256_json(runbook_digest_input(runbook)),
            "authorization_digest": sha256_json(
                {
                    "authorization_id": authorization_id,
                    "runbook_id": str(runbook.get("runbook_id") or ""),
                    "created_at": created_at,
                    "reason_code": reason_code,
                }
            ),
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
        "context_plan": {
            "selected_section_count": int(context_plan.get("selected_section_count") or 0),
            "skipped_section_count": int(context_plan.get("skipped_section_count") or 0),
            "selected_section_types": context_plan.get("selected_section_types")
            if isinstance(context_plan.get("selected_section_types"), list)
            else [],
        },
        "checkpoint": {
            "checkpoint_id": str(checkpoint.get("checkpoint_id") or ""),
            "created_at": str(checkpoint.get("created_at") or ""),
            "label": str(checkpoint.get("label") or ""),
            "include_secrets": bool(checkpoint.get("include_secrets")),
            "file_count": len([item for item in checkpoint_files if isinstance(item, dict)]),
            "path": str(checkpoint.get("path") or ""),
        },
        "execution_boundary": {
            "authorization_recorded": True,
            "execution_started": False,
            "requires_separate_operator_execute_authorization": True,
        },
        "safety": safety,
    }
    return artifact


def authorization_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    writer_role = artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {}
    checkpoint = artifact.get("checkpoint") if isinstance(artifact.get("checkpoint"), dict) else {}
    return {
        "authorization_id": artifact.get("authorization_id"),
        "runbook_id": artifact.get("runbook_id"),
        "gate_id": artifact.get("gate_id"),
        "chapter_id": artifact.get("chapter_id"),
        "status": artifact.get("status"),
        "created_at": artifact.get("created_at"),
        "path": path,
        "writer_role": writer_role,
        "provider": writer_role.get("provider"),
        "model": writer_role.get("model"),
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "safety": artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {},
    }


def final_provider_authorization_safety() -> dict[str, bool]:
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


def runbook_digest_input(runbook: dict[str, Any]) -> dict[str, Any]:
    return {
        "runbook_id": runbook.get("runbook_id"),
        "gate_id": runbook.get("gate_id"),
        "chapter_id": runbook.get("chapter_id"),
        "status": runbook.get("status"),
        "created_at": runbook.get("created_at"),
        "writer_role": runbook.get("writer_role") if isinstance(runbook.get("writer_role"), dict) else {},
        "digests": runbook.get("digests") if isinstance(runbook.get("digests"), dict) else {},
        "prompt_summary": runbook.get("prompt_summary") if isinstance(runbook.get("prompt_summary"), dict) else {},
        "token_budget": runbook.get("token_budget") if isinstance(runbook.get("token_budget"), dict) else {},
    }


def sha256_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
