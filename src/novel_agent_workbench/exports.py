from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .drafts import DraftGenerationService
from .storage import ProjectStore


@dataclass(frozen=True)
class TxtExportResult:
    path: str
    chapter_count: int
    bytes_written: int
    encoding: str = "utf-8-sig"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "chapter_count": self.chapter_count,
            "bytes_written": self.bytes_written,
            "encoding": self.encoding,
        }


class TxtManuscriptExportService:
    """Exports confirmed chapters as a plain text manuscript."""

    def __init__(self, store: ProjectStore):
        self.store = store
        self.drafts = DraftGenerationService(store)

    def export_confirmed_chapters(self, output_path: str | Path) -> TxtExportResult:
        chapters = self._confirmed_chapters_in_story_order()
        if not chapters:
            raise ValueError("没有已确认章节可导出。")

        target = Path(output_path).expanduser().resolve()
        if target.suffix.lower() != ".txt":
            target = target.with_suffix(".txt")
        target.parent.mkdir(parents=True, exist_ok=True)

        text = self._render_txt(chapters)
        target.write_text(text, encoding="utf-8-sig", newline="\r\n")
        return TxtExportResult(
            path=str(target),
            chapter_count=len(chapters),
            bytes_written=target.stat().st_size,
        )

    def _confirmed_chapters_in_story_order(self) -> list[dict[str, Any]]:
        entries = sorted(
            self.drafts.list_confirmed_chapters(),
            key=lambda item: chapter_sort_key(str(item.get("chapter_id") or "")),
        )
        chapters: list[dict[str, Any]] = []
        for entry in entries:
            chapter_id = str(entry.get("chapter_id") or "")
            if not chapter_id:
                continue
            chapters.append(self.drafts.read_confirmed_chapter(chapter_id))
        return chapters

    def _render_txt(self, chapters: list[dict[str, Any]]) -> str:
        project_meta = self.store.read_project_meta()
        project_title = str(project_meta.get("title") or self.store.project_id).strip()
        parts = [project_title]
        for chapter in chapters:
            title = format_chapter_heading(
                str(chapter.get("chapter_id") or ""),
                str(chapter.get("title") or ""),
            )
            content = normalize_txt_content(str(chapter.get("content") or ""))
            parts.append(f"{title}\n\n{content}".rstrip())
        return "\n\n".join(part for part in parts if part.strip()).rstrip() + "\n"


def chapter_sort_key(chapter_id: str) -> tuple[str, int, str]:
    match = re.search(r"(\d+)$", chapter_id)
    if match:
        return (chapter_id[: match.start()], int(match.group(1)), chapter_id)
    return (chapter_id, 0, chapter_id)


def format_chapter_heading(chapter_id: str, title: str) -> str:
    clean_title = title.strip()
    match = re.search(r"(\d+)$", chapter_id)
    if match:
        number = int(match.group(1))
        prefix = f"第{number:03d}章"
        if clean_title and clean_title != chapter_id:
            return f"{prefix} {clean_title}"
        return prefix
    if clean_title and clean_title != chapter_id:
        return f"{chapter_id} {clean_title}".strip()
    return chapter_id or clean_title or "未命名章节"


def normalize_txt_content(content: str) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()
