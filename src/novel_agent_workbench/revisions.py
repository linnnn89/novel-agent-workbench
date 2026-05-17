from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chapters import ChapterWorkflowService
from .drafts import DraftGenerationService, validate_chapter_id
from .reviews import DraftReviewService
from .storage import ProjectStore, safe_filename, utc_stamp


REVISION_REQUESTS_DIRNAME = "revision_requests"
REVISION_REQUESTS_INDEX_FILENAME = "revision_requests_index.json"


class RevisionRequestError(RuntimeError):
    """Raised when a revision request cannot be created safely."""


@dataclass(frozen=True, slots=True)
class RevisionRequestResult:
    revision_request_id: str
    review_id: str
    draft_id: str
    chapter_id: str
    status: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RevisionRequestService:
    """Metadata-only revision request service."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def requests_dir(self) -> Path:
        return self.store.data_dir / REVISION_REQUESTS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / REVISION_REQUESTS_INDEX_FILENAME

    def create_revision_request(self, review_id: str) -> RevisionRequestResult:
        self.store.initialize()
        with self.store.lock():
            review_entry = self._review_index_entry(review_id)
            review = DraftReviewService(self.store).read_review(review_id)
            decision = review.get("decision") if isinstance(review.get("decision"), dict) else {}
            if str(decision.get("status") or "") != "needs_revision":
                raise RevisionRequestError("Revision request requires a needs_revision review decision.")
            if self._find_by_review_id(review_id) is not None:
                raise RevisionRequestError(f"Review already has a revision request: {review_id}")
            draft_id = str(review.get("draft_id") or review_entry.get("draft_id") or "")
            chapter_id = str(review.get("chapter_id") or review_entry.get("chapter_id") or "")
            validate_chapter_id(chapter_id)
            draft = DraftGenerationService(self.store).read_draft(draft_id)
            created_at = utc_stamp()
            revision_request_id = new_revision_request_id()
            request_path = self.requests_dir / f"{safe_filename(chapter_id)}__{revision_request_id}.json"
            status = "requested"
            artifact = {
                "schema_version": 1,
                "revision_request_id": revision_request_id,
                "review_id": review_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "status": status,
                "created_at": created_at,
                "source_decision": {
                    "status": "needs_revision",
                    "reason_code": str(decision.get("reason_code") or ""),
                    "decided_at": str(decision.get("decided_at") or ""),
                },
                "revision_policy": "manual_revision_required",
                "request_summary": {
                    "source": "review_decision",
                    "metadata_keys": ["chapter_id", "draft_id", "review_id"],
                },
                "future_hooks": {
                    "llm_revision": "not_implemented",
                    "draft_mutation": "not_implemented",
                    "auto_commit": "not_implemented",
                    "memory_bank_update": "not_implemented",
                    "rag_update": "not_implemented",
                    "export_update": "not_implemented",
                },
            }
            self.store.write_json(request_path, artifact)
            self._append_index_entry(
                {
                    "revision_request_id": revision_request_id,
                    "review_id": review_id,
                    "draft_id": draft_id,
                    "chapter_id": chapter_id,
                    "status": status,
                    "created_at": created_at,
                    "path": str(request_path.relative_to(self.store.root)),
                    "source_decision": artifact["source_decision"],
                    "revision_policy": "manual_revision_required",
                }
            )
            ChapterWorkflowService(self.store).mark_revision_requested(
                chapter_id,
                title=str(draft.get("title") or ""),
                draft_id=draft_id,
                review_id=review_id,
                revision_request_id=revision_request_id,
            )
            return RevisionRequestResult(
                revision_request_id=revision_request_id,
                review_id=review_id,
                draft_id=draft_id,
                chapter_id=chapter_id,
                status=status,
                path=str(request_path),
                created_at=created_at,
            )

    def list_revision_requests(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "revision_requests": []})
        if not isinstance(index, dict):
            return []
        items = index.get("revision_requests")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_revision_request(self, revision_request_id: str) -> dict[str, Any]:
        for item in self.list_revision_requests():
            if item.get("revision_request_id") != revision_request_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise RevisionRequestError(f"Revision request index entry has no path: {revision_request_id}")
            value = self.store.read_json(path, default=None)
            if not isinstance(value, dict):
                raise RevisionRequestError(f"Revision request artifact is missing or invalid: {revision_request_id}")
            return value
        raise RevisionRequestError(f"Revision request not found: {revision_request_id}")

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "revision_requests": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "revision_requests": []}
        items = index.get("revision_requests") if isinstance(index.get("revision_requests"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "revision_requests": items})

    def _review_index_entry(self, review_id: str) -> dict[str, Any]:
        for item in DraftReviewService(self.store).list_reviews():
            if item.get("review_id") == review_id:
                return item
        raise RevisionRequestError(f"Review not found: {review_id}")

    def _find_by_review_id(self, review_id: str) -> dict[str, Any] | None:
        for item in self.list_revision_requests():
            if item.get("review_id") == review_id:
                return item
        return None


def new_revision_request_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"
