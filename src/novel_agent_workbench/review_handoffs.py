from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .drafts import DraftGenerationService, validate_chapter_id
from .manual_rewrite_comparison import ManualRewriteComparisonService
from .storage import ProjectStore, safe_filename, utc_stamp


REVIEW_HANDOFFS_DIRNAME = "review_handoffs"
REVIEW_HANDOFFS_INDEX_FILENAME = "review_handoffs_index.json"


class ReviewHandoffError(RuntimeError):
    """Raised when a selected manual rewrite candidate cannot be handed off safely."""


@dataclass(frozen=True, slots=True)
class ReviewHandoffResult:
    handoff_id: str
    comparison_id: str
    task_id: str
    chapter_id: str
    selected_draft_id: str
    status: str
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReviewHandoffService:
    """Metadata-only queue from selected manual rewrite candidates to later explicit review."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.comparisons = ManualRewriteComparisonService(store)
        self.drafts = DraftGenerationService(store)

    @property
    def handoffs_dir(self) -> Path:
        return self.store.data_dir / REVIEW_HANDOFFS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / REVIEW_HANDOFFS_INDEX_FILENAME

    def create_from_manual_comparison(self, comparison_id: str) -> ReviewHandoffResult:
        self.store.initialize()
        with self.store.lock():
            if self._find_by_comparison_id(comparison_id) is not None:
                raise ReviewHandoffError(f"Manual rewrite comparison already has a review handoff: {comparison_id}")
            comparison = self.comparisons.read_comparison(comparison_id)
            if str(comparison.get("status") or "") != "selected_for_review":
                raise ReviewHandoffError("Review handoff requires a selected_for_review manual comparison.")
            decision = comparison.get("decision") if isinstance(comparison.get("decision"), dict) else {}
            if str(decision.get("status") or "") != "selected_for_review":
                raise ReviewHandoffError("Review handoff requires a selected_for_review decision.")
            selected_draft_id = str(comparison.get("submitted_draft_id") or "")
            if not selected_draft_id:
                raise ReviewHandoffError(f"Manual rewrite comparison has no submitted draft: {comparison_id}")
            selected_draft = self.drafts.read_draft(selected_draft_id)
            chapter_id = str(comparison.get("chapter_id") or selected_draft.get("chapter_id") or "")
            validate_chapter_id(chapter_id)
            if str(selected_draft.get("chapter_id") or "") != chapter_id:
                raise ReviewHandoffError("Selected draft chapter_id does not match the comparison.")
            created_at = utc_stamp()
            handoff_id = f"{created_at}_{uuid4().hex[:12]}"
            path = self.handoffs_dir / f"{safe_filename(chapter_id)}__{safe_filename(handoff_id)}.json"
            artifact = {
                "schema_version": 1,
                "handoff_id": handoff_id,
                "comparison_id": comparison_id,
                "task_id": str(comparison.get("task_id") or ""),
                "suggestion_id": str(comparison.get("suggestion_id") or ""),
                "check_id": str(comparison.get("check_id") or ""),
                "chapter_id": chapter_id,
                "title": str(comparison.get("title") or selected_draft.get("title") or ""),
                "source_draft_id": str(comparison.get("source_draft_id") or ""),
                "selected_draft_id": selected_draft_id,
                "status": "pending_review",
                "created_at": created_at,
                "updated_at": created_at,
                "review": {"review_id": "", "created": False},
                "source_decision": {
                    "status": str(decision.get("status") or ""),
                    "reason_code": str(decision.get("reason_code") or ""),
                    "decided_at": str(decision.get("decided_at") or ""),
                },
                "safety": review_handoff_safety(),
            }
            self.store.write_json(path, artifact)
            self._append_index_entry(
                {
                    "handoff_id": handoff_id,
                    "comparison_id": comparison_id,
                    "task_id": artifact["task_id"],
                    "suggestion_id": artifact["suggestion_id"],
                    "check_id": artifact["check_id"],
                    "chapter_id": chapter_id,
                    "title": artifact["title"],
                    "source_draft_id": artifact["source_draft_id"],
                    "selected_draft_id": selected_draft_id,
                    "status": "pending_review",
                    "created_at": created_at,
                    "updated_at": created_at,
                    "path": str(path.relative_to(self.store.root)),
                    "review": artifact["review"],
                    "safety": artifact["safety"],
                }
            )
            return ReviewHandoffResult(
                handoff_id=handoff_id,
                comparison_id=comparison_id,
                task_id=artifact["task_id"],
                chapter_id=chapter_id,
                selected_draft_id=selected_draft_id,
                status="pending_review",
                path=str(path),
                created_at=created_at,
            )

    def list_handoffs(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "review_handoffs": []})
        if not isinstance(index, dict):
            return []
        items = index.get("review_handoffs")
        if not isinstance(items, list):
            return []
        handoffs = [item for item in items if isinstance(item, dict)]
        if status:
            handoffs = [item for item in handoffs if item.get("status") == status]
        return handoffs

    def read_handoff(self, handoff_id: str) -> dict[str, Any]:
        entry = self._handoff_index_entry(handoff_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise ReviewHandoffError(f"Review handoff index entry has no path: {handoff_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise ReviewHandoffError(f"Review handoff artifact is missing or invalid: {handoff_id}")
        return artifact

    def mark_review_created_unlocked(self, handoff_id: str, *, review_id: str, created_at: str) -> dict[str, Any]:
        entry = self._handoff_index_entry(handoff_id)
        artifact = self.read_handoff(handoff_id)
        if str(artifact.get("status") or "") != "pending_review":
            raise ReviewHandoffError(f"Review handoff is not pending review: {handoff_id}")
        review = {
            "review_id": str(review_id or ""),
            "created": True,
            "created_at": created_at,
        }
        artifact["status"] = "review_created"
        artifact["updated_at"] = created_at
        artifact["review"] = review
        self.store.write_json(str(entry["path"]), artifact)
        self._update_index_entry(
            handoff_id,
            {
                "status": "review_created",
                "updated_at": created_at,
                "review": review,
            },
        )
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_handoffs()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "review_handoffs": items})

    def _handoff_index_entry(self, handoff_id: str) -> dict[str, Any]:
        for item in self.list_handoffs():
            if item.get("handoff_id") == handoff_id:
                return item
        raise ReviewHandoffError(f"Review handoff not found: {handoff_id}")

    def _find_by_comparison_id(self, comparison_id: str) -> dict[str, Any] | None:
        for item in self.list_handoffs():
            if item.get("comparison_id") == comparison_id:
                return item
        return None

    def _update_index_entry(self, handoff_id: str, updates: dict[str, Any]) -> None:
        updated: list[dict[str, Any]] = []
        for item in self.list_handoffs():
            if item.get("handoff_id") == handoff_id:
                item = {**item, **updates}
            updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "review_handoffs": updated})


def review_handoff_safety() -> dict[str, bool]:
    return {
        "local_only": True,
        "provider_called": False,
        "external_corpus_used": False,
        "source_text_stored": False,
        "selected_text_stored": False,
        "prompt_text_stored": False,
        "secret_text_stored": False,
        "auto_review": False,
        "auto_apply": False,
        "auto_generate_draft": False,
        "auto_revision_request": False,
        "auto_commit": False,
        "confirmed_touched": False,
        "memory_bank_touched": False,
        "rag_touched": False,
        "exports_touched": False,
    }
