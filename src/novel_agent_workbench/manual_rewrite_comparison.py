from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .drafts import DraftGenerationService, validate_chapter_id
from .manual_rewrite import ManualRewriteTaskService, validate_manual_rewrite_reason_code
from .storage import ProjectStore, safe_filename, utc_stamp


MANUAL_REWRITE_COMPARISONS_DIRNAME = "manual_rewrite_comparisons"
MANUAL_REWRITE_COMPARISONS_INDEX_FILENAME = "manual_rewrite_comparisons_index.json"
MANUAL_REWRITE_COMPARISON_DECISIONS = {"selected_for_review", "rejected", "needs_more_manual_work"}


class ManualRewriteComparisonError(RuntimeError):
    """Raised when a manual rewrite candidate comparison cannot be created or decided safely."""


@dataclass(frozen=True, slots=True)
class ManualRewriteComparisonResult:
    comparison_id: str
    task_id: str
    suggestion_id: str
    check_id: str
    chapter_id: str
    source_draft_id: str
    submitted_draft_id: str
    char_count_delta: int
    paragraph_count_delta: int
    path: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ManualRewriteComparisonDecisionResult:
    comparison_id: str
    task_id: str
    decision: str
    reason_code: str
    decided_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ManualRewriteComparisonService:
    """Metadata-only comparison gate for manual rewrite draft candidates."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self.tasks = ManualRewriteTaskService(store)
        self.drafts = DraftGenerationService(store)

    @property
    def comparisons_dir(self) -> Path:
        return self.store.data_dir / MANUAL_REWRITE_COMPARISONS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / MANUAL_REWRITE_COMPARISONS_INDEX_FILENAME

    def create_comparison(self, task_id: str) -> ManualRewriteComparisonResult:
        self.store.initialize()
        with self.store.lock():
            if self._find_by_task_id(task_id) is not None:
                raise ManualRewriteComparisonError(f"Manual rewrite task already has a comparison: {task_id}")
            task = self.tasks.read_task(task_id)
            submitted_draft_id = str(task.get("submitted_draft_id") or "")
            if not submitted_draft_id:
                raise ManualRewriteComparisonError(f"Manual rewrite task has no submitted draft: {task_id}")
            source_draft_id = str(task.get("draft_id") or "")
            if not source_draft_id:
                raise ManualRewriteComparisonError(f"Manual rewrite task has no source draft: {task_id}")
            chapter_id = str(task.get("chapter_id") or "")
            validate_chapter_id(chapter_id)
            source = self.drafts.read_draft(source_draft_id)
            submitted = self.drafts.read_draft(submitted_draft_id)
            manual_meta = submitted.get("manual_rewrite") if isinstance(submitted.get("manual_rewrite"), dict) else {}
            link_check = {
                "task_id": str(manual_meta.get("manual_rewrite_task_id") or "") == task_id,
                "source_draft_id": str(manual_meta.get("source_draft_id") or "") == source_draft_id,
                "suggestion_id": str(manual_meta.get("source_suggestion_id") or "") == str(task.get("suggestion_id") or ""),
                "check_id": str(manual_meta.get("source_check_id") or "") == str(task.get("check_id") or ""),
                "chapter_id": str(submitted.get("chapter_id") or "") == chapter_id,
            }
            if not all(link_check.values()):
                raise ManualRewriteComparisonError(
                    f"Submitted draft is not linked to manual rewrite task: {submitted_draft_id}"
                )
            source_metrics = structural_metrics(str(source.get("content") or ""))
            submitted_metrics = structural_metrics(str(submitted.get("content") or ""))
            delta = {
                key: int(submitted_metrics[key]) - int(source_metrics[key])
                for key in sorted(source_metrics)
                if isinstance(source_metrics.get(key), int) and isinstance(submitted_metrics.get(key), int)
            }
            created_at = utc_stamp()
            comparison_id = f"{created_at}_{uuid4().hex[:12]}"
            path = self.comparisons_dir / f"{safe_filename(chapter_id)}__{safe_filename(comparison_id)}.json"
            artifact = {
                "schema_version": 1,
                "comparison_id": comparison_id,
                "task_id": task_id,
                "suggestion_id": str(task.get("suggestion_id") or ""),
                "check_id": str(task.get("check_id") or ""),
                "chapter_id": chapter_id,
                "title": str(task.get("title") or ""),
                "source_draft_id": source_draft_id,
                "submitted_draft_id": submitted_draft_id,
                "status": "comparison_ready",
                "created_at": created_at,
                "updated_at": created_at,
                "char_count_delta": delta["char_count"],
                "paragraph_count_delta": delta["paragraph_count"],
                "structure_metrics": {
                    "source_draft": source_metrics,
                    "submitted_draft": submitted_metrics,
                    "delta": delta,
                },
                "link_check": link_check,
                "decision": {"status": "pending", "reason_code": "", "decided_at": ""},
                "safety": manual_rewrite_comparison_safety(),
            }
            self.store.write_json(path, artifact)
            entry = {
                "comparison_id": comparison_id,
                "task_id": task_id,
                "suggestion_id": artifact["suggestion_id"],
                "check_id": artifact["check_id"],
                "chapter_id": chapter_id,
                "title": artifact["title"],
                "source_draft_id": source_draft_id,
                "submitted_draft_id": submitted_draft_id,
                "status": "comparison_ready",
                "char_count_delta": delta["char_count"],
                "paragraph_count_delta": delta["paragraph_count"],
                "decision": artifact["decision"],
                "created_at": created_at,
                "updated_at": created_at,
                "path": str(path.relative_to(self.store.root)),
                "safety": artifact["safety"],
            }
            self._append_index_entry(entry)
            return ManualRewriteComparisonResult(
                comparison_id=comparison_id,
                task_id=task_id,
                suggestion_id=artifact["suggestion_id"],
                check_id=artifact["check_id"],
                chapter_id=chapter_id,
                source_draft_id=source_draft_id,
                submitted_draft_id=submitted_draft_id,
                char_count_delta=delta["char_count"],
                paragraph_count_delta=delta["paragraph_count"],
                path=str(path),
                created_at=created_at,
            )

    def list_comparisons(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "manual_rewrite_comparisons": []})
        if not isinstance(index, dict):
            return []
        items = index.get("manual_rewrite_comparisons")
        if not isinstance(items, list):
            return []
        comparisons = [item for item in items if isinstance(item, dict)]
        if status:
            comparisons = [item for item in comparisons if item.get("status") == status]
        return comparisons

    def read_comparison(self, comparison_id: str) -> dict[str, Any]:
        entry = self._comparison_index_entry(comparison_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise ManualRewriteComparisonError(f"Manual rewrite comparison index entry has no path: {comparison_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise ManualRewriteComparisonError(
                f"Manual rewrite comparison artifact is missing or invalid: {comparison_id}"
            )
        return artifact

    def decide_comparison(
        self,
        comparison_id: str,
        *,
        decision: str,
        reason_code: str = "",
    ) -> ManualRewriteComparisonDecisionResult:
        self.store.initialize()
        with self.store.lock():
            decision = validate_manual_rewrite_comparison_decision(decision)
            reason_code = validate_manual_rewrite_reason_code(reason_code)
            entry = self._comparison_index_entry(comparison_id)
            artifact = self.read_comparison(comparison_id)
            current = artifact.get("decision") if isinstance(artifact.get("decision"), dict) else {}
            if str(current.get("status") or "pending") != "pending":
                raise ManualRewriteComparisonError(f"Manual rewrite comparison already has a decision: {comparison_id}")
            decided_at = utc_stamp()
            decision_payload = {
                "status": decision,
                "reason_code": reason_code,
                "decided_at": decided_at,
            }
            artifact["decision"] = decision_payload
            artifact["status"] = decision
            artifact["updated_at"] = decided_at
            self.store.write_json(str(entry["path"]), artifact)
            self._update_index_entry(
                comparison_id,
                {
                    "status": decision,
                    "decision": decision_payload,
                    "updated_at": decided_at,
                },
            )
            return ManualRewriteComparisonDecisionResult(
                comparison_id=comparison_id,
                task_id=str(artifact.get("task_id") or entry.get("task_id") or ""),
                decision=decision,
                reason_code=reason_code,
                decided_at=decided_at,
            )

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_comparisons()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "manual_rewrite_comparisons": items})

    def _comparison_index_entry(self, comparison_id: str) -> dict[str, Any]:
        for item in self.list_comparisons():
            if item.get("comparison_id") == comparison_id:
                return item
        raise ManualRewriteComparisonError(f"Manual rewrite comparison not found: {comparison_id}")

    def _find_by_task_id(self, task_id: str) -> dict[str, Any] | None:
        for item in self.list_comparisons():
            if item.get("task_id") == task_id:
                return item
        return None

    def _update_index_entry(self, comparison_id: str, updates: dict[str, Any]) -> None:
        updated: list[dict[str, Any]] = []
        for item in self.list_comparisons():
            if item.get("comparison_id") == comparison_id:
                item = {**item, **updates}
            updated.append(item)
        self.store.write_json(self.index_path, {"schema_version": 1, "manual_rewrite_comparisons": updated})


def structural_metrics(value: str) -> dict[str, int]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n|\n", value) if item.strip()]
    lines = value.splitlines() if value else []
    return {
        "char_count": len(value),
        "nonspace_char_count": sum(1 for character in value if not character.isspace()),
        "paragraph_count": len(paragraphs),
        "line_count": len(lines),
        "sentence_marker_count": sum(value.count(marker) for marker in ("。", "！", "？", ".", "!", "?")),
        "ascii_word_count": len(re.findall(r"[A-Za-z0-9_]+", value)),
    }


def validate_manual_rewrite_comparison_decision(decision: str) -> str:
    value = str(decision or "").strip()
    if value not in MANUAL_REWRITE_COMPARISON_DECISIONS:
        raise ManualRewriteComparisonError(f"Invalid manual rewrite comparison decision: {decision!r}")
    return value


def manual_rewrite_comparison_safety() -> dict[str, bool]:
    return {
        "local_only": True,
        "provider_called": False,
        "external_corpus_used": False,
        "source_text_stored": False,
        "submitted_text_stored": False,
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
