from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .corpus_profiler import STRICT_CHAPTER_HEADING_RE, CorpusProfilerError, decode_text
from .storage import ProjectStore, safe_filename, utc_stamp


CORPUS_BOUNDARIES_DIRNAME = "corpus_boundaries"
CORPUS_BOUNDARIES_INDEX_FILENAME = "corpus_boundaries_index.json"


class CorpusBoundaryError(RuntimeError):
    """Raised when corpus chapter boundaries cannot be created or read safely."""


@dataclass(frozen=True, slots=True)
class CorpusBoundaryResult:
    boundary_id: str
    status: str
    path: str
    created_at: str
    file_name: str
    source_sha256: str
    chapter_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CorpusBoundaryService:
    """Stores no-text chapter boundary indexes for external corpus files."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def boundaries_dir(self) -> Path:
        return self.store.data_dir / CORPUS_BOUNDARIES_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / CORPUS_BOUNDARIES_INDEX_FILENAME

    def save_corpus_boundaries(self, path: str | Path) -> CorpusBoundaryResult:
        self.store.initialize()
        with self.store.lock():
            source_path = Path(path)
            artifact = build_boundary_artifact(source_path)
            boundary_id = new_corpus_boundary_id()
            created_at = utc_stamp()
            artifact.update({"boundary_id": boundary_id, "created_at": created_at})
            file_name = artifact["source"]["file_name"]
            artifact_path = self.boundaries_dir / f"{safe_filename(file_name)}__{boundary_id}.json"
            self.store.write_json(artifact_path, artifact)
            entry = {
                "boundary_id": boundary_id,
                "status": artifact["status"],
                "created_at": created_at,
                "file_name": file_name,
                "source_sha256": artifact["source"]["sha256"],
                "encoding": artifact["encoding"],
                "chapter_count": artifact["chapter_count"],
                "path": str(artifact_path.relative_to(self.store.root)),
                "safety": artifact["safety"],
            }
            self._append_index_entry(entry)
            return CorpusBoundaryResult(
                boundary_id=boundary_id,
                status=artifact["status"],
                path=str(artifact_path),
                created_at=created_at,
                file_name=file_name,
                source_sha256=artifact["source"]["sha256"],
                chapter_count=int(artifact["chapter_count"]),
            )

    def list_corpus_boundaries(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "boundaries": []})
        if not isinstance(index, dict):
            return []
        items = index.get("boundaries")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_corpus_boundaries(self, boundary_id: str) -> dict[str, Any]:
        for item in self.list_corpus_boundaries():
            if item.get("boundary_id") != boundary_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise CorpusBoundaryError(f"Corpus boundary index entry has no path: {boundary_id}")
            value = self.store.read_json(path, default=None)
            if not isinstance(value, dict):
                raise CorpusBoundaryError(f"Corpus boundary artifact is missing or invalid: {boundary_id}")
            return value
        raise CorpusBoundaryError(f"Corpus boundary not found: {boundary_id}")

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "boundaries": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "boundaries": []}
        items = index.get("boundaries") if isinstance(index.get("boundaries"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "boundaries": items})


def build_boundary_artifact(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        raise CorpusProfilerError(f"Corpus file not found: {path}")
    data = path.read_bytes()
    decoded = decode_text(data)
    lines = text_lines_with_offsets(decoded["text"])
    heading_indexes = [
        index for index, item in enumerate(lines) if STRICT_CHAPTER_HEADING_RE.match(str(item["text"]))
    ]
    entries = boundary_entries(lines, heading_indexes, text_length=len(decoded["text"]))
    return {
        "schema_version": 1,
        "boundary_id": "",
        "status": "boundaries_ready",
        "created_at": "",
        "source": {
            "file_name": path.name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest().upper(),
            "original_path_stored": False,
        },
        "encoding": {
            "detected": decoded["encoding"],
            "utf8_strict_ok": decoded["utf8_strict_ok"],
        },
        "chapter_count": len(entries),
        "boundaries": entries,
        "safety": {
            "source_text_copied": False,
            "chapter_heading_text_included": False,
            "source_path_stored": False,
            "provider_called": False,
            "writes_project_files": True,
        },
        "recommendation": "manual_review_required_before_import",
    }


def text_lines_with_offsets(text: str) -> list[dict[str, Any]]:
    raw_lines = text.splitlines(keepends=True)
    if not raw_lines and text:
        raw_lines = [text]
    offset = 0
    items: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw_lines, start=1):
        stripped = raw_line.rstrip("\r\n")
        items.append(
            {
                "line_number": line_number,
                "start_char": offset,
                "end_char": offset + len(raw_line),
                "text": stripped,
            }
        )
        offset += len(raw_line)
    return items


def boundary_entries(lines: list[dict[str, Any]], heading_indexes: list[int], *, text_length: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for ordinal, heading_index in enumerate(heading_indexes, start=1):
        next_heading_index = heading_indexes[ordinal] if ordinal < len(heading_indexes) else None
        heading_line = lines[heading_index]
        start_line = int(heading_line["line_number"]) + 1
        end_line = int(lines[next_heading_index]["line_number"]) - 1 if next_heading_index is not None else len(lines)
        start_char = int(lines[heading_index + 1]["start_char"]) if heading_index + 1 < len(lines) else text_length
        end_char = int(lines[next_heading_index]["start_char"]) if next_heading_index is not None else text_length
        entries.append(
            {
                "ordinal": ordinal,
                "heading_line_number": int(heading_line["line_number"]),
                "body_start_line": start_line,
                "body_end_line": max(start_line - 1, end_line),
                "body_start_char": start_char,
                "body_end_char": max(start_char, end_char),
                "body_char_count": max(0, end_char - start_char),
            }
        )
    return entries


def new_corpus_boundary_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"
