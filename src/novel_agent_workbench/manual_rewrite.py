from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .self_style import SelfStyleBaselineService
from .storage import ProjectStore, safe_filename, utc_stamp


MANUAL_REWRITE_TASKS_DIRNAME = "manual_rewrite_tasks"
MANUAL_REWRITE_TASKS_INDEX_FILENAME = "manual_rewrite_tasks_index.json"
MANUAL_REWRITE_TASK_STATUSES = {"pending", "in_progress", "done", "skipped"}


class ManualRewriteTaskError(RuntimeError):
    """Raised when a manual rewrite task cannot be created or updated safely."""


@dataclass(frozen=True, slots=True)
class ManualRewriteTaskResult:
    task_id: str
    suggestion_id: str
    check_id: str
    draft_id: str
    chapter_id: str
    status: str
    reason_code: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ManualRewriteTaskStatusResult:
    task_id: str
    suggestion_id: str
    status: str
    reason_code: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ManualRewriteTaskService:
    """Metadata-only workspace for human rewrite tasks."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def tasks_dir(self) -> Path:
        return self.store.data_dir / MANUAL_REWRITE_TASKS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / MANUAL_REWRITE_TASKS_INDEX_FILENAME

    def create_task_from_style_suggestion(self, suggestion_id: str) -> ManualRewriteTaskResult:
        self.store.initialize()
        with self.store.lock():
            style_service = SelfStyleBaselineService(self.store)
            suggestion = style_service.read_style_suggestion(suggestion_id)
            decision = suggestion.get("decision") if isinstance(suggestion.get("decision"), dict) else {}
            if str(decision.get("status") or "") != "needs_manual_rewrite":
                raise ManualRewriteTaskError("Manual rewrite task requires a needs_manual_rewrite suggestion decision.")
            existing = self._find_by_suggestion_id(suggestion_id)
            if existing is not None:
                raise ManualRewriteTaskError(f"Style suggestion already has a manual rewrite task: {suggestion_id}")
            draft = suggestion.get("draft") if isinstance(suggestion.get("draft"), dict) else {}
            created_at = utc_stamp()
            task_id = f"{created_at}_{uuid4().hex[:12]}"
            chapter_id = str(draft.get("chapter_id") or "")
            draft_id = str(draft.get("draft_id") or "")
            check_id = str(suggestion.get("check_id") or "")
            reason_code = str(decision.get("reason_code") or "")
            task_path = self.tasks_dir / f"{safe_filename(chapter_id or 'chapter')}__{safe_filename(task_id)}.json"
            artifact = {
                "schema_version": 1,
                "task_id": task_id,
                "suggestion_id": suggestion_id,
                "check_id": check_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "title": str(draft.get("title") or ""),
                "status": "pending",
                "reason_code": reason_code,
                "created_at": created_at,
                "updated_at": created_at,
                "source_decision": {
                    "status": "needs_manual_rewrite",
                    "reason_code": reason_code,
                    "decided_at": str(decision.get("decided_at") or ""),
                },
                "workspace_policy": {
                    "manual_rewrite_required": True,
                    "auto_apply": False,
                    "auto_generate_draft": False,
                    "auto_commit": False,
                },
                "safety": manual_rewrite_safety(),
            }
            self.store.write_json(task_path, artifact)
            entry = {
                "task_id": task_id,
                "suggestion_id": suggestion_id,
                "check_id": check_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "title": str(draft.get("title") or ""),
                "status": "pending",
                "reason_code": reason_code,
                "created_at": created_at,
                "updated_at": created_at,
                "path": str(task_path.relative_to(self.store.root)),
                "safety": artifact["safety"],
            }
            self._append_index_entry(entry)
            return ManualRewriteTaskResult(
                task_id=task_id,
                suggestion_id=suggestion_id,
                check_id=check_id,
                draft_id=draft_id,
                chapter_id=chapter_id,
                status="pending",
                reason_code=reason_code,
                path=str(task_path),
                created_at=created_at,
            )

    def list_tasks(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "manual_rewrite_tasks": []})
        if not isinstance(index, dict):
            return []
        items = index.get("manual_rewrite_tasks")
        if not isinstance(items, list):
            return []
        tasks = [item for item in items if isinstance(item, dict)]
        if status:
            status = validate_manual_rewrite_status(status)
            tasks = [item for item in tasks if item.get("status") == status]
        return tasks

    def read_task(self, task_id: str) -> dict[str, Any]:
        entry = self._task_index_entry(task_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise ManualRewriteTaskError(f"Manual rewrite task index entry has no path: {task_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise ManualRewriteTaskError(f"Manual rewrite task artifact is missing or invalid: {task_id}")
        return artifact

    def mark_task(self, task_id: str, *, status: str, reason_code: str = "") -> ManualRewriteTaskStatusResult:
        self.store.initialize()
        with self.store.lock():
            status = validate_manual_rewrite_status(status)
            reason_code = validate_manual_rewrite_reason_code(reason_code)
            entry = self._task_index_entry(task_id)
            artifact = self.read_task(task_id)
            updated_at = utc_stamp()
            artifact["status"] = status
            artifact["updated_at"] = updated_at
            if reason_code:
                artifact["status_reason_code"] = reason_code
            self.store.write_json(str(entry["path"]), artifact)
            updates: dict[str, Any] = {"status": status, "updated_at": updated_at}
            if reason_code:
                updates["status_reason_code"] = reason_code
            self._update_index_entry(task_id, updates)
            return ManualRewriteTaskStatusResult(
                task_id=task_id,
                suggestion_id=str(artifact.get("suggestion_id") or entry.get("suggestion_id") or ""),
                status=status,
                reason_code=reason_code,
                updated_at=updated_at,
            )

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_tasks()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "manual_rewrite_tasks": items})

    def _task_index_entry(self, task_id: str) -> dict[str, Any]:
        for item in self.list_tasks():
            if item.get("task_id") == task_id:
                return item
        raise ManualRewriteTaskError(f"Manual rewrite task not found: {task_id}")

    def _find_by_suggestion_id(self, suggestion_id: str) -> dict[str, Any] | None:
        for item in self.list_tasks():
            if item.get("suggestion_id") == suggestion_id:
                return item
        return None

    def _update_index_entry(self, task_id: str, updates: dict[str, Any]) -> None:
        updated: list[dict[str, Any]] = []
        for item in self.list_tasks():
            if item.get("task_id") == task_id:
                item = {**item, **updates}
            updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "manual_rewrite_tasks": updated})


def validate_manual_rewrite_status(status: str) -> str:
    value = str(status or "").strip()
    if value not in MANUAL_REWRITE_TASK_STATUSES:
        raise ManualRewriteTaskError(f"Invalid manual rewrite task status: {status!r}")
    return value


def validate_manual_rewrite_reason_code(reason_code: str) -> str:
    value = str(reason_code or "").strip()
    if not value:
        return ""
    if len(value) > 80:
        raise ManualRewriteTaskError("reason_code is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise ManualRewriteTaskError("reason_code must use ASCII letters, numbers, '_' or '-'.")
    return value


def manual_rewrite_safety() -> dict[str, bool]:
    return {
        "local_only": True,
        "provider_called": False,
        "external_corpus_used": False,
        "draft_text_stored": False,
        "prompt_text_stored": False,
        "secret_text_stored": False,
        "auto_apply": False,
        "auto_generate_draft": False,
        "auto_revision_request": False,
        "auto_commit": False,
        "confirmed_touched": False,
        "memory_bank_touched": False,
        "rag_touched": False,
        "exports_touched": False,
    }
