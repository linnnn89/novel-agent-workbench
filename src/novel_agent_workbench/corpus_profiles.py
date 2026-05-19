from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .corpus_profiler import profile_corpus
from .storage import ProjectStore, safe_filename, utc_stamp


CORPUS_PROFILES_DIRNAME = "corpus_profiles"
CORPUS_PROFILES_INDEX_FILENAME = "corpus_profiles_index.json"


class CorpusProfileArtifactError(RuntimeError):
    """Raised when a corpus profile artifact cannot be created or read safely."""


@dataclass(frozen=True, slots=True)
class CorpusProfileArtifactResult:
    profile_id: str
    status: str
    path: str
    created_at: str
    file_name: str
    source_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CorpusProfileArtifactService:
    """Stores conservative metadata-only corpus profile artifacts inside one project."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def profiles_dir(self) -> Path:
        return self.store.data_dir / CORPUS_PROFILES_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / CORPUS_PROFILES_INDEX_FILENAME

    def save_corpus_profile(self, path: str | Path, *, max_name_candidates: int = 20) -> CorpusProfileArtifactResult:
        self.store.initialize()
        with self.store.lock():
            profile = profile_corpus(path, max_name_candidates=max_name_candidates).to_dict()
            created_at = utc_stamp()
            profile_id = new_corpus_profile_id()
            source = profile.get("source") if isinstance(profile.get("source"), dict) else {}
            file_name = str(source.get("file_name") or "corpus.txt")
            source_sha256 = str(source.get("sha256") or "")
            artifact_path = self.profiles_dir / f"{safe_filename(file_name)}__{profile_id}.json"
            artifact = sanitize_persistent_profile(profile, profile_id=profile_id, created_at=created_at)
            self.store.write_json(artifact_path, artifact)
            entry = {
                "profile_id": profile_id,
                "status": artifact["status"],
                "created_at": created_at,
                "file_name": file_name,
                "source_sha256": source_sha256,
                "encoding": artifact["encoding"],
                "strict_chapter_heading_count": artifact["structure"]["strict_chapter_heading_count"],
                "line_count": artifact["structure"]["line_count"],
                "path": str(artifact_path.relative_to(self.store.root)),
                "safety": artifact["safety"],
            }
            self._append_index_entry(entry)
            return CorpusProfileArtifactResult(
                profile_id=profile_id,
                status=artifact["status"],
                path=str(artifact_path),
                created_at=created_at,
                file_name=file_name,
                source_sha256=source_sha256,
            )

    def list_corpus_profiles(self) -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "profiles": []})
        if not isinstance(index, dict):
            return []
        items = index.get("profiles")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def read_corpus_profile(self, profile_id: str) -> dict[str, Any]:
        for item in self.list_corpus_profiles():
            if item.get("profile_id") != profile_id:
                continue
            path = item.get("path")
            if not isinstance(path, str):
                raise CorpusProfileArtifactError(f"Corpus profile index entry has no path: {profile_id}")
            value = self.store.read_json(path, default=None)
            if not isinstance(value, dict):
                raise CorpusProfileArtifactError(f"Corpus profile artifact is missing or invalid: {profile_id}")
            return value
        raise CorpusProfileArtifactError(f"Corpus profile not found: {profile_id}")

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "profiles": []})
        if not isinstance(index, dict):
            index = {"schema_version": 1, "profiles": []}
        items = index.get("profiles") if isinstance(index.get("profiles"), list) else []
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "profiles": items})


def sanitize_persistent_profile(profile: dict[str, Any], *, profile_id: str, created_at: str) -> dict[str, Any]:
    source = profile.get("source") if isinstance(profile.get("source"), dict) else {}
    name_candidates = profile.get("name_candidates") if isinstance(profile.get("name_candidates"), dict) else {}
    safety = profile.get("safety") if isinstance(profile.get("safety"), dict) else {}
    return {
        "schema_version": 1,
        "profile_id": profile_id,
        "status": "profile_ready",
        "created_at": created_at,
        "source": {
            "file_name": str(source.get("file_name") or ""),
            "size_bytes": int(source.get("size_bytes") or 0),
            "sha256": str(source.get("sha256") or ""),
            "original_path_stored": False,
        },
        "encoding": profile.get("encoding") if isinstance(profile.get("encoding"), dict) else {},
        "structure": profile.get("structure") if isinstance(profile.get("structure"), dict) else {},
        "chapter_stats": profile.get("chapter_stats") if isinstance(profile.get("chapter_stats"), dict) else {},
        "line_stats": profile.get("line_stats") if isinstance(profile.get("line_stats"), dict) else {},
        "dialogue_proxy": profile.get("dialogue_proxy") if isinstance(profile.get("dialogue_proxy"), dict) else {},
        "name_candidates": {
            "method": str(name_candidates.get("method") or ""),
            "candidate_count": int(name_candidates.get("candidate_count") or 0),
            "top_included": False,
        },
        "safety": {
            **safety,
            "source_text_copied": False,
            "chapter_heading_text_included": False,
            "source_path_stored": False,
            "name_candidate_text_stored": False,
            "provider_called": False,
            "writes_project_files": True,
        },
        "recommendation": "manual_review_required_before_import",
    }


def new_corpus_profile_id() -> str:
    return f"{utc_stamp()}_{uuid4().hex[:12]}"
