from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .storage import ProjectStore, utc_stamp


CHAPTER_WORKFLOW_FILENAME = "chapters_workflow.json"
CHAPTER_STATUSES = {
    "planned",
    "drafting",
    "draft_ready",
    "review_ready",
    "review_accepted",
    "needs_revision",
    "revision_requested",
    "revision_draft_ready",
    "committed",
    "blocked",
}


class ChapterWorkflowError(RuntimeError):
    """Raised when chapter workflow state cannot be updated safely."""


@dataclass(frozen=True, slots=True)
class ChapterWorkflowEntry:
    chapter_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    latest_draft_id: str = ""
    latest_review_id: str = ""
    latest_review_decision: dict[str, Any] | None = None
    latest_revision_request_id: str = ""
    latest_revision_draft_id: str = ""
    confirmed_chapter_id: str = ""
    error_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChapterWorkflowService:
    """Metadata-only chapter workflow state for backend and future UI use."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def path(self) -> Path:
        return self.store.data_dir / CHAPTER_WORKFLOW_FILENAME

    def list_chapters(self) -> list[dict[str, Any]]:
        index = self._read_index()
        return list(index["chapters"])

    def get_chapter(self, chapter_id: str) -> dict[str, Any]:
        validate_chapter_id(chapter_id)
        for item in self.list_chapters():
            if item.get("chapter_id") == chapter_id:
                return item
        raise ChapterWorkflowError(f"Chapter not found: {chapter_id}")

    def remove_chapter(self, chapter_id: str) -> dict[str, Any]:
        validate_chapter_id(chapter_id)
        index = self._read_index()
        kept: list[dict[str, Any]] = []
        removed: dict[str, Any] | None = None
        for item in index["chapters"]:
            if item.get("chapter_id") == chapter_id:
                removed = item
                continue
            kept.append(item)
        if removed is not None:
            self.store.write_json(self.path, {"schema_version": 1, "chapters": kept})
        return {
            "chapter_id": chapter_id,
            "removed": removed is not None,
            "remaining_count": len(kept),
        }

    def mark_planned(self, chapter_id: str, *, title: str = "") -> dict[str, Any]:
        return self._upsert(chapter_id, title=title, status="planned")

    def mark_drafting(self, chapter_id: str, *, title: str = "") -> dict[str, Any]:
        current = self._find(chapter_id)
        if current and current.get("status") == "committed":
            return current
        return self._upsert(chapter_id, title=title, status="drafting", error_summary={})

    def mark_draft_ready(self, chapter_id: str, *, title: str = "", draft_id: str) -> dict[str, Any]:
        current = self._find(chapter_id)
        status = "committed" if current and current.get("status") == "committed" else "draft_ready"
        return self._upsert(chapter_id, title=title, status=status, latest_draft_id=draft_id, error_summary={})

    def mark_review_ready(
        self,
        chapter_id: str,
        *,
        title: str = "",
        draft_id: str,
        review_id: str,
    ) -> dict[str, Any]:
        current = self._find(chapter_id)
        status = "committed" if current and current.get("status") == "committed" else "review_ready"
        return self._upsert(
            chapter_id,
            title=title,
            status=status,
            latest_draft_id=draft_id,
            latest_review_id=review_id,
            error_summary={},
        )

    def mark_review_decision(
        self,
        chapter_id: str,
        *,
        title: str = "",
        draft_id: str,
        review_id: str,
        decision: str,
        reason_code: str = "",
        decided_at: str,
    ) -> dict[str, Any]:
        current = self._find(chapter_id)
        if current and current.get("status") == "committed":
            status = "committed"
        elif decision == "accepted":
            status = "review_accepted"
        elif decision == "needs_revision":
            status = "needs_revision"
        elif decision == "blocked":
            status = "blocked"
        else:
            raise ChapterWorkflowError(f"Invalid review decision: {decision}")
        error_summary = (
            {
                "stage": "review_decision",
                "error_type": "manual_block",
                "message": safe_error_field(reason_code),
                "timestamp": decided_at,
            }
            if decision == "blocked"
            else {}
        )
        return self._upsert(
            chapter_id,
            title=title,
            status=status,
            latest_draft_id=draft_id,
            latest_review_id=review_id,
            latest_review_decision={
                "decision": safe_error_field(decision),
                "review_id": safe_error_field(review_id),
                "reason_code": safe_error_field(reason_code),
                "decided_at": decided_at,
            },
            error_summary=error_summary,
        )

    def mark_revision_requested(
        self,
        chapter_id: str,
        *,
        title: str = "",
        draft_id: str,
        review_id: str,
        revision_request_id: str,
    ) -> dict[str, Any]:
        current = self._find(chapter_id)
        status = "committed" if current and current.get("status") == "committed" else "revision_requested"
        return self._upsert(
            chapter_id,
            title=title,
            status=status,
            latest_draft_id=draft_id,
            latest_review_id=review_id,
            latest_revision_request_id=revision_request_id,
            error_summary={},
        )

    def mark_revision_draft_ready(
        self,
        chapter_id: str,
        *,
        title: str = "",
        draft_id: str,
        review_id: str,
        revision_request_id: str,
    ) -> dict[str, Any]:
        current = self._find(chapter_id)
        status = "committed" if current and current.get("status") == "committed" else "revision_draft_ready"
        return self._upsert(
            chapter_id,
            title=title,
            status=status,
            latest_draft_id=draft_id,
            latest_review_id=review_id,
            latest_revision_request_id=revision_request_id,
            latest_revision_draft_id=draft_id,
            error_summary={},
        )

    def mark_committed(
        self,
        chapter_id: str,
        *,
        title: str = "",
        draft_id: str,
        confirmed_chapter_id: str,
    ) -> dict[str, Any]:
        return self._upsert(
            chapter_id,
            title=title,
            status="committed",
            latest_draft_id=draft_id,
            confirmed_chapter_id=confirmed_chapter_id,
            error_summary={},
        )

    def record_error(
        self,
        chapter_id: str,
        *,
        title: str = "",
        stage: str,
        error_type: str,
        message: str = "",
    ) -> dict[str, Any]:
        current = self._find(chapter_id)
        status = "committed" if current and current.get("status") == "committed" else "blocked"
        return self._upsert(
            chapter_id,
            title=title,
            status=status,
            error_summary={
                "stage": safe_error_field(stage),
                "error_type": safe_error_field(error_type),
                "message": safe_error_field(message),
                "timestamp": utc_stamp(),
            },
        )

    def _read_index(self) -> dict[str, Any]:
        index = self.store.read_json(self.path, default={"schema_version": 1, "chapters": []})
        if not isinstance(index, dict):
            return {"schema_version": 1, "chapters": []}
        chapters = index.get("chapters") if isinstance(index.get("chapters"), list) else []
        return {"schema_version": 1, "chapters": [item for item in chapters if isinstance(item, dict)]}

    def _find(self, chapter_id: str) -> dict[str, Any] | None:
        validate_chapter_id(chapter_id)
        for item in self.list_chapters():
            if item.get("chapter_id") == chapter_id:
                return item
        return None

    def _upsert(
        self,
        chapter_id: str,
        *,
        title: str = "",
        status: str,
        latest_draft_id: str | None = None,
        latest_review_id: str | None = None,
        latest_review_decision: dict[str, Any] | None = None,
        latest_revision_request_id: str | None = None,
        latest_revision_draft_id: str | None = None,
        confirmed_chapter_id: str | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validate_chapter_id(chapter_id)
        if status not in CHAPTER_STATUSES:
            raise ChapterWorkflowError(f"Invalid chapter status: {status}")
        index = self._read_index()
        now = utc_stamp()
        chapters: list[dict[str, Any]] = []
        updated: dict[str, Any] | None = None
        for item in index["chapters"]:
            if item.get("chapter_id") != chapter_id:
                chapters.append(item)
                continue
            updated = {
                **default_entry(chapter_id, now),
                **item,
                "title": title.strip() or str(item.get("title") or ""),
                "status": status,
                "updated_at": now,
                "latest_draft_id": latest_draft_id if latest_draft_id is not None else str(item.get("latest_draft_id") or ""),
                "latest_review_id": latest_review_id
                if latest_review_id is not None
                else str(item.get("latest_review_id") or ""),
                "latest_review_decision": latest_review_decision
                if latest_review_decision is not None
                else item.get("latest_review_decision") or {},
                "latest_revision_request_id": latest_revision_request_id
                if latest_revision_request_id is not None
                else str(item.get("latest_revision_request_id") or ""),
                "latest_revision_draft_id": latest_revision_draft_id
                if latest_revision_draft_id is not None
                else str(item.get("latest_revision_draft_id") or ""),
                "confirmed_chapter_id": confirmed_chapter_id
                if confirmed_chapter_id is not None
                else str(item.get("confirmed_chapter_id") or ""),
                "error_summary": error_summary if error_summary is not None else item.get("error_summary") or {},
            }
            chapters.append(updated)
        if updated is None:
            updated = {
                **default_entry(chapter_id, now),
                "title": title.strip(),
                "status": status,
                "latest_draft_id": latest_draft_id or "",
                "latest_review_id": latest_review_id or "",
                "latest_review_decision": latest_review_decision or {},
                "latest_revision_request_id": latest_revision_request_id or "",
                "latest_revision_draft_id": latest_revision_draft_id or "",
                "confirmed_chapter_id": confirmed_chapter_id or "",
                "error_summary": error_summary or {},
            }
            chapters.append(updated)
        self.store.write_json(self.path, {"schema_version": 1, "chapters": chapters})
        return updated


def default_entry(chapter_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "title": "",
        "status": "planned",
        "created_at": timestamp,
        "updated_at": timestamp,
        "latest_draft_id": "",
        "latest_review_id": "",
        "latest_review_decision": {},
        "latest_revision_request_id": "",
        "latest_revision_draft_id": "",
        "confirmed_chapter_id": "",
        "error_summary": {},
    }


def validate_chapter_id(chapter_id: str) -> None:
    value = chapter_id.strip()
    if not value or value in {".", ".."}:
        raise ChapterWorkflowError("chapter_id cannot be empty, '.' or '..'.")
    if any(separator in value for separator in ("/", "\\", ":", " ")):
        raise ChapterWorkflowError(f"Unsafe chapter_id: {chapter_id!r}")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise ChapterWorkflowError(f"Unsafe chapter_id: {chapter_id!r}")


def safe_error_field(value: str) -> str:
    return " ".join(str(value or "").split())[:200]
