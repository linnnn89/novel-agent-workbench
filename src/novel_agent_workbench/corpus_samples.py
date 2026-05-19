from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .corpus_boundaries import CorpusBoundaryService
from .corpus_profiler import CorpusProfilerError, decode_text
from .storage import ProjectStore, safe_filename, utc_stamp


CORPUS_SAMPLES_DIRNAME = "corpus_samples"
CORPUS_SAMPLES_INDEX_FILENAME = "corpus_samples_index.json"
MAX_SAMPLE_CHARS = 2000


class CorpusSampleError(RuntimeError):
    """Raised when a temporary corpus sample cannot be created or read safely."""


@dataclass(frozen=True, slots=True)
class CorpusSampleResult:
    sample_id: str
    status: str
    path: str
    created_at: str
    boundary_id: str
    ordinal: int
    char_count: int
    publish_blocker: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CorpusSampleService:
    """Creates explicitly temporary corpus samples for local testing only."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def samples_dir(self) -> Path:
        return self.store.data_dir / CORPUS_SAMPLES_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / CORPUS_SAMPLES_INDEX_FILENAME

    def create_corpus_sample(
        self,
        boundary_id: str,
        source_path: str | Path,
        *,
        ordinal: int,
        max_chars: int = 800,
    ) -> CorpusSampleResult:
        self.store.initialize()
        if ordinal < 1:
            raise CorpusSampleError("ordinal must be >= 1")
        if max_chars < 1 or max_chars > MAX_SAMPLE_CHARS:
            raise CorpusSampleError(f"max_chars must be between 1 and {MAX_SAMPLE_CHARS}")
        with self.store.lock():
            boundary_artifact = CorpusBoundaryService(self.store).read_corpus_boundaries(boundary_id)
            boundary = find_boundary(boundary_artifact, ordinal)
            text, source_sha256 = read_source_text(source_path)
            expected_sha = str(boundary_artifact.get("source", {}).get("sha256") or "")
            if source_sha256 != expected_sha:
                raise CorpusSampleError("source file hash does not match boundary artifact")
            start = int(boundary.get("body_start_char") or 0)
            end = int(boundary.get("body_end_char") or start)
            sample_text = text[start : min(end, start + max_chars)]
            created_at = utc_stamp()
            sample_id = new_corpus_sample_id()
            artifact_path = self.samples_dir / f"{safe_filename(boundary_id)}__{sample_id}.json"
            artifact = {
                "schema_version": 1,
                "sample_id": sample_id,
                "status": "sample_ready",
                "created_at": created_at,
                "test_only": True,
                "publish_blocker": True,
                "boundary_id": boundary_id,
                "ordinal": ordinal,
                "source": {
                    "file_name": str(boundary_artifact.get("source", {}).get("file_name") or Path(source_path).name),
                    "sha256": source_sha256,
                    "source_path_stored": False,
                },
                "range": {
                    "body_start_char": start,
                    "sample_start_char": start,
                    "sample_end_char": start + len(sample_text),
                    "sample_char_count": len(sample_text),
                    "max_chars": max_chars,
                },
                "sample_text": sample_text,
                "safety": {
                    "source_text_copied": True,
                    "test_only": True,
                    "publish_blocker": True,
                    "provider_called": False,
                    "writes_project_files": True,
                    "memory_bank_updated": False,
                    "rag_updated": False,
                    "draft_created": False,
                    "confirmed_chapter_created": False,
                    "export_created": False,
                },
                "required_cleanup": "remove_runtime_project_or_retire_sample_artifact_before_github_publish",
            }
            self.store.write_json(artifact_path, artifact)
            entry = {
                "sample_id": sample_id,
                "status": "sample_ready",
                "created_at": created_at,
                "test_only": True,
                "publish_blocker": True,
                "boundary_id": boundary_id,
                "ordinal": ordinal,
                "source_sha256": source_sha256,
                "char_count": len(sample_text),
                "path": str(artifact_path.relative_to(self.store.root)),
            }
            self._append_index_entry(entry)
            return CorpusSampleResult(
                sample_id=sample_id,
                status="sample_ready",
                path=str(artifact_path),
                created_at=created_at,
                boundary_id=boundary_id,
                ordinal=ordinal,
                char_count=len(sample_text),
                publish_blocker=True,
            )

    def list_corpus_samples(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "samples": []})
        if not isinstance(index, dict):
            return []
        items = index.get("samples")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_corpus_sample(self, sample_id: str, *, include_text: bool = False) -> dict[str, Any]:
        for item in self.list_corpus_samples():
            if item.get("sample_id") != sample_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise CorpusSampleError(f"Corpus sample index entry has no path: {sample_id}")
            artifact = self.store.read_json(path, default=None)
            if not isinstance(artifact, dict):
                raise CorpusSampleError(f"Corpus sample artifact is missing or invalid: {sample_id}")
            if include_text:
                return artifact
            return {key: value for key, value in artifact.items() if key != "sample_text"}
        raise CorpusSampleError(f"Corpus sample not found: {sample_id}")

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "samples": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "samples": []}
        items = index.get("samples") if isinstance(index.get("samples"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "samples": items})


def find_boundary(boundary_artifact: dict[str, Any], ordinal: int) -> dict[str, Any]:
    entries = boundary_artifact.get("boundaries")
    if not isinstance(entries, list):
        raise CorpusSampleError("Boundary artifact has no boundaries list")
    for item in entries:
        if isinstance(item, dict) and int(item.get("ordinal") or 0) == ordinal:
            return item
    raise CorpusSampleError(f"Boundary ordinal not found: {ordinal}")


def read_source_text(path: str | Path) -> tuple[str, str]:
    source_path = Path(path)
    if not source_path.exists() or not source_path.is_file():
        raise CorpusProfilerError(f"Corpus file not found: {source_path}")
    data = source_path.read_bytes()
    decoded = decode_text(data)
    return str(decoded["text"]), hashlib.sha256(data).hexdigest().upper()


def new_corpus_sample_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"
