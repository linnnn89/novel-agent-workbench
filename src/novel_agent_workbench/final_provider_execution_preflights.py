from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .final_assembly_gates import FinalAssemblyGateService
from .final_provider_authorizations import (
    FINAL_PROVIDER_AUTHORIZATION_STATUS,
    FinalProviderAuthorizationService,
    runbook_digest_input,
    sha256_json,
)
from .final_provider_runbooks import (
    FINAL_PROVIDER_RUNBOOK_STATUS,
    FinalProviderRunbookService,
    gate_metadata_digest_input,
)
from .providers import get_model_role_config
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_PROVIDER_EXECUTION_PREFLIGHTS_DIRNAME = "final_provider_execution_preflights"
FINAL_PROVIDER_EXECUTION_PREFLIGHTS_INDEX_FILENAME = "final_provider_execution_preflights_index.json"
PREFLIGHT_PASSED_STATUS = "passed_pending_execute_authorization"
PREFLIGHT_BLOCKED_STATUS = "blocked"


class FinalProviderExecutionPreflightError(RuntimeError):
    """Raised when a final Provider execution preflight cannot be created."""


@dataclass(frozen=True, slots=True)
class FinalProviderExecutionPreflightResult:
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


class FinalProviderExecutionPreflightService:
    """Read-only verifier for the final Provider gate/runbook/authorization chain."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.authorizations = FinalProviderAuthorizationService(store)
        self.runbooks = FinalProviderRunbookService(store)
        self.gates = FinalAssemblyGateService(store)

    @property
    def preflights_dir(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_EXECUTION_PREFLIGHTS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_EXECUTION_PREFLIGHTS_INDEX_FILENAME

    def create_preflight(self, authorization_id: str) -> FinalProviderExecutionPreflightResult:
        self.store.initialize()
        with self.store.lock():
            authorization = self.authorizations.read_authorization(authorization_id)
            runbook_id = str(authorization.get("runbook_id") or "")
            gate_id = str(authorization.get("gate_id") or "")
            chapter_id = str(authorization.get("chapter_id") or "")
            if not runbook_id or not gate_id or not chapter_id:
                raise FinalProviderExecutionPreflightError(
                    f"Final Provider authorization is missing required ids: {authorization_id}"
                )
            runbook = self.runbooks.read_runbook(runbook_id)
            gate = self.gates.read_gate(gate_id)
            created_at = utc_stamp()
            preflight_id = f"{created_at}_{uuid4().hex[:12]}"
            checks = build_preflight_checks(
                authorization=authorization,
                runbook=runbook,
                gate=gate,
                current_writer_role=current_writer_role_summary(self.store),
            )
            issues = [item for item in checks if item.get("passed") is not True]
            status = PREFLIGHT_PASSED_STATUS if not issues else PREFLIGHT_BLOCKED_STATUS
            path = self.preflights_dir / f"{safe_filename(chapter_id)}__{safe_filename(preflight_id)}.json"
            artifact = preflight_artifact(
                preflight_id=preflight_id,
                authorization=authorization,
                runbook=runbook,
                gate=gate,
                checks=checks,
                status=status,
                created_at=created_at,
            )
            self.store.write_json(path, artifact)
            self._append_index_entry(preflight_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
            return FinalProviderExecutionPreflightResult(
                preflight_id=preflight_id,
                authorization_id=authorization_id,
                runbook_id=runbook_id,
                gate_id=gate_id,
                chapter_id=chapter_id,
                status=status,
                issue_count=len(issues),
                path=str(path),
                created_at=created_at,
            )

    def list_preflights(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(
            self.index_path,
            default={"schema_version": 1, "final_provider_execution_preflights": []},
        )
        if not isinstance(index, dict):
            return []
        items = index.get("final_provider_execution_preflights")
        if not isinstance(items, list):
            return []
        preflights = [item for item in items if isinstance(item, dict)]
        if status:
            preflights = [item for item in preflights if item.get("status") == status]
        return preflights

    def read_preflight(self, preflight_id: str) -> dict[str, Any]:
        entry = self._preflight_index_entry(preflight_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalProviderExecutionPreflightError(
                f"Final Provider execution preflight index entry has no path: {preflight_id}"
            )
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalProviderExecutionPreflightError(
                f"Final Provider execution preflight artifact is missing or invalid: {preflight_id}"
            )
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_preflights()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_provider_execution_preflights": items})

    def _preflight_index_entry(self, preflight_id: str) -> dict[str, Any]:
        for item in self.list_preflights():
            if item.get("preflight_id") == preflight_id:
                return item
        raise FinalProviderExecutionPreflightError(f"Final Provider execution preflight not found: {preflight_id}")


def build_preflight_checks(
    *,
    authorization: dict[str, Any],
    runbook: dict[str, Any],
    gate: dict[str, Any],
    current_writer_role: dict[str, Any],
) -> list[dict[str, Any]]:
    auth_digests = authorization.get("digests") if isinstance(authorization.get("digests"), dict) else {}
    runbook_digests = runbook.get("digests") if isinstance(runbook.get("digests"), dict) else {}
    auth_role = authorization.get("writer_role") if isinstance(authorization.get("writer_role"), dict) else {}
    runbook_role = runbook.get("writer_role") if isinstance(runbook.get("writer_role"), dict) else {}
    gate_role = gate.get("writer_role") if isinstance(gate.get("writer_role"), dict) else {}
    auth_boundary = authorization.get("execution_boundary") if isinstance(authorization.get("execution_boundary"), dict) else {}
    checkpoint = authorization.get("checkpoint") if isinstance(authorization.get("checkpoint"), dict) else {}
    return [
        check("authorization_status", authorization.get("status") == FINAL_PROVIDER_AUTHORIZATION_STATUS),
        check("runbook_status", runbook.get("status") == FINAL_PROVIDER_RUNBOOK_STATUS),
        check("gate_status", gate.get("status") == "approved"),
        check("authorization_runbook_match", authorization.get("runbook_id") == runbook.get("runbook_id")),
        check("authorization_gate_match", authorization.get("gate_id") == runbook.get("gate_id") == gate.get("gate_id")),
        check(
            "chapter_match",
            authorization.get("chapter_id") == runbook.get("chapter_id") == gate.get("chapter_id"),
        ),
        check("runbook_digest_match", auth_digests.get("runbook_digest") == sha256_json(runbook_digest_input(runbook))),
        check("gate_digest_match", auth_digests.get("gate_digest") == sha256_json(gate_metadata_digest_input(gate))),
        check("runbook_gate_digest_match", runbook_digests.get("gate_digest") == sha256_json(gate_metadata_digest_input(gate))),
        check("prompt_digest_match", auth_digests.get("prompt_digest") == runbook_digests.get("prompt_digest") == gate.get("prompt_digest")),
        check(
            "system_prompt_digest_match",
            auth_digests.get("system_prompt_digest")
            == runbook_digests.get("system_prompt_digest")
            == gate.get("system_prompt_digest"),
        ),
        check("context_digest_match", auth_digests.get("context_digest") == runbook_digests.get("context_digest") == gate.get("context_digest")),
        check("authorization_provider_model_match", role_pair(auth_role) == role_pair(runbook_role) == role_pair(gate_role)),
        check("current_provider_model_match", role_pair(auth_role) == role_pair(current_writer_role)),
        check("execution_not_started", auth_boundary.get("execution_started") is False),
        check("separate_execute_authorization_required", auth_boundary.get("requires_separate_operator_execute_authorization") is True),
        check("checkpoint_recorded", bool(checkpoint.get("checkpoint_id")) and checkpoint.get("include_secrets") is False),
    ]


def preflight_artifact(
    *,
    preflight_id: str,
    authorization: dict[str, Any],
    runbook: dict[str, Any],
    gate: dict[str, Any],
    checks: list[dict[str, Any]],
    status: str,
    created_at: str,
) -> dict[str, Any]:
    auth_role = authorization.get("writer_role") if isinstance(authorization.get("writer_role"), dict) else {}
    prompt_summary = authorization.get("prompt_summary") if isinstance(authorization.get("prompt_summary"), dict) else {}
    token_budget = authorization.get("token_budget") if isinstance(authorization.get("token_budget"), dict) else {}
    issues = [item for item in checks if item.get("passed") is not True]
    return {
        "schema_version": 1,
        "preflight_id": preflight_id,
        "authorization_id": str(authorization.get("authorization_id") or ""),
        "runbook_id": str(runbook.get("runbook_id") or ""),
        "gate_id": str(gate.get("gate_id") or ""),
        "chapter_id": str(authorization.get("chapter_id") or ""),
        "status": status,
        "created_at": created_at,
        "writer_role": {
            "role": "writer",
            "provider": str(auth_role.get("provider") or ""),
            "model": str(auth_role.get("model") or ""),
        },
        "digests": {
            "authorization_digest": str((authorization.get("digests") if isinstance(authorization.get("digests"), dict) else {}).get("authorization_digest") or ""),
            "runbook_digest": sha256_json(runbook_digest_input(runbook)),
            "gate_digest": sha256_json(gate_metadata_digest_input(gate)),
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
        "execution_boundary": {
            "preflight_only": True,
            "execution_started": False,
            "requires_separate_operator_execute_authorization": True,
        },
        "safety": final_provider_execution_preflight_safety(),
    }


def preflight_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    writer_role = artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {}
    return {
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


def current_writer_role_summary(store: ProjectStore) -> dict[str, Any]:
    role_config = get_model_role_config(store, "writer")
    return {
        "role": "writer",
        "provider": role_config.provider,
        "model": role_config.model,
    }


def final_provider_execution_preflight_safety() -> dict[str, bool]:
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


def role_pair(value: dict[str, Any]) -> tuple[str, str]:
    return str(value.get("provider") or ""), str(value.get("model") or "")


def check(check_id: str, passed: bool) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed)}
