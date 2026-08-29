"""Tk-free state transformations for the classic Memory Bank editor."""

from __future__ import annotations

from typing import Any, Collection, Iterable

from .memory_bank import normalize_memory_target_tokens
from .ui_presenters import readable_chapter_label


def memory_chapter_row_label(chapter: dict[str, Any], checked_chapter_ids: Collection[str]) -> str:
    """Format one chapter row without depending on a Tk variable or widget."""
    chapter_id = str(chapter.get("chapter_id") or "")
    title = str(chapter.get("title") or "").strip()
    committed_at = str(chapter.get("committed_at") or "").strip()
    prefix = "✓" if chapter_id in checked_chapter_ids else "□"
    parts = [prefix, readable_chapter_label(chapter_id)]
    if title:
        parts.append(title)
    if committed_at:
        parts.append(committed_at[:8])
    return "  ".join(parts)


def checked_memory_chapter_ids(
    confirmed_chapters: Iterable[dict[str, Any]],
    checked_chapter_ids: Collection[str],
) -> list[str]:
    """Return selected IDs in the durable confirmed-chapter order shown by the editor."""
    return [
        str(chapter.get("chapter_id") or "")
        for chapter in confirmed_chapters
        if str(chapter.get("chapter_id") or "") in checked_chapter_ids
    ]


def checked_memory_chapters_label(chapter_ids: Iterable[str]) -> str:
    """Summarize the current selection while keeping long labels bounded."""
    ids = [str(chapter_id or "").strip() for chapter_id in chapter_ids if str(chapter_id or "").strip()]
    if not ids:
        return "尚未勾选章节"
    labels = [readable_chapter_label(chapter_id) for chapter_id in ids]
    if len(labels) <= 5:
        return "、".join(labels)
    return "、".join(labels[:5]) + f" 等 {len(labels)} 章"


def memory_editor_snapshot(
    *,
    text: str,
    include_context: object,
    target_tokens: object,
    chapter_ids: Iterable[str],
) -> dict[str, Any]:
    """Build the canonical value snapshot used for dirty-state comparisons and saves."""
    return {
        "text": str(text or "").strip(),
        "include_context": bool(include_context),
        "target_tokens": normalize_memory_target_tokens(target_tokens),
        "checked_chapter_ids": [str(chapter_id or "") for chapter_id in chapter_ids],
    }
