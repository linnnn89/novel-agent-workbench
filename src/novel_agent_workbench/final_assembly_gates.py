from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .context_assembler import ContextAssemblerService
from .drafts import DraftGenerationRequest, validate_chapter_id
from .providers import ModelRoleConfig, get_model_role_config
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_ASSEMBLY_GATES_DIRNAME = "final_assembly_gates"
FINAL_ASSEMBLY_GATES_INDEX_FILENAME = "final_assembly_gates_index.json"


class FinalAssemblyGateError(RuntimeError):
    """Raised when a final Provider assembly gate is missing or invalid."""


@dataclass(frozen=True, slots=True)
class FinalAssemblyGateResult:
    gate_id: str
    chapter_id: str
    status: str
    context_section_count: int
    estimated_total_tokens: int
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinalAssemblyGateApprovalResult:
    gate_id: str
    status: str
    reason_code: str
    approved_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalAssemblyGateService:
    """Metadata-only approval gate for future real context-aware Provider assembly."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def gates_dir(self) -> Path:
        return self.store.data_dir / FINAL_ASSEMBLY_GATES_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_ASSEMBLY_GATES_INDEX_FILENAME

    def create_gate(
        self,
        *,
        chapter_id: str,
        prompt: str,
        system_prompt: str = "",
        max_context_tokens: int | None = None,
    ) -> FinalAssemblyGateResult:
        validate_chapter_id(chapter_id)
        prompt_value = str(prompt or "")
        if not prompt_value.strip():
            raise FinalAssemblyGateError("prompt cannot be empty.")
        self.store.initialize()
        with self.store.lock():
            role_config = get_model_role_config(self.store, "writer")
            render = ContextAssemblerService(self.store).prompt_render_dry_run(
                prompt=prompt_value,
                system_prompt=system_prompt,
                max_context_tokens=max_context_tokens,
                chapter_id=chapter_id,
                include_prompt_text=False,
                include_context_text=False,
            ).to_dict()
            created_at = utc_stamp()
            gate_id = f"{created_at}_{uuid4().hex[:12]}"
            path = self.gates_dir / f"{safe_filename(chapter_id)}__{safe_filename(gate_id)}.json"
            artifact = gate_artifact(
                gate_id=gate_id,
                chapter_id=chapter_id,
                prompt=prompt_value,
                system_prompt=system_prompt,
                render=render,
                role_config=role_config,
                status="pending_approval",
                reason_code="",
                created_at=created_at,
                approved_at="",
            )
            self.store.write_json(path, artifact)
            entry = gate_index_entry(artifact, path.relative_to(self.store.root).as_posix())
            self._append_index_entry(entry)
            prompt_summary = artifact["prompt_summary"]
            return FinalAssemblyGateResult(
                gate_id=gate_id,
                chapter_id=chapter_id,
                status="pending_approval",
                context_section_count=int(prompt_summary.get("context_section_count") or 0),
                estimated_total_tokens=int(prompt_summary.get("estimated_total_tokens") or 0),
                path=str(path),
                created_at=created_at,
            )

    def approve_gate(self, gate_id: str, *, reason_code: str = "") -> FinalAssemblyGateApprovalResult:
        safe_reason = validate_reason_code(reason_code)
        self.store.initialize()
        with self.store.lock():
            entry = self._gate_index_entry(gate_id)
            artifact = self.read_gate(gate_id)
            if str(artifact.get("status") or "") != "pending_approval":
                raise FinalAssemblyGateError(f"Final assembly gate is not pending approval: {gate_id}")
            approved_at = utc_stamp()
            artifact["status"] = "approved"
            artifact["approved_at"] = approved_at
            artifact["approval"] = {
                "status": "approved",
                "reason_code": safe_reason,
                "approved_at": approved_at,
            }
            self.store.write_json(str(entry["path"]), artifact)
            self._update_index_entry(
                gate_id,
                {
                    "status": "approved",
                    "approved_at": approved_at,
                    "approval": artifact["approval"],
                },
            )
            return FinalAssemblyGateApprovalResult(
                gate_id=gate_id,
                status="approved",
                reason_code=safe_reason,
                approved_at=approved_at,
            )

    def list_gates(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "final_assembly_gates": []})
        if not isinstance(index, dict):
            return []
        items = index.get("final_assembly_gates")
        if not isinstance(items, list):
            return []
        gates = [item for item in items if isinstance(item, dict)]
        if status:
            gates = [item for item in gates if item.get("status") == status]
        return gates

    def read_gate(self, gate_id: str) -> dict[str, Any]:
        entry = self._gate_index_entry(gate_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalAssemblyGateError(f"Final assembly gate index entry has no path: {gate_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalAssemblyGateError(f"Final assembly gate artifact is missing or invalid: {gate_id}")
        return artifact

    def require_approved_gate(
        self,
        gate_id: str,
        *,
        request: DraftGenerationRequest,
        max_context_tokens: int | None,
        role_config: ModelRoleConfig,
    ) -> dict[str, Any]:
        if not gate_id:
            raise FinalAssemblyGateError("Context-aware real Provider generation requires an approved final assembly gate.")
        gate = self.read_gate(gate_id)
        if str(gate.get("status") or "") != "approved":
            raise FinalAssemblyGateError(f"Final assembly gate is not approved: {gate_id}")
        expected = gate_artifact(
            gate_id=str(gate.get("gate_id") or gate_id),
            chapter_id=request.chapter_id,
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            render=ContextAssemblerService(self.store).prompt_render_dry_run(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                max_context_tokens=max_context_tokens,
                chapter_id=request.chapter_id,
                include_prompt_text=False,
                include_context_text=False,
            ).to_dict(),
            role_config=role_config,
            status="approved",
            reason_code=str((gate.get("approval") if isinstance(gate.get("approval"), dict) else {}).get("reason_code") or ""),
            created_at=str(gate.get("created_at") or ""),
            approved_at=str(gate.get("approved_at") or ""),
        )
        mismatches = gate_mismatches(gate, expected)
        if mismatches:
            raise FinalAssemblyGateError(f"Final assembly gate does not match current request/context: {', '.join(mismatches)}")
        return {
            "gate_id": gate_id,
            "status": "approved",
            "matched": True,
            "context_digest": gate.get("context_digest"),
            "prompt_digest": gate.get("prompt_digest"),
        }

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_gates()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_assembly_gates": items})

    def _gate_index_entry(self, gate_id: str) -> dict[str, Any]:
        for item in self.list_gates():
            if item.get("gate_id") == gate_id:
                return item
        raise FinalAssemblyGateError(f"Final assembly gate not found: {gate_id}")

    def _update_index_entry(self, gate_id: str, updates: dict[str, Any]) -> None:
        updated: list[dict[str, Any]] = []
        for item in self.list_gates():
            if item.get("gate_id") == gate_id:
                item = {**item, **updates}
            updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_assembly_gates": updated})


def gate_artifact(
    *,
    gate_id: str,
    chapter_id: str,
    prompt: str,
    system_prompt: str,
    render: dict[str, Any],
    role_config: ModelRoleConfig,
    status: str,
    reason_code: str,
    created_at: str,
    approved_at: str,
) -> dict[str, Any]:
    context_package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
    sections = context_package.get("sections") if isinstance(context_package.get("sections"), list) else []
    skipped = context_package.get("skipped") if isinstance(context_package.get("skipped"), list) else []
    section_summaries = [section_summary(item) for item in sections if isinstance(item, dict)]
    skipped_summaries = [section_summary(item) for item in skipped if isinstance(item, dict)]
    prompt_summary = render.get("prompt_summary") if isinstance(render.get("prompt_summary"), dict) else {}
    token_budget = context_package.get("token_budget") if isinstance(context_package.get("token_budget"), dict) else {}
    artifact = {
        "schema_version": 1,
        "gate_id": gate_id,
        "chapter_id": chapter_id,
        "status": status,
        "created_at": created_at,
        "approved_at": approved_at,
        "approval": {"status": status if status == "approved" else "pending", "reason_code": reason_code, "approved_at": approved_at},
        "writer_role": {
            "role": "writer",
            "provider": role_config.provider,
            "model": role_config.model,
        },
        "prompt_digest": sha256_text(prompt),
        "system_prompt_digest": sha256_text(system_prompt),
        "prompt_summary": {
            "prompt_chars": len(prompt),
            "system_prompt_chars": len(system_prompt or ""),
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
        "context_sections": section_summaries,
        "skipped_context": skipped_summaries,
        "context_digest": sha256_json({"sections": section_summaries, "skipped": skipped_summaries, "token_budget": token_budget}),
        "safety": {
            "provider_called": False,
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
        },
    }
    return artifact


def gate_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    return {
        "gate_id": artifact.get("gate_id"),
        "chapter_id": artifact.get("chapter_id"),
        "status": artifact.get("status"),
        "created_at": artifact.get("created_at"),
        "approved_at": artifact.get("approved_at"),
        "path": path,
        "writer_role": artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {},
        "prompt_summary": artifact.get("prompt_summary") if isinstance(artifact.get("prompt_summary"), dict) else {},
        "context_digest": artifact.get("context_digest"),
        "safety": artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {},
    }


def section_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": item.get("source_type"),
        "source_id": item.get("source_id"),
        "category_id": item.get("category_id"),
        "priority": item.get("priority"),
        "memory_weight": item.get("memory_weight"),
        "estimated_tokens": item.get("estimated_tokens"),
        "char_count": item.get("char_count"),
        "selection_status": item.get("selection_status"),
        "skip_reason": item.get("skip_reason"),
        "contains_text": bool(item.get("contains_text")),
    }


def gate_mismatches(actual: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    fields = [
        "chapter_id",
        "prompt_digest",
        "system_prompt_digest",
        "context_digest",
    ]
    mismatches = [field for field in fields if actual.get(field) != expected.get(field)]
    actual_role = actual.get("writer_role") if isinstance(actual.get("writer_role"), dict) else {}
    expected_role = expected.get("writer_role") if isinstance(expected.get("writer_role"), dict) else {}
    for field in ("provider", "model"):
        if actual_role.get(field) != expected_role.get(field):
            mismatches.append(f"writer_role.{field}")
    return mismatches


def sha256_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def sha256_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_reason_code(reason_code: str) -> str:
    value = str(reason_code or "").strip()
    if not value:
        return ""
    if len(value) > 80:
        raise FinalAssemblyGateError("reason_code is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise FinalAssemblyGateError("reason_code must use ASCII letters, numbers, '_' or '-'.")
    return value
