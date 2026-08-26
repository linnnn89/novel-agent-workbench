from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .final_assembly_gates import FinalAssemblyGateService
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_PROVIDER_RUNBOOKS_DIRNAME = "final_provider_runbooks"
FINAL_PROVIDER_RUNBOOKS_INDEX_FILENAME = "final_provider_runbooks_index.json"
FINAL_PROVIDER_RUNBOOK_STATUS = "pending_operator_authorization"


class FinalProviderRunbookError(RuntimeError):
    """Raised when a final Provider runbook cannot be created safely."""


@dataclass(frozen=True, slots=True)
class FinalProviderRunbookResult:
    runbook_id: str
    gate_id: str
    chapter_id: str
    status: str
    provider: str
    model: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalProviderRunbookService:
    """Metadata-only operator runbook before any real final Provider call."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.gates = FinalAssemblyGateService(store)

    @property
    def runbooks_dir(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_RUNBOOKS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_RUNBOOKS_INDEX_FILENAME

    def create_runbook(self, gate_id: str) -> FinalProviderRunbookResult:
        self.store.initialize()
        with self.store.lock():
            gate = self.gates.read_gate(gate_id)
            if str(gate.get("status") or "") != "approved":
                raise FinalProviderRunbookError(f"Final provider runbook requires an approved final assembly gate: {gate_id}")
            chapter_id = str(gate.get("chapter_id") or "")
            if not chapter_id:
                raise FinalProviderRunbookError(f"Final assembly gate has no chapter_id: {gate_id}")
            created_at = utc_stamp()
            runbook_id = f"{created_at}_{uuid4().hex[:12]}"
            path = self.runbooks_dir / f"{safe_filename(chapter_id)}__{safe_filename(runbook_id)}.json"
            artifact = runbook_artifact(runbook_id=runbook_id, gate=gate, created_at=created_at)
            self.store.write_json(path, artifact)
            self._append_index_entry(runbook_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
            writer_role = artifact["writer_role"] if isinstance(artifact.get("writer_role"), dict) else {}
            return FinalProviderRunbookResult(
                runbook_id=runbook_id,
                gate_id=str(gate.get("gate_id") or gate_id),
                chapter_id=chapter_id,
                status=FINAL_PROVIDER_RUNBOOK_STATUS,
                provider=str(writer_role.get("provider") or ""),
                model=str(writer_role.get("model") or ""),
                path=str(path),
                created_at=created_at,
            )

    def list_runbooks(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "final_provider_runbooks": []})
        if not isinstance(index, dict):
            return []
        items = index.get("final_provider_runbooks")
        if not isinstance(items, list):
            return []
        runbooks = [item for item in items if isinstance(item, dict)]
        if status:
            runbooks = [item for item in runbooks if item.get("status") == status]
        return runbooks

    def read_runbook(self, runbook_id: str) -> dict[str, Any]:
        entry = self._runbook_index_entry(runbook_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalProviderRunbookError(f"Final provider runbook index entry has no path: {runbook_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalProviderRunbookError(f"Final provider runbook artifact is missing or invalid: {runbook_id}")
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_runbooks()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_provider_runbooks": items})

    def _runbook_index_entry(self, runbook_id: str) -> dict[str, Any]:
        for item in self.list_runbooks():
            if item.get("runbook_id") == runbook_id:
                return item
        raise FinalProviderRunbookError(f"Final provider runbook not found: {runbook_id}")


def runbook_artifact(*, runbook_id: str, gate: dict[str, Any], created_at: str) -> dict[str, Any]:
    writer_role = gate.get("writer_role") if isinstance(gate.get("writer_role"), dict) else {}
    prompt_summary = gate.get("prompt_summary") if isinstance(gate.get("prompt_summary"), dict) else {}
    token_budget = gate.get("token_budget") if isinstance(gate.get("token_budget"), dict) else {}
    context_sections = gate.get("context_sections") if isinstance(gate.get("context_sections"), list) else []
    skipped_context = gate.get("skipped_context") if isinstance(gate.get("skipped_context"), list) else []
    approval = gate.get("approval") if isinstance(gate.get("approval"), dict) else {}
    safety = final_provider_runbook_safety()
    artifact = {
        "schema_version": 1,
        "runbook_id": runbook_id,
        "gate_id": str(gate.get("gate_id") or ""),
        "chapter_id": str(gate.get("chapter_id") or ""),
        "status": FINAL_PROVIDER_RUNBOOK_STATUS,
        "created_at": created_at,
        "source_gate": {
            "gate_id": str(gate.get("gate_id") or ""),
            "status": str(gate.get("status") or ""),
            "approved_at": str(gate.get("approved_at") or ""),
            "approval_reason_code": str(approval.get("reason_code") or ""),
        },
        "writer_role": {
            "role": "writer",
            "provider": str(writer_role.get("provider") or ""),
            "model": str(writer_role.get("model") or ""),
        },
        "digests": {
            "prompt_digest": str(gate.get("prompt_digest") or ""),
            "system_prompt_digest": str(gate.get("system_prompt_digest") or ""),
            "context_digest": str(gate.get("context_digest") or ""),
            "gate_digest": sha256_json(gate_metadata_digest_input(gate)),
        },
        "prompt_summary": {
            "prompt_chars": int(prompt_summary.get("prompt_chars") or 0),
            "system_prompt_chars": int(prompt_summary.get("system_prompt_chars") or 0),
            "context_section_count": int(prompt_summary.get("context_section_count") or 0),
            "context_chars": int(prompt_summary.get("context_chars") or 0),
            "estimated_total_chars": int(prompt_summary.get("estimated_total_chars") or 0),
            "estimated_total_tokens": int(prompt_summary.get("estimated_total_tokens") or 0),
        },
        "token_budget": {
            "max_context_tokens": int(token_budget.get("max_context_tokens") or 0),
            "estimated_used_tokens": int(token_budget.get("estimated_used_tokens") or 0),
            "estimated_remaining_tokens": int(token_budget.get("estimated_remaining_tokens") or 0),
        },
        "context_plan": {
            "selected_section_count": len([item for item in context_sections if isinstance(item, dict)]),
            "skipped_section_count": len([item for item in skipped_context if isinstance(item, dict)]),
            "selected_section_types": sorted(
                {
                    str(item.get("source_type") or "")
                    for item in context_sections
                    if isinstance(item, dict) and str(item.get("source_type") or "")
                }
            ),
        },
        "operator_checklist": {
            "approved_final_assembly_gate": True,
            "provider_config_snapshot": True,
            "no_provider_call": True,
            "no_draft_write": True,
            "no_context_update": True,
            "no_memory_bank_update": True,
            "no_rag_update": True,
            "no_export_update": True,
            "requires_operator_authorization": True,
        },
        "safety": safety,
    }
    return artifact


def runbook_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    writer_role = artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {}
    prompt_summary = artifact.get("prompt_summary") if isinstance(artifact.get("prompt_summary"), dict) else {}
    return {
        "runbook_id": artifact.get("runbook_id"),
        "gate_id": artifact.get("gate_id"),
        "chapter_id": artifact.get("chapter_id"),
        "status": artifact.get("status"),
        "created_at": artifact.get("created_at"),
        "path": path,
        "writer_role": writer_role,
        "provider": writer_role.get("provider"),
        "model": writer_role.get("model"),
        "context_section_count": prompt_summary.get("context_section_count"),
        "estimated_total_tokens": prompt_summary.get("estimated_total_tokens"),
        "safety": artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {},
    }


def final_provider_runbook_safety() -> dict[str, bool]:
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


def gate_metadata_digest_input(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": gate.get("gate_id"),
        "chapter_id": gate.get("chapter_id"),
        "status": gate.get("status"),
        "approved_at": gate.get("approved_at"),
        "writer_role": gate.get("writer_role") if isinstance(gate.get("writer_role"), dict) else {},
        "prompt_digest": gate.get("prompt_digest"),
        "system_prompt_digest": gate.get("system_prompt_digest"),
        "context_digest": gate.get("context_digest"),
        "prompt_summary": gate.get("prompt_summary") if isinstance(gate.get("prompt_summary"), dict) else {},
        "token_budget": gate.get("token_budget") if isinstance(gate.get("token_budget"), dict) else {},
    }


def sha256_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
