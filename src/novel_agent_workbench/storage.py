from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator

from .config import DATA_FILE_DEFAULTS, CURRENT_CONFIG_SCHEMA_VERSION, default_data_file, default_project_config, merge_project_config


TRASH_SUFFIX = ".trash"
REGISTRY_FILENAME = "registry.json"
DEFAULT_PROJECTS_DIRNAME = "workspace_projects"


class StorageError(RuntimeError):
    """Base storage error for the workbench."""


class InvalidProjectIdError(ValueError):
    """Raised when a project id is unsafe for local path construction."""


class ProjectLockError(StorageError):
    """Raised when a project is already locked."""


@dataclass(frozen=True, slots=True)
class ProjectRegistry:
    """Backend-only entrypoint for multiple local projects."""

    projects_root: Path

    @classmethod
    def default(cls) -> "ProjectRegistry":
        package_root = Path(__file__).resolve().parents[2]
        return cls.open(package_root / DEFAULT_PROJECTS_DIRNAME)

    @classmethod
    def open(cls, projects_root: str | Path) -> "ProjectRegistry":
        return cls(projects_root=Path(projects_root).resolve())

    @property
    def registry_path(self) -> Path:
        return self.projects_root / REGISTRY_FILENAME

    def initialize(self) -> None:
        self.projects_root.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._atomic_write_registry([])

    def create_project(self, project_id: str, *, title: str = "") -> ProjectStore:
        validate_project_id(project_id)
        self.initialize()
        store = ProjectStore.open(self.projects_root, project_id)
        store.initialize()
        meta = store.read_project_meta()
        meta.update(
            {
                "project_id": project_id,
                "title": title.strip() or project_id,
                "created_at": meta.get("created_at") or utc_stamp(),
                "updated_at": utc_stamp(),
                "schema_version": int(meta.get("schema_version") or 1),
            }
        )
        store.write_project_meta(meta)
        store.migrate_config()
        self._upsert_entry(
            {
                "project_id": project_id,
                "title": meta["title"],
                "path": str(store.root),
                "created_at": meta["created_at"],
                "updated_at": meta["updated_at"],
            }
        )
        return store

    def open_project(self, project_id: str) -> ProjectStore:
        validate_project_id(project_id)
        store = ProjectStore.open(self.projects_root, project_id)
        if not store.project_meta_path.exists():
            raise StorageError(f"Project does not exist: {project_id}")
        return store

    def list_projects(self) -> list[dict[str, Any]]:
        self.initialize()
        entries = self._read_registry()
        repaired = self._discover_missing_entries(entries)
        if repaired != entries:
            self._atomic_write_registry(repaired)
        return sorted(
            repaired,
            key=lambda item: (str(item.get("updated_at") or ""), str(item.get("project_id") or "")),
            reverse=True,
        )

    def _upsert_entry(self, entry: dict[str, Any]) -> None:
        entries = [item for item in self._read_registry() if item.get("project_id") != entry["project_id"]]
        entries.append(entry)
        self._atomic_write_registry(entries)

    def _discover_missing_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        known = {str(item.get("project_id") or "") for item in entries}
        repaired = list(entries)
        for child in sorted(self.projects_root.iterdir() if self.projects_root.exists() else []):
            if not child.is_dir():
                continue
            project_id = child.name
            if project_id in known:
                continue
            try:
                validate_project_id(project_id)
                store = ProjectStore.open(self.projects_root, project_id)
                meta = store.read_project_meta()
            except (InvalidProjectIdError, StorageError, json.JSONDecodeError):
                continue
            if meta.get("project_id") != project_id:
                continue
            repaired.append(
                {
                    "project_id": project_id,
                    "title": str(meta.get("title") or project_id),
                    "path": str(store.root),
                    "created_at": str(meta.get("created_at") or ""),
                    "updated_at": str(meta.get("updated_at") or meta.get("created_at") or ""),
                }
            )
        return repaired

    def _read_registry(self) -> list[dict[str, Any]]:
        self.initialize()
        text = self.registry_path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        value = json.loads(text)
        if not isinstance(value, list):
            raise StorageError("registry.json must contain a list.")
        return [item for item in value if isinstance(item, dict)]

    def _atomic_write_registry(self, entries: list[dict[str, Any]]) -> None:
        self.projects_root.mkdir(parents=True, exist_ok=True)
        atomic_write_json_file(self.registry_path, entries)


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

    def data_file_path(self, name: str) -> Path:
        if name not in DATA_FILE_DEFAULTS:
            raise StorageError(f"Unknown managed data file: {name}")
        return self.data_dir / name

    def initialize(self) -> None:
        self._assert_project_root_safe()
        self._ensure_storage_dirs()
        if not self.project_meta_path.exists():
            self.write_project_meta({"project_id": self.project_id, "schema_version": 1})
        if not self.config_path.exists():
            self.write_config(default_project_config())
        if not self.secrets_path.exists():
            self.write_secrets({})
        self.ensure_default_data_files()

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
        target = self._resolve_owned_path(self.secrets_path)
        atomic_write_json_file(target, data)

    def update_secrets(self, updates: dict[str, Any]) -> dict[str, Any]:
        secrets = self.read_secrets()
        secrets.update(updates)
        self.write_secrets(secrets)
        return secrets

    def ensure_default_data_files(self) -> list[str]:
        created: list[str] = []
        for name in DATA_FILE_DEFAULTS:
            path = self.data_file_path(name)
            if not path.exists():
                self.write_json(path, default_data_file(name))
                created.append(name)
        return created

    def migrate_config(self) -> dict[str, Any]:
        self._assert_project_root_safe()
        self._ensure_storage_dirs()
        current = self.read_config()
        migrated, changed = merge_project_config(current)
        missing_files = [name for name in DATA_FILE_DEFAULTS if not self.data_file_path(name).exists()]
        missing_meta = not self.project_meta_path.exists()
        if changed or missing_files or missing_meta:
            checkpoint = self.create_checkpoint(label="pre_migration")
            if missing_meta:
                self.write_project_meta({"project_id": self.project_id, "schema_version": 1})
            self.write_config(migrated)
            created_files = self.ensure_default_data_files()
            return {
                "changed": True,
                "schema_version": CURRENT_CONFIG_SCHEMA_VERSION,
                "checkpoint": checkpoint,
                "created_files": created_files,
                "created_project_meta": missing_meta,
            }
        return {
            "changed": False,
            "schema_version": CURRENT_CONFIG_SCHEMA_VERSION,
            "checkpoint": None,
            "created_files": [],
            "created_project_meta": False,
        }

    def public_state(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_path": str(self.root),
            "config": self.read_config(),
            "secrets": public_secrets_state(self.read_secrets()),
        }

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

    def create_checkpoint(self, *, label: str = "", include_secrets: bool = False) -> dict[str, Any]:
        self._assert_project_root_safe()
        self._ensure_storage_dirs()
        checkpoint_id = utc_stamp()
        checkpoint_dir = self.backups_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        safe_label = safe_filename(label.strip()) if label.strip() else "checkpoint"
        checkpoint_path = checkpoint_dir / f"{checkpoint_id}_{safe_label}.zip"
        files = self._checkpoint_file_entries(include_secrets=include_secrets)
        manifest = {
            "checkpoint_id": checkpoint_id,
            "created_at": checkpoint_id,
            "project_id": self.project_id,
            "label": label,
            "include_secrets": bool(include_secrets),
            "format": "novel_agent_workbench.project_checkpoint.v1",
            "files": files,
        }
        with zipfile.ZipFile(checkpoint_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("checkpoint_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            for item in files:
                archive.write(self.root / item["path"], arcname=item["path"])
        return {**manifest, "path": str(checkpoint_path)}

    def restore_checkpoint(self, checkpoint_path: str | Path) -> dict[str, Any]:
        source = self._resolve_owned_path(checkpoint_path)
        with zipfile.ZipFile(source, "r") as archive:
            manifest = self._read_checkpoint_manifest(archive)
            if manifest.get("project_id") != self.project_id:
                raise StorageError(
                    f"Checkpoint project mismatch: {manifest.get('project_id')!r} != {self.project_id!r}"
                )
            files = manifest.get("files")
            if not isinstance(files, list):
                raise StorageError("Checkpoint manifest has no file list.")
            restored: list[str] = []
            for item in files:
                if not isinstance(item, dict):
                    raise StorageError("Checkpoint manifest contains an invalid file entry.")
                relative = self._safe_checkpoint_relative_path(str(item.get("path") or ""))
                data = archive.read(relative.as_posix())
                expected_sha = str(item.get("sha256") or "")
                if sha256(data).hexdigest() != expected_sha:
                    raise StorageError(f"Checkpoint file hash mismatch: {relative.as_posix()}")
                target = self._resolve_owned_path(relative)
                self._atomic_write_bytes(target, data, retire_existing=True)
                restored.append(relative.as_posix())
        return {"checkpoint_id": manifest.get("checkpoint_id"), "project_id": self.project_id, "restored_files": restored}

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
        if path.exists():
            backup_path = self._backup_path_for(path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path)
        atomic_write_json_file(path, data)

    def _atomic_write_bytes(self, path: Path, data: bytes, *, retire_existing: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            if path.exists() and retire_existing:
                retire_path(path)
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

    def _checkpoint_file_entries(self, *, include_secrets: bool) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.root)
            if self._should_exclude_from_checkpoint(relative, include_secrets=include_secrets):
                continue
            data = path.read_bytes()
            entries.append(
                {
                    "path": relative.as_posix(),
                    "size": len(data),
                    "sha256": sha256(data).hexdigest(),
                }
            )
        return entries

    def _should_exclude_from_checkpoint(self, relative: Path, *, include_secrets: bool) -> bool:
        parts = relative.parts
        if not parts:
            return True
        if parts[0] in {"backups", "locks"}:
            return True
        if relative.name.endswith(TRASH_SUFFIX):
            return True
        if not include_secrets and relative.as_posix() == "data/secrets.local.json":
            return True
        return False

    def _read_checkpoint_manifest(self, archive: zipfile.ZipFile) -> dict[str, Any]:
        names = set(archive.namelist())
        if "checkpoint_manifest.json" not in names:
            raise StorageError("Checkpoint has no checkpoint_manifest.json.")
        manifest = json.loads(archive.read("checkpoint_manifest.json").decode("utf-8"))
        if not isinstance(manifest, dict):
            raise StorageError("Checkpoint manifest is not an object.")
        for name in names:
            if name == "checkpoint_manifest.json":
                continue
            self._safe_checkpoint_relative_path(name)
        return manifest

    def _safe_checkpoint_relative_path(self, value: str) -> Path:
        if not value or value.startswith("/") or value.startswith("\\") or ":" in value:
            raise StorageError(f"Unsafe checkpoint path: {value!r}")
        relative = Path(value)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise StorageError(f"Unsafe checkpoint path: {value!r}")
        return relative

    def _assert_project_root_safe(self) -> None:
        self._assert_path_inside_root(self.root.resolve())

    def _assert_path_inside_root(self, path: Path) -> None:
        root = self.projects_root.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise StorageError(f"Path escapes projects root: {path}") from exc

    def _ensure_storage_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)


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


def safe_filename(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
    cleaned = cleaned.strip("._")
    return cleaned or "checkpoint"


def public_secrets_state(secrets: dict[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    for key, value in secrets.items():
        if isinstance(value, str):
            public[key] = {"has_value": bool(value), "masked": mask_secret(value)}
        elif isinstance(value, dict):
            public[key] = public_secrets_state(value)
        else:
            public[key] = {"has_value": value is not None, "masked": ""}
    return public


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}****{value[-4:]}"


def atomic_write_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
