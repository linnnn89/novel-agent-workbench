from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .context_assembler import ContextAssemblerService
from .drafts import DraftGenerationRequest, DraftGenerationService, render_context_prompt
from .final_assembly_gates import FinalAssemblyGateError, FinalAssemblyGateService, validate_reason_code
from .final_provider_real_execution_readiness import (
    REAL_EXECUTION_READY_STATUS,
    FinalProviderRealExecutionReadinessService,
)
from .providers import CHUTES_PROVIDER_ID, get_model_role_config
from .storage import ProjectStore, safe_filename, utc_stamp


FINAL_PROVIDER_REAL_EXECUTIONS_DIRNAME = "final_provider_real_executions"
FINAL_PROVIDER_REAL_EXECUTIONS_INDEX_FILENAME = "final_provider_real_executions_index.json"
FINAL_PROVIDER_REAL_EXECUTION_DRAFT_CREATED_STATUS = "draft_created"


class FinalProviderRealExecutionError(RuntimeError):
    """Raised when a final real Provider execution cannot safely proceed."""


@dataclass(frozen=True, slots=True)
class FinalProviderRealExecutionResult:
    execution_id: str
    readiness_id: str
    attempt_id: str
    preflight_id: str
    authorization_id: str
    runbook_id: str
    gate_id: str
    chapter_id: str
    draft_id: str
    status: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FinalProviderRealExecutionPostcheckResult:
    execution_id: str
    draft_id: str
    chapter_id: str
    ok: bool
    status: str
    issue_count: int
    issues: list[dict[str, str]]
    checks: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalProviderRealExecutionService:
    """Explicit real final Provider execution path behind readiness."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.readiness = FinalProviderRealExecutionReadinessService(store)

    @property
    def executions_dir(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_REAL_EXECUTIONS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / FINAL_PROVIDER_REAL_EXECUTIONS_INDEX_FILENAME

    def execute(
        self,
        readiness_id: str,
        *,
        prompt: str,
        system_prompt: str = "",
        title: str = "",
        max_context_tokens: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reason_code: str = "",
    ) -> FinalProviderRealExecutionResult:
        safe_reason = validate_reason_code(reason_code)
        self.store.initialize()
        if self._find_by_readiness_id(readiness_id) is not None:
            raise FinalProviderRealExecutionError(
                f"Final Provider real execution readiness already has an execution: {readiness_id}"
            )
        readiness = self.readiness.read_readiness(readiness_id)
        if str(readiness.get("status") or "") != REAL_EXECUTION_READY_STATUS:
            raise FinalProviderRealExecutionError(
                f"Final Provider real execution readiness is not ready: {readiness_id}"
            )
        if int(readiness.get("issue_count") or 0) != 0:
            raise FinalProviderRealExecutionError(
                f"Final Provider real execution readiness has issues: {readiness_id}"
            )
        chapter_id = str(readiness.get("chapter_id") or "")
        gate_id = str(readiness.get("gate_id") or "")
        if not chapter_id or not gate_id:
            raise FinalProviderRealExecutionError(f"Final Provider real execution readiness is missing ids: {readiness_id}")
        request = DraftGenerationRequest(
            chapter_id=chapter_id,
            title=title,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata={"final_provider_real_execution": True, "readiness_id": readiness_id},
        )
        role_config = get_model_role_config(self.store, "writer")
        if role_config.provider != CHUTES_PROVIDER_ID:
            raise FinalProviderRealExecutionError("Final real Provider execution requires chutes_openai writer config.")
        try:
            FinalAssemblyGateService(self.store).require_approved_gate(
                gate_id,
                request=request,
                max_context_tokens=max_context_tokens,
                role_config=role_config,
            )
        except FinalAssemblyGateError as exc:
            raise FinalProviderRealExecutionError(str(exc)) from exc
        render = ContextAssemblerService(self.store).prompt_render_dry_run(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            max_context_tokens=max_context_tokens,
            include_prompt_text=True,
            include_context_text=True,
        ).to_dict()
        rendered_prompt = render_context_prompt(render)
        context_request = DraftGenerationRequest(
            chapter_id=request.chapter_id,
            title=request.title,
            prompt=rendered_prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            metadata={**request.metadata, "context_aware_generation": True},
        )
        draft_service = DraftGenerationService(self.store)
        created_at = utc_stamp()
        execution_id = f"{created_at}_{uuid4().hex[:12]}"
        draft_result = draft_service.generate_draft(context_request)
        draft_service._write_context_generation_summary(
            draft_result.draft_id,
            render,
            mode="real_context_aware_generation",
        )
        path = self.executions_dir / f"{safe_filename(chapter_id)}__{safe_filename(execution_id)}.json"
        artifact = execution_artifact(
            execution_id=execution_id,
            readiness=readiness,
            draft_result=draft_result.to_dict(),
            created_at=created_at,
            reason_code=safe_reason,
        )
        self.store.write_json(path, artifact)
        self._append_index_entry(execution_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
        return FinalProviderRealExecutionResult(
            execution_id=execution_id,
            readiness_id=readiness_id,
            attempt_id=str(readiness.get("attempt_id") or ""),
            preflight_id=str(readiness.get("preflight_id") or ""),
            authorization_id=str(readiness.get("authorization_id") or ""),
            runbook_id=str(readiness.get("runbook_id") or ""),
            gate_id=gate_id,
            chapter_id=chapter_id,
            draft_id=draft_result.draft_id,
            status=FINAL_PROVIDER_REAL_EXECUTION_DRAFT_CREATED_STATUS,
            path=str(path),
            created_at=created_at,
        )

    def list_executions(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(
            self.index_path,
            default={"schema_version": 1, "final_provider_real_executions": []},
        )
        if not isinstance(index, dict):
            return []
        items = index.get("final_provider_real_executions")
        if not isinstance(items, list):
            return []
        executions = [item for item in items if isinstance(item, dict)]
        if status:
            executions = [item for item in executions if item.get("status") == status]
        return executions

    def read_execution(self, execution_id: str) -> dict[str, Any]:
        entry = self._execution_index_entry(execution_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise FinalProviderRealExecutionError(f"Final Provider real execution index entry has no path: {execution_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise FinalProviderRealExecutionError(
                f"Final Provider real execution artifact is missing or invalid: {execution_id}"
            )
        return artifact

    def postcheck_execution(self, execution_id: str) -> FinalProviderRealExecutionPostcheckResult:
        """Read-only verification after a real execution has produced a draft."""

        self.store.initialize()
        artifact = self.read_execution(execution_id)
        draft_info = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else {}
        boundary = artifact.get("execution_boundary") if isinstance(artifact.get("execution_boundary"), dict) else {}
        safety = artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {}
        chapter_id = str(artifact.get("chapter_id") or "")
        draft_id = str(draft_info.get("draft_id") or "")
        issues: list[dict[str, str]] = []
        checks: dict[str, bool] = {}

        def record(name: str, ok: bool, message: str) -> None:
            checks[name] = ok
            if not ok:
                issues.append({"code": name, "message": message})

        record(
            "execution_status_draft_created",
            str(artifact.get("status") or "") == FINAL_PROVIDER_REAL_EXECUTION_DRAFT_CREATED_STATUS,
            "Execution artifact status is not draft_created.",
        )
        record("execution_has_draft_id", bool(draft_id), "Execution artifact does not reference a draft id.")
        record("execution_has_chapter_id", bool(chapter_id), "Execution artifact does not reference a chapter id.")

        draft: dict[str, Any] | None = None
        if draft_id:
            try:
                draft = DraftGenerationService(self.store).read_draft(draft_id)
            except Exception as exc:  # pragma: no cover - defensive metadata check
                issues.append({"code": "draft_artifact_readable", "message": str(exc)})
                checks["draft_artifact_readable"] = False
        else:
            checks["draft_artifact_readable"] = False
        if draft is not None:
            provider = draft.get("provider") if isinstance(draft.get("provider"), dict) else {}
            record("draft_status_is_draft", str(draft.get("status") or "") == "draft", "Draft is no longer in draft status.")
            record("draft_chapter_matches_execution", str(draft.get("chapter_id") or "") == chapter_id, "Draft chapter id does not match execution.")
            record("draft_provider_is_chutes", str(provider.get("provider") or "") == CHUTES_PROVIDER_ID, "Draft provider is not chutes_openai.")
            record("draft_not_empty", bool(str(draft.get("content") or "")), "Draft content is empty.")

        role_config = get_model_role_config(self.store, "writer")
        record(
            "writer_provider_still_chutes",
            role_config.provider == CHUTES_PROVIDER_ID,
            "Writer provider no longer matches chutes_openai.",
        )
        record(
            "boundary_records_user_trigger",
            boundary.get("user_triggered") is True,
            "Execution boundary does not record user-triggered execution.",
        )
        record("boundary_no_auto_commit", boundary.get("auto_commit") is False, "Execution boundary allows auto commit.")
        record("safety_no_prompt_text", safety.get("prompt_text_stored") is False, "Execution safety indicates prompt text storage.")
        record("safety_no_context_text", safety.get("context_text_stored") is False, "Execution safety indicates context text storage.")
        record("safety_no_secret_text", safety.get("secret_text_stored") is False, "Execution safety indicates secret text storage.")
        record("safety_no_memory_touch", safety.get("memory_bank_touched") is False, "Execution safety indicates Memory Bank mutation.")
        record("safety_no_rag_touch", safety.get("rag_touched") is False, "Execution safety indicates RAG mutation.")
        record("safety_no_exports_touch", safety.get("exports_touched") is False, "Execution safety indicates export mutation.")
        record("safety_no_docx_touch", safety.get("docx_touched") is False, "Execution safety indicates DOCX mutation.")
        record(
            "execution_metadata_has_no_forbidden_text_keys",
            not contains_forbidden_execution_metadata_text_key(artifact),
            "Execution metadata contains a forbidden text-bearing key.",
        )
        confirmed_chapters = DraftGenerationService(self.store).list_confirmed_chapters()
        record(
            "chapter_not_confirmed",
            all(item.get("chapter_id") != chapter_id for item in confirmed_chapters),
            "Execution chapter already appears in confirmed chapters.",
        )
        ok = not issues
        return FinalProviderRealExecutionPostcheckResult(
            execution_id=execution_id,
            draft_id=draft_id,
            chapter_id=chapter_id,
            ok=ok,
            status="passed" if ok else "failed",
            issue_count=len(issues),
            issues=issues,
            checks=checks,
        )

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_executions()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "final_provider_real_executions": items})

    def _execution_index_entry(self, execution_id: str) -> dict[str, Any]:
        for item in self.list_executions():
            if item.get("execution_id") == execution_id:
                return item
        raise FinalProviderRealExecutionError(f"Final Provider real execution not found: {execution_id}")

    def _find_by_readiness_id(self, readiness_id: str) -> dict[str, Any] | None:
        for item in self.list_executions():
            if item.get("readiness_id") == readiness_id:
                return item
        return None


def execution_artifact(
    *,
    execution_id: str,
    readiness: dict[str, Any],
    draft_result: dict[str, Any],
    created_at: str,
    reason_code: str,
) -> dict[str, Any]:
    writer_role = readiness.get("writer_role") if isinstance(readiness.get("writer_role"), dict) else {}
    return {
        "schema_version": 1,
        "execution_id": execution_id,
        "readiness_id": str(readiness.get("readiness_id") or ""),
        "attempt_id": str(readiness.get("attempt_id") or ""),
        "preflight_id": str(readiness.get("preflight_id") or ""),
        "authorization_id": str(readiness.get("authorization_id") or ""),
        "runbook_id": str(readiness.get("runbook_id") or ""),
        "gate_id": str(readiness.get("gate_id") or ""),
        "chapter_id": str(readiness.get("chapter_id") or ""),
        "status": FINAL_PROVIDER_REAL_EXECUTION_DRAFT_CREATED_STATUS,
        "created_at": created_at,
        "operator_trigger": {
            "user_triggered": True,
            "reason_code": reason_code,
            "triggered_at": created_at,
        },
        "writer_role": {
            "role": "writer",
            "provider": str(writer_role.get("provider") or ""),
            "model": str(writer_role.get("model") or ""),
        },
        "draft": {
            "draft_id": str(draft_result.get("draft_id") or ""),
            "chapter_id": str(draft_result.get("chapter_id") or ""),
            "provider": str(draft_result.get("provider") or ""),
            "model": str(draft_result.get("model") or ""),
            "usage": draft_result.get("usage") if isinstance(draft_result.get("usage"), dict) else {},
        },
        "source_readiness": {
            "readiness_id": str(readiness.get("readiness_id") or ""),
            "status": str(readiness.get("status") or ""),
            "issue_count": int(readiness.get("issue_count") or 0),
        },
        "execution_boundary": {
            "execution_started": True,
            "user_triggered": True,
            "provider_called": True,
            "real_llm_called": True,
            "network_gate_removed": True,
            "writes_draft": True,
            "auto_commit": False,
        },
        "safety": final_provider_real_execution_safety(),
    }


def execution_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    writer_role = artifact.get("writer_role") if isinstance(artifact.get("writer_role"), dict) else {}
    draft = artifact.get("draft") if isinstance(artifact.get("draft"), dict) else {}
    return {
        "execution_id": artifact.get("execution_id"),
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
        "draft_id": draft.get("draft_id"),
        "provider": writer_role.get("provider"),
        "model": writer_role.get("model"),
        "safety": artifact.get("safety") if isinstance(artifact.get("safety"), dict) else {},
    }


def final_provider_real_execution_safety() -> dict[str, bool]:
    return {
        "provider_called": True,
        "real_llm_called": True,
        "user_triggered": True,
        "secret_value_read": True,
        "prompt_text_stored": False,
        "context_text_stored": False,
        "chapter_text_stored": False,
        "secret_text_stored": False,
        "writes_draft": True,
        "auto_commit": False,
        "memory_bank_touched": False,
        "rag_touched": False,
        "exports_touched": False,
        "ui_touched": False,
        "docx_touched": False,
    }


FORBIDDEN_EXECUTION_METADATA_TEXT_KEYS = {
    "prompt",
    "system_prompt",
    "context",
    "context_text",
    "content",
    "chapter_text",
    "generated_text",
    "response_text",
    "raw_response",
    "request_body",
    "api_key",
    "secret",
    "secret_value",
}


def contains_forbidden_execution_metadata_text_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_EXECUTION_METADATA_TEXT_KEYS:
                return True
            if contains_forbidden_execution_metadata_text_key(item):
                return True
        return False
    if isinstance(value, list):
        return any(contains_forbidden_execution_metadata_text_key(item) for item in value)
    return False
