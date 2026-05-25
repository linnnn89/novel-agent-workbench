from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .chapters import ChapterWorkflowService
from .config import DEFAULT_REVIEW_SYSTEM_PROMPT, DEFAULT_REVIEW_TASK_PROMPT, effective_generation_settings
from .drafts import (
    DraftGenerationService,
    grouped_context_sections,
    sanitize_provider_draft_text,
    stream_sanitizer_callback,
    validate_chapter_id,
)
from .manual_rewrite_comparison import ManualRewriteComparisonService
from .providers import ProviderRequest, generate_with_provider, provider_request_role_or_writer_fallback
from .review_handoffs import ReviewHandoffService
from .storage import ProjectStore, safe_filename, utc_stamp


REVIEWS_DIRNAME = "reviews"
REVIEWS_INDEX_FILENAME = "reviews_index.json"
REVIEW_DECISIONS = {"accepted", "needs_revision", "blocked"}
REASONING_LEAK_DECISION = "needs_revision"
REASONING_LEAK_REASON_CODE = "reasoning_leak"
REASONING_LEAK_ISSUE_CODE = "reasoning_leak_detected"
AI_REVIEW_TYPE = "ai"
AI_REVIEW_SYSTEM_PROMPT = DEFAULT_REVIEW_SYSTEM_PROMPT


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
            gate = manual_rewrite_review_gate(self.store, draft)
            if gate["required"] and not gate["allowed"]:
                raise DraftReviewError(
                    "Manual rewrite submitted draft requires selected_for_review comparison "
                    "or pending_review handoff before review."
                )
            content = str(draft.get("content") or "")
            created_at = utc_stamp()
            if contains_reasoning_leak(content):
                return self._create_reasoning_leak_review(
                    draft_id=draft_id,
                    chapter_id=chapter_id,
                    title=title,
                    content_chars=len(content),
                    gate=gate,
                    created_at=created_at,
                )
            if not review_scorer_enabled(self.store.read_config()):
                return self._create_manual_pending_review(
                    draft_id=draft_id,
                    chapter_id=chapter_id,
                    title=title,
                    content_chars=len(content),
                    gate=gate,
                    created_at=created_at,
                )
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
                    "manual_rewrite_review_gate": gate,
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
            if gate.get("matched_gate") == "pending_review_handoff" and gate.get("handoff_id"):
                ReviewHandoffService(self.store).mark_review_created_unlocked(
                    str(gate["handoff_id"]),
                    review_id=review_id,
                    created_at=created_at,
                )
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

    def ai_review_draft(
        self,
        draft_id: str,
        *,
        max_context_tokens: int | None = None,
        stream: bool | None = None,
        stream_callback: Any | None = None,
        reasoning_callback: Any | None = None,
        extra_instruction: str = "",
    ) -> DraftReviewResult:
        self.store.initialize()
        with self.store.lock():
            draft_service = DraftGenerationService(self.store)
            draft = draft_service.read_draft(draft_id)
            chapter_id = str(draft.get("chapter_id") or "").strip()
            validate_chapter_id(chapter_id)
            title = str(draft.get("title") or "")
            workflow = ChapterWorkflowService(self.store)
            workflow.get_chapter(chapter_id)
            gate = manual_rewrite_review_gate(self.store, draft)
            if gate["required"] and not gate["allowed"]:
                raise DraftReviewError(
                    "Manual rewrite submitted draft requires selected_for_review comparison "
                    "or pending_review handoff before AI review."
                )
            from .context_assembler import ContextAssemblerService

            config = self.store.read_config()
            raw_content = str(draft.get("content") or "")
            draft_sanitized = sanitize_provider_draft_text(raw_content)
            review_system_prompt = ai_review_system_prompt(config)
            review_task_template = ai_review_task_prompt_template(config)
            task_prompt = ai_review_task_prompt(
                chapter_id=chapter_id,
                title=title,
                template=review_task_template,
                extra_instruction=extra_instruction,
            )
            render = ContextAssemblerService(self.store).prompt_render_dry_run(
                prompt=task_prompt,
                system_prompt=review_system_prompt,
                max_context_tokens=max_context_tokens,
                chapter_id=chapter_id,
                include_prompt_text=True,
                include_context_text=True,
            ).to_dict()
            provider_prompt = render_ai_review_prompt(
                render,
                draft,
                draft_sanitized["content"],
                review_prompt=task_prompt,
            )
            request_role = provider_request_role_or_writer_fallback(self.store, "scorer")
            safe_stream_callback = stream_sanitizer_callback(stream_callback, reasoning_callback)
            try:
                response = generate_with_provider(
                    self.store,
                    ProviderRequest(
                        role=request_role,
                        prompt=provider_prompt,
                        system_prompt=review_system_prompt,
                        max_tokens=2048,
                        stream=stream,
                        stream_callback=safe_stream_callback,
                        metadata={
                            "ai_review": True,
                            "chapter_id": chapter_id,
                            "draft_id": draft_id,
                            "context_aware_review": True,
                        },
                    ),
                )
            except Exception as exc:
                workflow.record_error(
                    chapter_id,
                    title=title,
                    stage="ai_review_draft",
                    error_type=getattr(exc, "error_type", exc.__class__.__name__),
                    message=str(exc),
                )
                raise

            created_at = utc_stamp()
            review_id = new_review_id()
            review_path = self.reviews_dir / f"{safe_filename(chapter_id)}__{review_id}.json"
            status = "ai_review_ready"
            response_sanitized = sanitize_provider_draft_text(response.text)
            comment = response_sanitized["content"] or "AI 审稿未返回可显示的意见。"
            context_stats = render_context_stats(render)
            artifact = {
                "schema_version": 1,
                "review_type": AI_REVIEW_TYPE,
                "review_id": review_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "status": status,
                "created_at": created_at,
                "scores": mock_scores(response.text),
                "issues": [
                    {
                        "code": "ai_review_completed",
                        "severity": "info",
                        "message": "AI review completed with draft text and active context.",
                    }
                ],
                "recommendation": "ai_review_completed",
                "comment": comment,
                "decision": pending_decision(),
                "provider": {
                    "role": "scorer",
                    "provider": response.provider,
                    "model": response.model,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage,
                },
                "request_summary": {
                    "review_type": AI_REVIEW_TYPE,
                    "draft_chars": len(raw_content),
                    "provider_draft_chars": len(draft_sanitized["content"]),
                    "prompt_chars": len(provider_prompt),
                    "provider_request_role": request_role,
                    "logical_role": "scorer",
                    "metadata_keys": ["ai_review", "chapter_id", "context_aware_review", "draft_id"],
                    "manual_rewrite_review_gate": gate,
                    "draft_text_sanitizer": draft_sanitized["summary"],
                    "response_sanitizer": response_sanitized["summary"],
                    "extra_instruction_chars": len(str(extra_instruction or "").strip()),
                    **context_stats,
                },
            }
            self.store.write_json(review_path, artifact)
            self._append_index_entry(
                {
                    "review_id": review_id,
                    "review_type": AI_REVIEW_TYPE,
                    "draft_id": draft_id,
                    "chapter_id": chapter_id,
                    "status": status,
                    "created_at": created_at,
                    "path": str(review_path.relative_to(self.store.root)),
                    "provider": response.provider,
                    "model": response.model,
                    "usage": response.usage,
                    "recommendation": "ai_review_completed",
                    "decision": pending_decision(),
                }
            )
            workflow.mark_review_ready(chapter_id, title=title, draft_id=draft_id, review_id=review_id)
            if gate.get("matched_gate") == "pending_review_handoff" and gate.get("handoff_id"):
                ReviewHandoffService(self.store).mark_review_created_unlocked(
                    str(gate["handoff_id"]),
                    review_id=review_id,
                    created_at=created_at,
                )
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

    def _create_manual_pending_review(
        self,
        *,
        draft_id: str,
        chapter_id: str,
        title: str,
        content_chars: int,
        gate: dict[str, Any],
        created_at: str,
    ) -> DraftReviewResult:
        review_id = new_review_id()
        review_path = self.reviews_dir / f"{safe_filename(chapter_id)}__{review_id}.json"
        status = "review_ready"
        decision = pending_decision()
        artifact = {
            "schema_version": 1,
            "review_id": review_id,
            "draft_id": draft_id,
            "chapter_id": chapter_id,
            "status": status,
            "created_at": created_at,
            "scores": {},
            "issues": [
                {
                    "code": "scorer_optional_disabled",
                    "severity": "info",
                    "message": "Scoring model is disabled by global settings; manual review is required.",
                }
            ],
            "recommendation": "manual_review_required",
            "comment": "评分模型未启用；请人工确认、重写或阻断。",
            "decision": decision,
            "provider": {"role": "scorer", "provider": "manual", "model": "", "finish_reason": "", "usage": {}},
            "request_summary": {
                "draft_chars": content_chars,
                "metadata_keys": ["chapter_id", "draft_id", "manual_review"],
                "manual_rewrite_review_gate": gate,
                "scorer_enabled": False,
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
                "provider": "manual",
                "model": "",
                "usage": {},
                "recommendation": "manual_review_required",
                "decision": decision,
            }
        )
        ChapterWorkflowService(self.store).mark_review_ready(chapter_id, title=title, draft_id=draft_id, review_id=review_id)
        return DraftReviewResult(
            review_id=review_id,
            draft_id=draft_id,
            chapter_id=chapter_id,
            status=status,
            path=str(review_path),
            provider="manual",
            model="",
            usage={},
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

    def accept_draft_manually(self, draft_id: str, *, reason_code: str = "desktop_confirm") -> ReviewDecisionResult:
        self.store.initialize()
        with self.store.lock():
            reason_code = validate_reason_code(reason_code)
            draft = DraftGenerationService(self.store).read_draft(draft_id)
            chapter_id = str(draft.get("chapter_id") or "").strip()
            validate_chapter_id(chapter_id)
            title = str(draft.get("title") or "")
            existing_entry = self._find_by_draft_id(draft_id)
            if existing_entry is not None:
                review = self.read_review(str(existing_entry.get("review_id") or ""))
                existing = review.get("decision") if isinstance(review.get("decision"), dict) else {}
                status = str(existing.get("status") or "pending")
                if status == "accepted":
                    return ReviewDecisionResult(
                        review_id=str(review.get("review_id") or existing_entry.get("review_id") or ""),
                        draft_id=draft_id,
                        chapter_id=chapter_id,
                        decision="accepted",
                        reason_code=str(existing.get("reason_code") or ""),
                        decided_at=str(existing.get("decided_at") or ""),
                    )
                if status != "pending":
                    raise DraftReviewError(f"Draft review is not manually acceptable: {draft_id}")
                decided_at = utc_stamp()
                decision_summary = {"status": "accepted", "reason_code": reason_code, "decided_at": decided_at}
                review["decision"] = decision_summary
                self.store.write_json(str(existing_entry["path"]), review)
                self._update_index_decision(str(existing_entry["review_id"]), decision_summary)
                ChapterWorkflowService(self.store).mark_review_decision(
                    chapter_id,
                    title=title,
                    draft_id=draft_id,
                    review_id=str(existing_entry["review_id"]),
                    decision="accepted",
                    reason_code=reason_code,
                    decided_at=decided_at,
                )
                return ReviewDecisionResult(
                    review_id=str(existing_entry["review_id"]),
                    draft_id=draft_id,
                    chapter_id=chapter_id,
                    decision="accepted",
                    reason_code=reason_code,
                    decided_at=decided_at,
                )

            created_at = utc_stamp()
            review_id = new_review_id()
            review_path = self.reviews_dir / f"{safe_filename(chapter_id)}__{review_id}.json"
            decision_summary = {"status": "accepted", "reason_code": reason_code, "decided_at": created_at}
            artifact = {
                "schema_version": 1,
                "review_id": review_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "status": "manual_review_ready",
                "created_at": created_at,
                "scores": {"overall": 1.0},
                "issues": [],
                "recommendation": "user_confirmed",
                "comment": "User accepted this draft in the desktop editor.",
                "decision": decision_summary,
                "provider": {"role": "user", "provider": "manual", "model": "desktop", "finish_reason": "", "usage": {}},
                "request_summary": {
                    "draft_chars": len(str(draft.get("content") or "")),
                    "metadata_keys": ["draft_id", "chapter_id", "manual_confirm"],
                },
            }
            self.store.write_json(review_path, artifact)
            self._append_index_entry(
                {
                    "review_id": review_id,
                    "draft_id": draft_id,
                    "chapter_id": chapter_id,
                    "status": "manual_review_ready",
                    "created_at": created_at,
                    "path": str(review_path.relative_to(self.store.root)),
                    "provider": "manual",
                    "model": "desktop",
                    "usage": {},
                    "recommendation": "user_confirmed",
                    "decision": decision_summary,
                }
            )
            workflow = ChapterWorkflowService(self.store)
            workflow.mark_review_ready(chapter_id, title=title, draft_id=draft_id, review_id=review_id)
            workflow.mark_review_decision(
                chapter_id,
                title=title,
                draft_id=draft_id,
                review_id=review_id,
                decision="accepted",
                reason_code=reason_code,
                decided_at=created_at,
            )
            return ReviewDecisionResult(
                review_id=review_id,
                draft_id=draft_id,
                chapter_id=chapter_id,
                decision="accepted",
                reason_code=reason_code,
                decided_at=created_at,
            )

    def _create_reasoning_leak_review(
        self,
        *,
        draft_id: str,
        chapter_id: str,
        title: str,
        content_chars: int,
        gate: dict[str, Any],
        created_at: str,
    ) -> DraftReviewResult:
        review_id = new_review_id()
        review_path = self.reviews_dir / f"{safe_filename(chapter_id)}__{review_id}.json"
        decision = {
            "status": REASONING_LEAK_DECISION,
            "reason_code": REASONING_LEAK_REASON_CODE,
            "decided_at": created_at,
        }
        artifact = {
            "schema_version": 1,
            "review_id": review_id,
            "draft_id": draft_id,
            "chapter_id": chapter_id,
            "status": "review_ready",
            "created_at": created_at,
            "scores": {"overall": 0.0},
            "issues": [
                {
                    "code": REASONING_LEAK_ISSUE_CODE,
                    "severity": "blocker",
                    "message": "Reasoning markup was detected; manual revision is required.",
                }
            ],
            "recommendation": "manual_revision_required",
            "comment": "Reasoning leak guard blocked this draft from acceptance.",
            "decision": decision,
            "provider": {
                "role": "scorer",
                "provider": "local_guard",
                "model": "reasoning-leak-guard",
                "finish_reason": "guard_triggered",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
            "request_summary": {
                "draft_chars": content_chars,
                "metadata_keys": ["chapter_id", "draft_id", "reasoning_leak_guard"],
                "manual_rewrite_review_gate": gate,
                "reasoning_leak_guard": {
                    "checked": True,
                    "triggered": True,
                    "decision": REASONING_LEAK_DECISION,
                    "reason_code": REASONING_LEAK_REASON_CODE,
                },
            },
        }
        self.store.write_json(review_path, artifact)
        self._append_index_entry(
            {
                "review_id": review_id,
                "draft_id": draft_id,
                "chapter_id": chapter_id,
                "status": "review_ready",
                "created_at": created_at,
                "path": str(review_path.relative_to(self.store.root)),
                "provider": "local_guard",
                "model": "reasoning-leak-guard",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "recommendation": "manual_revision_required",
                "decision": decision,
            }
        )
        workflow = ChapterWorkflowService(self.store)
        workflow.mark_review_ready(chapter_id, title=title, draft_id=draft_id, review_id=review_id)
        workflow.mark_review_decision(
            chapter_id,
            title=title,
            draft_id=draft_id,
            review_id=review_id,
            decision=REASONING_LEAK_DECISION,
            reason_code=REASONING_LEAK_REASON_CODE,
            decided_at=created_at,
        )
        if gate.get("matched_gate") == "pending_review_handoff" and gate.get("handoff_id"):
            ReviewHandoffService(self.store).mark_review_created_unlocked(
                str(gate["handoff_id"]),
                review_id=review_id,
                created_at=created_at,
            )
        return DraftReviewResult(
            review_id=review_id,
            draft_id=draft_id,
            chapter_id=chapter_id,
            status="review_ready",
            path=str(review_path),
            provider="local_guard",
            model="reasoning-leak-guard",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
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

    def find_review_for_draft(self, draft_id: str) -> dict[str, Any] | None:
        entry = self._find_by_draft_id(draft_id)
        if entry is None:
            return None
        review_id = str(entry.get("review_id") or "")
        if not review_id:
            return None
        return self.read_review(review_id)

    def find_ai_review_for_draft(self, draft_id: str) -> dict[str, Any] | None:
        for entry in reversed(self.list_reviews()):
            if entry.get("draft_id") != draft_id:
                continue
            review_id = str(entry.get("review_id") or "")
            if not review_id:
                continue
            review = self.read_review(review_id)
            if is_ai_review(review):
                return review
        return None

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


def review_scorer_enabled(config: object) -> bool:
    settings = effective_generation_settings(config)
    review = settings.get("review") if isinstance(settings.get("review"), dict) else {}
    return bool(review.get("scorer_enabled"))


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


def ai_review_system_prompt(config: object) -> str:
    settings = effective_generation_settings(config)
    review = settings.get("review") if isinstance(settings.get("review"), dict) else {}
    value = str(review.get("system_prompt") or "").strip()
    return value or DEFAULT_REVIEW_SYSTEM_PROMPT


def ai_review_task_prompt_template(config: object) -> str:
    settings = effective_generation_settings(config)
    review = settings.get("review") if isinstance(settings.get("review"), dict) else {}
    value = str(review.get("task_prompt") or "").strip()
    return value or DEFAULT_REVIEW_TASK_PROMPT


def ai_review_task_prompt(
    *,
    chapter_id: str,
    title: str = "",
    template: str = "",
    extra_instruction: str = "",
) -> str:
    heading = f"{chapter_id}"
    if title:
        heading = f"{heading}（{title}）"
    value = str(template or DEFAULT_REVIEW_TASK_PROMPT)
    rendered = (
        value.replace("{chapter_heading}", heading)
        .replace("{chapter_id}", chapter_id)
        .replace("{title}", title)
        .strip()
    )
    extra = str(extra_instruction or "").strip()
    if extra:
        rendered = f"{rendered}\n\n【本次审稿特殊要求】\n{extra}"
    return rendered


def render_ai_review_prompt(
    render: dict[str, Any],
    draft: dict[str, Any],
    draft_text: str,
    *,
    review_prompt: str = "",
) -> str:
    context_text = render_review_context_materials(render)
    chapter_id = str(draft.get("chapter_id") or "")
    title = str(draft.get("title") or "")
    version_label = str(draft.get("version_label") or "")
    task_text = str(review_prompt or "").strip() or ai_review_task_prompt(chapter_id=chapter_id, title=title)
    lines = [
        "【审稿任务】",
        task_text,
        "",
        "【目标章节】",
        f"章节 ID：{chapter_id}",
        f"标题：{title or chapter_id}",
        f"草稿版本：{version_label or '-'}",
        "",
        "【上下文与资料】",
        context_text or "无额外上下文。",
        "",
        "【待审草稿正文】",
        draft_text or "（空草稿）",
    ]
    return "\n".join(lines).strip()


def render_review_context_materials(render: dict[str, Any]) -> str:
    package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
    sections = package.get("sections") if isinstance(package.get("sections"), list) else []
    lines: list[str] = []
    for group in grouped_context_sections(sections):
        lines.append(f"【{group['label']}】")
        for item in group["items"]:
            title = str(item.get("title") or item.get("source_id") or "").strip()
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            if title:
                lines.append(f"{title}:")
            lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def render_context_stats(render: dict[str, Any]) -> dict[str, int]:
    package = render.get("context_package") if isinstance(render.get("context_package"), dict) else {}
    sections = package.get("sections") if isinstance(package.get("sections"), list) else []
    skipped = package.get("skipped") if isinstance(package.get("skipped"), list) else []
    context_chars = sum(len(str(item.get("text") or "")) for item in sections if isinstance(item, dict))
    return {
        "context_section_count": len(sections),
        "skipped_context_count": len(skipped),
        "context_chars": context_chars,
    }


def is_ai_review(review: dict[str, Any]) -> bool:
    return str(review.get("review_type") or "") == AI_REVIEW_TYPE


def contains_reasoning_leak(content: str) -> bool:
    value = str(content or "").lower()
    return "<think" in value or "</think>" in value


def manual_rewrite_review_gate(store: ProjectStore, draft: dict[str, Any]) -> dict[str, Any]:
    draft_id = str(draft.get("draft_id") or "")
    manual_rewrite = draft.get("manual_rewrite") if isinstance(draft.get("manual_rewrite"), dict) else {}
    if str(manual_rewrite.get("mode") or "") != "manual_rewrite_draft_candidate":
        return {
            "required": False,
            "allowed": True,
            "matched_gate": "",
            "comparison_id": "",
            "handoff_id": "",
        }
    comparison_id = selected_manual_rewrite_comparison_id(store, draft_id)
    if comparison_id:
        return {
            "required": True,
            "allowed": True,
            "matched_gate": "selected_for_review_comparison",
            "comparison_id": comparison_id,
            "handoff_id": "",
        }
    handoff_id = pending_review_handoff_id(store, draft_id)
    if handoff_id:
        return {
            "required": True,
            "allowed": True,
            "matched_gate": "pending_review_handoff",
            "comparison_id": "",
            "handoff_id": handoff_id,
        }
    return {
        "required": True,
        "allowed": False,
        "matched_gate": "",
        "comparison_id": "",
        "handoff_id": "",
    }


def selected_manual_rewrite_comparison_id(store: ProjectStore, draft_id: str) -> str:
    for entry in ManualRewriteComparisonService(store).list_comparisons():
        if str(entry.get("submitted_draft_id") or "") != draft_id:
            continue
        comparison_id = str(entry.get("comparison_id") or "")
        if not comparison_id:
            continue
        try:
            artifact = ManualRewriteComparisonService(store).read_comparison(comparison_id)
        except Exception:
            continue
        decision = artifact.get("decision") if isinstance(artifact.get("decision"), dict) else {}
        if str(artifact.get("status") or "") == "selected_for_review" and str(decision.get("status") or "") == "selected_for_review":
            return comparison_id
    return ""


def pending_review_handoff_id(store: ProjectStore, draft_id: str) -> str:
    index = store.read_json(store.data_dir / "review_handoffs_index.json", default={"review_handoffs": []})
    items = index.get("review_handoffs") if isinstance(index, dict) and isinstance(index.get("review_handoffs"), list) else []
    for entry in items:
        if not isinstance(entry, dict) or str(entry.get("selected_draft_id") or "") != draft_id:
            continue
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        artifact = store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("selected_draft_id") or "") == draft_id and str(artifact.get("status") or "") == "pending_review":
            return str(artifact.get("handoff_id") or entry.get("handoff_id") or "")
    return ""
