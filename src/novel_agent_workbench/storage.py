from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


TRASH_SUFFIX = ".trash"


class StorageError(RuntimeError):
    """Base storage error for the workbench."""


class InvalidProjectIdError(ValueError):
    """Raised when a project id is unsafe for local path construction."""


class ProjectLockError(StorageError):
    """Raised when a project is already locked."""


@dataclass(frozen=True, slots=True)
class ProjectStore:
    """Safe local file store for one novel project."""

    projects_root: Path
    project_id: str

    @classmethod
    def open(cls, projects_root: str | Path, project_id: str) -> "ProjectStore":
        validate_project_id(project_id)
        root = Path(projects_root).resolve()
        store = cls(projects_root=root, project_id=project_id)
        store._assert_project_root_safe()
        return store

    @property
    def root(self) -> Path:
        return self.projects_root / self.project_id

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def locks_dir(self) -> Path:
        return self.root / "locks"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def secrets_path(self) -> Path:
        return self.data_dir / "secrets.local.json"

    @property
    def project_meta_path(self) -> Path:
        return self.root / "project.json"

    def initialize(self) -> None:
        self._assert_project_root_safe()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        if not self.project_meta_path.exists():
            self.write_project_meta({"project_id": self.project_id, "schema_version": 1})
        if not self.config_path.exists():
            self.write_config({})
        if not self.secrets_path.exists():
            self.write_secrets({})

    def read_project_meta(self) -> dict[str, Any]:
        return self.read_json(self.project_meta_path, default={})

    def write_project_meta(self, data: dict[str, Any]) -> None:
        self.write_json(self.project_meta_path, data)

    def read_config(self) -> dict[str, Any]:
        return self.read_json(self.config_path, default={})

    def write_config(self, data: dict[str, Any]) -> None:
        self.write_json(self.config_path, data)

    def read_secrets(self) -> dict[str, Any]:
        return self.read_json(self.secrets_path, default={})

    def write_secrets(self, data: dict[str, Any]) -> None:
        self.write_json(self.secrets_path, data)

    def read_json(self, path: str | Path, *, default: Any = None) -> Any:
        target = self._resolve_owned_path(path)
        if not target.exists():
            return default
        text = target.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)

    def write_json(self, path: str | Path, data: Any) -> None:
        target = self._resolve_owned_path(path)
        self._atomic_write_json(target, data)

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.initialize()
        lock_path = self.locks_dir / "project.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ProjectLockError(f"Project is already locked: {self.project_id}") from exc
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
                file.write(json.dumps({"project_id": self.project_id, "locked_at": utc_stamp()}, ensure_ascii=False))
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            yield
        finally:
            if lock_path.exists():
                retire_path(lock_path)

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup_path = self._backup_path_for(path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)

        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
                json.dump(data, file, ensure_ascii=False, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                retire_path(temp_path)
            raise

    def _backup_path_for(self, path: Path) -> Path:
        relative = path.relative_to(self.root)
        safe_name = "__".join(relative.parts)
        return self.backups_dir / f"{safe_name}.{utc_stamp()}.bak"

    def _resolve_owned_path(self, path: str | Path) -> Path:
        raw = Path(path)
        target = raw if raw.is_absolute() else self.root / raw
        target = target.resolve()
        self._assert_path_inside_root(target)
        return target

    def _assert_project_root_safe(self) -> None:
        self._assert_path_inside_root(self.root.resolve())

    def _assert_path_inside_root(self, path: Path) -> None:
        root = self.projects_root.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise StorageError(f"Path escapes projects root: {path}") from exc


def validate_project_id(project_id: str) -> None:
    if not project_id or project_id in {".", ".."}:
        raise InvalidProjectIdError("Project id cannot be empty, '.' or '..'.")
    if any(separator in project_id for separator in ("/", "\\")) or ":" in project_id:
        raise InvalidProjectIdError(f"Unsafe project id: {project_id!r}")
    if not all(character.isalnum() or character in {"_", "-"} for character in project_id):
        raise InvalidProjectIdError(f"Unsafe project id: {project_id!r}")


def retire_path(path: str | Path) -> Path:
    source = Path(path)
    target = trash_path_for(source)
    source.rename(target)
    return target


def trash_path_for(path: str | Path) -> Path:
    source = Path(path)
    stamp = utc_stamp()
    return source.with_name(f"{source.name}.{stamp}{TRASH_SUFFIX}")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
