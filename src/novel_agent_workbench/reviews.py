from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chapters import ChapterWorkflowService
from .drafts import DraftGenerationService, validate_chapter_id
from .providers import ProviderRequest, generate_with_provider
from .storage import ProjectStore, safe_filename, utc_stamp


REVIEWS_DIRNAME = "reviews"
REVIEWS_INDEX_FILENAME = "reviews_index.json"
REVIEW_DECISIONS = {"accepted", "needs_revision", "blocked"}


class DraftReviewError(RuntimeError):
    """Raised when a draft review cannot be produced safely."""


@dataclass(frozen=True, slots=True)
class DraftReviewResult:
    review_id: str
    draft_id: str
    chapter_id: str
    status: str
    path: str
    provider: str
    model: str
    usage: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReviewDecisionResult:
    review_id: str
    draft_id: str
    chapter_id: str
    decision: str
    reason_code: str
    decided_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DraftReviewService:
    """Metadata-only quality review service for draft artifacts."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def reviews_dir(self) -> Path:
        return self.store.data_dir / REVIEWS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / REVIEWS_INDEX_FILENAME

    def review_draft(self, draft_id: str) -> DraftReviewResult:
        self.store.initialize()
        with self.store.lock():
            draft_service = DraftGenerationService(self.store)
            draft = draft_service.read_draft(draft_id)
            chapter_id = str(draft.get("chapter_id") or "").strip()
            validate_chapter_id(chapter_id)
            title = str(draft.get("title") or "")
            workflow = ChapterWorkflowService(self.store)
            chapter = workflow.get_chapter(chapter_id)
            if chapter.get("status") == "blocked":
                raise DraftReviewError(f"Chapter is blocked and cannot be reviewed: {chapter_id}")
            if self._find_by_draft_id(draft_id) is not None:
                raise DraftReviewError(f"Draft already has a review: {draft_id}")
            content = str(draft.get("content") or "")
            created_at = utc_stamp()
            try:
                response = generate_with_provider(
                    self.store,
                    ProviderRequest(
                        role="scorer",
                        prompt=f"Review draft metadata only. draft_chars={len(content)}",
                        max_tokens=64,
                        metadata={
                            "draft_review": True,
                            "chapter_id": chapter_id,
                            "draft_id": draft_id,
                        },
                    ),
                )
            except Exception as exc:
                workflow.record_error(
                    chapter_id,
                    title=title,
                    stage="review_draft",
                    error_type=getattr(exc, "error_type", exc.__class__.__name__),
                    message=str(exc),
                )
                raise

            review_id = new_review_id()
            review_path = self.reviews_dir / f"{safe_filename(chapter_id)}__{review_id}.json"
            status = "review_ready"
            artifact = {
                "schema_version": 1,
                "review_id": review_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "status": status,
                "created_at": created_at,
                "scores": mock_scores(response.text),
                "issues": [
                    {
                        "code": "mock_scorer",
                        "severity": "info",
                        "message": "Mock scorer completed metadata-only review.",
                    }
                ],
                "recommendation": "manual_review_required",
                "comment": safe_review_comment(response.text),
                "decision": pending_decision(),
                "provider": {
                    "role": "scorer",
                    "provider": response.provider,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                },
                "request_summary": {
                    "draft_chars": len(content),
                    "metadata_keys": ["chapter_id", "draft_id", "draft_review"],
                },
            }
            self.store.write_json(review_path, artifact)
            self._append_index_entry(
                {
                    "review_id": review_id,
                    "draft_id": draft_id,
                    "chapter_id": chapter_id,
                    "status": status,
                    "created_at": created_at,
                    "path": str(review_path.relative_to(self.store.root)),
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage,
                    "recommendation": "manual_review_required",
                    "decision": pending_decision(),
                }
            )
            workflow.mark_review_ready(chapter_id, title=title, draft_id=draft_id, review_id=review_id)
            return DraftReviewResult(
                review_id=review_id,
                draft_id=draft_id,
                chapter_id=chapter_id,
                status=status,
                path=str(review_path),
                provider=response.provider,
                model=response.model,
                usage=response.usage,
            )

    def decide_review(self, review_id: str, *, decision: str, reason_code: str = "") -> ReviewDecisionResult:
        self.store.initialize()
        with self.store.lock():
            decision = validate_review_decision(decision)
            reason_code = validate_reason_code(reason_code)
            review_entry = self._review_index_entry(review_id)
            review = self.read_review(review_id)
            existing = review.get("decision") if isinstance(review.get("decision"), dict) else {}
            if str(existing.get("status") or "pending") != "pending":
                raise DraftReviewError(f"Review already has a manual decision: {review_id}")
            draft_id = str(review.get("draft_id") or review_entry.get("draft_id") or "")
            chapter_id = str(review.get("chapter_id") or review_entry.get("chapter_id") or "")
            validate_chapter_id(chapter_id)
            draft = DraftGenerationService(self.store).read_draft(draft_id)
            decided_at = utc_stamp()
            decision_summary = {
                "status": decision,
                "reason_code": reason_code,
                "decided_at": decided_at,
            }
            review["decision"] = decision_summary
            self.store.write_json(str(review_entry["path"]), review)
            self._update_index_decision(review_id, decision_summary)
            ChapterWorkflowService(self.store).mark_review_decision(
                chapter_id,
                title=str(draft.get("title") or ""),
                draft_id=draft_id,
                review_id=review_id,
                decision=decision,
                reason_code=reason_code,
                decided_at=decided_at,
            )
            return ReviewDecisionResult(
                review_id=review_id,
                draft_id=draft_id,
                chapter_id=chapter_id,
                decision=decision,
                reason_code=reason_code,
                decided_at=decided_at,
            )

    def list_reviews(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "reviews": []})
        if not isinstance(index, dict):
            return []
        reviews = index.get("reviews")
        if not isinstance(reviews, list):
            return []
        return [item for item in reviews if isinstance(item, dict)]

    def read_review(self, review_id: str) -> dict[str, Any]:
        for item in self.list_reviews():
            if item.get("review_id") != review_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise DraftReviewError(f"Review index entry has no path: {review_id}")
            review = self.store.read_json(path, default=None)
            if not isinstance(review, dict):
                raise DraftReviewError(f"Review artifact is missing or invalid: {review_id}")
            return review
        raise DraftReviewError(f"Review not found: {review_id}")

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "reviews": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "reviews": []}
        reviews = index.get("reviews") if isinstance(index.get("reviews"), list) else []
        reviews.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "reviews": reviews})

    def _review_index_entry(self, review_id: str) -> dict[str, Any]:
        for item in self.list_reviews():
            if item.get("review_id") == review_id:
                return item
        raise DraftReviewError(f"Review not found: {review_id}")

    def _update_index_decision(self, review_id: str, decision: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "reviews": []})
        reviews = index.get("reviews") if isinstance(index, dict) and isinstance(index.get("reviews"), list) else []
        updated: list[dict[str, Any]] = []
        for item in reviews:
            if isinstance(item, dict) and item.get("review_id") == review_id:
                item = {**item, "decision": decision}
            if isinstance(item, dict):
                updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "reviews": updated})

    def _find_by_draft_id(self, draft_id: str) -> dict[str, Any] | None:
        for item in self.list_reviews():
            if item.get("draft_id") == draft_id:
                return item
        return None


def new_review_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"


def pending_decision() -> dict[str, str]:
    return {"status": "pending", "reason_code": "", "decided_at": ""}


def validate_review_decision(decision: str) -> str:
    value = str(decision or "").strip()
    if value not in REVIEW_DECISIONS:
        raise DraftReviewError(f"Invalid review decision: {decision!r}")
    return value


def validate_reason_code(reason_code: str) -> str:
    value = str(reason_code or "").strip()
    if not value:
        return ""
    if len(value) > 80:
        raise DraftReviewError("reason_code is too long.")
    if not all(character.isascii() and (character.isalnum() or character in {"_", "-"}) for character in value):
        raise DraftReviewError("reason_code must use ASCII letters, numbers, '_' or '-'.")
    return value


def mock_scores(text: str) -> dict[str, float]:
    return {"overall": 0.0 if "score=0" in text else 0.5}


def safe_review_comment(text: str) -> str:
    value = " ".join(str(text or "").split())
    if "MOCK scorer result" in value:
        return "Mock scorer result recorded; manual review is required."
    return "Scorer result recorded; manual review is required."
