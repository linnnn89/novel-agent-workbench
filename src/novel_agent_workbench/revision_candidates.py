from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .drafts import DraftGenerationService
from .revisions import RevisionRequestService
from .storage import ProjectStore


class RevisionCandidateError(RuntimeError):
    """Raised when revision candidate metadata cannot be read safely."""


@dataclass(frozen=True, slots=True)
class RevisionCandidateSummary:
    draft_id: str
    chapter_id: str
    title: str
    status: str
    created_at: str
    provider: str
    model: str
    usage: dict[str, int]
    char_count: int
    word_count: int
    line_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RevisionCandidateComparison:
    revision_request_id: str
    chapter_id: str
    source_draft: dict[str, Any]
    candidate_draft: dict[str, Any]
    deltas: dict[str, int]
    link_check: dict[str, bool]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RevisionCandidateService:
    """Read-only comparison surface for revision draft candidates."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.drafts = DraftGenerationService(store)
        self.requests = RevisionRequestService(store)

    def list_revision_candidates(self, revision_request_id: str) -> dict[str, Any]:
        request = self.requests.read_revision_request(revision_request_id)
        candidates = [
            self._summary_for_draft_id(str(item.get("draft_id") or "")).to_dict()
            for item in self.drafts.list_drafts()
            if self._is_candidate_entry(item, revision_request_id)
        ]
        return {
            "revision_request_id": revision_request_id,
            "chapter_id": str(request.get("chapter_id") or ""),
            "source_draft_id": str(request.get("draft_id") or ""),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    def compare_revision_candidate(
        self, revision_request_id: str, candidate_draft_id: str
    ) -> RevisionCandidateComparison:
        request = self.requests.read_revision_request(revision_request_id)
        source_draft_id = str(request.get("draft_id") or "")
        review_id = str(request.get("review_id") or "")
        chapter_id = str(request.get("chapter_id") or "")
        source = self.drafts.read_draft(source_draft_id)
        candidate = self.drafts.read_draft(candidate_draft_id)
        revision_meta = candidate.get("revision") if isinstance(candidate.get("revision"), dict) else {}
        link_check = {
            "revision_request_id": str(revision_meta.get("revision_request_id") or "") == revision_request_id,
            "source_draft_id": str(revision_meta.get("source_draft_id") or "") == source_draft_id,
            "source_review_id": str(revision_meta.get("source_review_id") or "") == review_id,
            "chapter_id": str(candidate.get("chapter_id") or "") == chapter_id,
        }
        if not all(link_check.values()):
            raise RevisionCandidateError(f"Draft is not a candidate for revision request: {candidate_draft_id}")
        source_summary = self._summary_for_artifact(source).to_dict()
        candidate_summary = self._summary_for_artifact(candidate).to_dict()
        return RevisionCandidateComparison(
            revision_request_id=revision_request_id,
            chapter_id=chapter_id,
            source_draft=source_summary,
            candidate_draft=candidate_summary,
            deltas={
                "char_count": int(candidate_summary["char_count"]) - int(source_summary["char_count"]),
                "word_count": int(candidate_summary["word_count"]) - int(source_summary["word_count"]),
                "line_count": int(candidate_summary["line_count"]) - int(source_summary["line_count"]),
            },
            link_check=link_check,
            recommendation="manual_review_required",
        )

    def _is_candidate_entry(self, entry: dict[str, Any], revision_request_id: str) -> bool:
        revision = entry.get("revision") if isinstance(entry.get("revision"), dict) else {}
        return str(revision.get("revision_request_id") or "") == revision_request_id and bool(entry.get("draft_id"))

    def _summary_for_draft_id(self, draft_id: str) -> RevisionCandidateSummary:
        if not draft_id:
            raise RevisionCandidateError("Candidate draft id is missing.")
        return self._summary_for_artifact(self.drafts.read_draft(draft_id))

    def _summary_for_artifact(self, artifact: dict[str, Any]) -> RevisionCandidateSummary:
        provider = artifact.get("provider") if isinstance(artifact.get("provider"), dict) else {}
        content = str(artifact.get("content") or "")
        return RevisionCandidateSummary(
            draft_id=str(artifact.get("draft_id") or ""),
            chapter_id=str(artifact.get("chapter_id") or ""),
            title=str(artifact.get("title") or ""),
            status=str(artifact.get("status") or ""),
            created_at=str(artifact.get("created_at") or ""),
            provider=str(provider.get("provider") or ""),
            model=str(provider.get("model") or ""),
            usage=provider.get("usage") if isinstance(provider.get("usage"), dict) else {},
            char_count=len(content),
            word_count=len(content.split()),
            line_count=count_lines(content),
        )


def count_lines(value: str) -> int:
    if not value:
        return 0
    return len(value.splitlines()) or 1
