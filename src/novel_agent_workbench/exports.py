from __future__ import annotations

import re
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .chapters import chapter_id_number, chapter_number_width, format_chapter_number
from .drafts import DraftGenerationService
from .storage import ProjectStore


@dataclass(frozen=True)
class TxtExportResult:
    path: str
    chapter_count: int
    bytes_written: int
    encoding: str = "utf-8-sig"
    draft_count: int = 0
    scope: str = "confirmed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "chapter_count": self.chapter_count,
            "bytes_written": self.bytes_written,
            "encoding": self.encoding,
            "draft_count": self.draft_count,
            "scope": self.scope,
        }


class TxtManuscriptExportService:
    """Exports a single readable manuscript, with an explicit chapter selection policy."""

    def __init__(self, store: ProjectStore):
        self.store = store
        self.drafts = DraftGenerationService(store)

    def export_confirmed_chapters(self, output_path: str | Path) -> TxtExportResult:
        return self.export_manuscript(output_path, scope="confirmed")

    def export_manuscript(self, output_path: str | Path, *, scope: str = "whole") -> TxtExportResult:
        if scope not in {"whole", "confirmed"}:
            raise ValueError("未知的 TXT 导出范围。")
        # Read a consistent snapshot before touching the destination.
        with self.store.lock():
            chapters = self._confirmed_chapters_in_story_order()
            confirmed_ids = {str(item["chapter_id"]) for item in chapters}
            draft_count = 0
            if scope == "whole":
                latest: dict[str, dict[str, Any]] = {}
                for entry in self.drafts.list_drafts():
                    chapter_id = str(entry.get("chapter_id") or "")
                    if not chapter_id or chapter_id in confirmed_ids:
                        continue
                    previous = latest.get(chapter_id)
                    if previous is None or draft_version_key(entry) >= draft_version_key(previous):
                        latest[chapter_id] = entry
                for entry in latest.values():
                    chapters.append(self.drafts.read_draft(str(entry["draft_id"])))
                    draft_count += 1
            if not chapters:
                raise ValueError("没有可导出的章节正文。" if scope == "whole" else "没有已确认章节可导出。")
            chapters.sort(key=lambda item: chapter_sort_key(str(item.get("chapter_id") or "")))
            text = self._render_txt(chapters)
        # Explicit bytes give identical BOM/CRLF output on Windows, macOS and Linux.
        data = text.replace("\n", "\r\n").encode("utf-8-sig")
        target = Path(output_path).expanduser()
        if target.suffix.lower() != ".txt":
            target = target.with_name(target.name + ".txt")
        target = target.absolute()
        if target.is_symlink():
            raise ValueError("请另选普通文件路径，不要覆盖符号链接。")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".naw-txt-", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return TxtExportResult(str(target), len(chapters), len(data), draft_count=draft_count, scope=scope)

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
        project_title = " ".join(str(project_meta.get("title") or self.store.project_id).split())
        parts = [project_title]
        numbers = [
            number
            for number in (chapter_id_number(str(chapter.get("chapter_id") or "")) for chapter in chapters)
            if number is not None
        ]
        heading_width = chapter_number_width(numbers)
        for chapter in chapters:
            title = format_chapter_heading(
                str(chapter.get("chapter_id") or ""),
                str(chapter.get("title") or ""),
                width=heading_width,
            )
            content = normalize_txt_content(str(chapter.get("content") or ""))
            parts.append(f"{title}\n\n{content}".rstrip())
        return "\n\n".join(part for part in parts if part.strip()).rstrip() + "\n"


def chapter_sort_key(chapter_id: str) -> tuple[str, int, str]:
    match = re.search(r"(\d+)$", chapter_id)
    if match:
        return (chapter_id[: match.start()], int(match.group(1)), chapter_id)
    return (chapter_id, 0, chapter_id)


def format_chapter_heading(chapter_id: str, title: str, *, width: int | None = None) -> str:
    clean_title = " ".join(title.split())
    number = chapter_id_number(chapter_id)
    if number is not None:
        prefix = f"第{format_chapter_number(number, width)}章"
        if clean_title and clean_title != chapter_id:
            return f"{prefix} {clean_title}"
        return prefix
    if clean_title and clean_title != chapter_id:
        return f"{chapter_id} {clean_title}".strip()
    return chapter_id or clean_title or "未命名章节"


def normalize_txt_content(content: str) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip("\n")


def draft_version_key(entry: dict[str, Any]) -> tuple[int, str, str]:
    try:
        version = int(entry.get("version") or 0)
    except (ValueError, TypeError):
        version = 0
    return version, str(entry.get("created_at") or ""), str(entry.get("draft_id") or "")


def safe_txt_filename(title: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip().rstrip(". ")
    name = name[:100].rstrip(". ") or "未命名作品"
    if re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])", name.split(".")[0]):
        name = "_" + name
    return name + ".txt"
