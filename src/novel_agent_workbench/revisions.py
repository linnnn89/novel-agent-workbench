from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chapters import ChapterWorkflowService
from .drafts import DraftGenerationResult, DraftGenerationService, new_draft_id, validate_chapter_id
from .providers import MOCK_PROVIDER_ID, ProviderRequest, generate_with_provider, get_model_role_config
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

    def generate_revision_draft(self, revision_request_id: str) -> DraftGenerationResult:
        self.store.initialize()
        with self.store.lock():
            request_entry = self._request_index_entry(revision_request_id)
            request_artifact = self.read_revision_request(revision_request_id)
            if str(request_artifact.get("status") or "") != "requested":
                raise RevisionRequestError(f"Revision request is not draftable: {revision_request_id}")
            generated_draft_id = str(request_artifact.get("generated_draft_id") or "")
            if generated_draft_id:
                raise RevisionRequestError(f"Revision request already has a draft candidate: {revision_request_id}")
            draft_id = str(request_artifact.get("draft_id") or request_entry.get("draft_id") or "")
            review_id = str(request_artifact.get("review_id") or request_entry.get("review_id") or "")
            chapter_id = str(request_artifact.get("chapter_id") or request_entry.get("chapter_id") or "")
            validate_chapter_id(chapter_id)
            role_config = get_model_role_config(self.store, "reviser")
            if role_config.provider != MOCK_PROVIDER_ID:
                raise RevisionRequestError("Revision draft generation is mock-only in this phase.")
            source_draft = DraftGenerationService(self.store).read_draft(draft_id)
            source_content = str(source_draft.get("content") or "")
            title = str(source_draft.get("title") or "")
            response = generate_with_provider(
                self.store,
                ProviderRequest(
                    role="reviser",
                    feature_id="ai_refinement",
                    prompt=f"Create mock revision draft candidate. source_draft_chars={len(source_content)}",
                    max_tokens=64,
                    metadata={
                        "revision_draft": True,
                        "chapter_id": chapter_id,
                        "source_draft_id": draft_id,
                        "review_id": review_id,
                        "revision_request_id": revision_request_id,
                    },
                ),
            )
            new_id = new_draft_id()
            created_at = utc_stamp()
            draft_service = DraftGenerationService(self.store)
            version = draft_service.next_chapter_draft_version(chapter_id)
            version_label = f"ver{version}"
            draft_path = self.store.data_dir / "drafts" / f"{safe_filename(chapter_id)}__{version_label}__{new_id}.json"
            artifact = {
                "schema_version": 1,
                "status": "draft",
                "draft_id": new_id,
                "chapter_id": chapter_id,
                "title": title,
                "version": version,
                "version_label": version_label,
                "created_at": created_at,
                "content": response.text,
                "provider": {
                    "role": "reviser",
                    "provider": response.provider,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                },
                "revision": {
                    "source_draft_id": draft_id,
                    "source_review_id": review_id,
                    "revision_request_id": revision_request_id,
                    "mode": "mock_revision_candidate",
                },
                "request_summary": {
                    "source_draft_chars": len(source_content),
                    "metadata_keys": ["chapter_id", "revision_draft", "revision_request_id", "review_id", "source_draft_id"],
                },
            }
            self.store.write_json(draft_path, artifact)
            self._append_draft_index_entry(
                {
                    "draft_id": new_id,
                    "chapter_id": chapter_id,
                    "title": title,
                    "created_at": created_at,
                    "status": "draft",
                    "version": version,
                    "version_label": version_label,
                    "path": str(draft_path.relative_to(self.store.root)),
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage,
                    "revision": {
                        "source_draft_id": draft_id,
                        "source_review_id": review_id,
                        "revision_request_id": revision_request_id,
                    },
                }
            )
            request_artifact["status"] = "draft_created"
            request_artifact["generated_draft_id"] = new_id
            request_artifact["updated_at"] = created_at
            self.store.write_json(str(request_entry["path"]), request_artifact)
            self._update_request_index_entry(
                revision_request_id,
                {
                    "status": "draft_created",
                    "generated_draft_id": new_id,
                    "updated_at": created_at,
                },
            )
            ChapterWorkflowService(self.store).mark_revision_draft_ready(
                chapter_id,
                title=title,
                draft_id=new_id,
                review_id=review_id,
                revision_request_id=revision_request_id,
            )
            return DraftGenerationResult(
                draft_id=new_id,
                chapter_id=chapter_id,
                title=title,
                path=str(draft_path),
                provider=response.provider,
                model=response.model,
                usage=response.usage,
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

    def _request_index_entry(self, revision_request_id: str) -> dict[str, Any]:
        for item in self.list_revision_requests():
            if item.get("revision_request_id") == revision_request_id:
                return item
        raise RevisionRequestError(f"Revision request not found: {revision_request_id}")

    def _update_request_index_entry(self, revision_request_id: str, updates: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "revision_requests": []})
        items = index.get("revision_requests") if isinstance(index, dict) and isinstance(index.get("revision_requests"), list) else []
        updated: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict) and item.get("revision_request_id") == revision_request_id:
                item = {**item, **updates}
            if isinstance(item, dict):
                updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "revision_requests": updated})

    def _append_draft_index_entry(self, entry: dict[str, Any]) -> None:
        path = self.store.data_dir / "drafts_index.json"
        index = self.store.read_json(path, default={"schema_version": 1, "drafts": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "drafts": []}
        drafts = index.get("drafts") if isinstance(index.get("drafts"), list) else []
        drafts.append(entry)
        self.store.write_json(path, {"schema_version": 1, "drafts": drafts})

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
