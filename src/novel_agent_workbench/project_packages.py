from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .config import CURRENT_CONFIG_SCHEMA_VERSION
from .storage import (
    InvalidProjectIdError,
    ProjectLockError,
    ProjectRegistry,
    ProjectStore,
    StorageError,
    atomic_write_bytes_file,
    is_excluded_from_checkpoint,
    retire_path,
    safe_archive_relative_path,
    utc_stamp,
    validate_project_id,
)


PACKAGE_FORMAT = "novel_agent_workbench.project_package.v1"
PACKAGE_MANIFEST_NAME = "package_manifest.json"
CHECKPOINT_MANIFEST_NAME = "checkpoint_manifest.json"
# namelist cap is MAX+1 because package_manifest.json is a ZIP member but not in files[].
MAX_PACKAGE_FILES = 20_000
MAX_PACKAGE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
OVERWRITE_CONFIRM_PHRASE = "确认覆盖"
IMPORT_MODES = {"keep_id", "new_id", "overwrite"}
PORTABLE_EXCLUSIONS = [
    "backups/",
    "locks/",
    "*.trash",
    "data/secrets.local.json",
    "*.nawpkg",
    "*.zip",
    "*.env",
]


@dataclass(frozen=True)
class ProjectPackageExportResult:
    path: str
    project_id: str
    title: str
    file_count: int
    bytes_written: int
    inventory: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "project_id": self.project_id,
            "title": self.title,
            "file_count": self.file_count,
            "bytes_written": self.bytes_written,
            "inventory": dict(self.inventory),
        }


@dataclass(frozen=True)
class ProjectPackageInspectResult:
    path: str
    format: str
    schema_version: int
    exported_at: str
    source_project_id: str
    title: str
    inventory: dict[str, Any]
    conflict: bool
    existing_title: str | None
    source_project_id_valid: bool
    suggested_new_project_id: str
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "format": self.format,
            "schema_version": self.schema_version,
            "exported_at": self.exported_at,
            "source_project_id": self.source_project_id,
            "title": self.title,
            "inventory": dict(self.inventory),
            "conflict": self.conflict,
            "existing_title": self.existing_title,
            "source_project_id_valid": self.source_project_id_valid,
            "suggested_new_project_id": self.suggested_new_project_id,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ProjectPackageImportResult:
    mode: str
    project_id: str
    title: str
    source_project_id: str
    checkpoint: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "project_id": self.project_id,
            "title": self.title,
            "source_project_id": self.source_project_id,
            "checkpoint": dict(self.checkpoint) if isinstance(self.checkpoint, dict) else None,
        }


@dataclass(frozen=True)
class _ValidatedPackage:
    path: Path
    manifest: dict[str, Any]
    files: dict[str, bytes]
    project_meta: dict[str, Any]
    warnings: list[str]


class ProjectPackageService:
    """Portable project snapshot (.nawpkg). Not a checkpoint, not TXT export."""

    def __init__(self, registry: ProjectRegistry) -> None:
        self.registry = registry

    def pack(self, project_id: str, output_path: str | Path) -> ProjectPackageExportResult:
        store = self.registry.open_project(project_id)
        target = _resolve_output_path(output_path)
        # Saving inside the project would nest the next export's previous package.
        _reject_output_inside_project(store, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with store.lock():
                entries, overrides = _collect_portable_files(store)
                meta = store.read_project_meta()
                title = str(meta.get("title") or store.project_id)
                inventory = _inventory_for(store, entries)
                exported_at = utc_stamp()
                manifest = {
                    "format": PACKAGE_FORMAT,
                    "schema_version": 1,
                    "package_id": exported_at,
                    "exported_at": exported_at,
                    "workbench_version": _workbench_version(),
                    "source": {
                        "project_id": store.project_id,
                        "title": title,
                        "project_schema_version": int(meta.get("schema_version") or 1),
                        "config_schema_version": _config_schema_version(overrides.get("data/config.json")),
                    },
                    "include_secrets": False,
                    "exclusions": list(PORTABLE_EXCLUSIONS),
                    "inventory": inventory,
                    "files": entries,
                }
                manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
                _write_package_zip(target, manifest_bytes, entries, store, overrides)
        except ProjectLockError as exc:
            raise StorageError("作品正在保存或生成，请稍后重试。") from exc
        except OSError as exc:
            raise _translate_os_error(exc) from exc
        return ProjectPackageExportResult(
            path=str(target),
            project_id=store.project_id,
            title=title,
            file_count=len(entries),
            bytes_written=target.stat().st_size,
            inventory=inventory,
        )

    def inspect(self, package_path: str | Path) -> ProjectPackageInspectResult:
        validated = _validate_package_file(package_path)
        source_id = str(validated.project_meta.get("project_id") or "")
        title = str(validated.project_meta.get("title") or source_id)
        source_valid = _project_id_is_valid(source_id)
        existing = self._existing_ids()
        conflict = source_valid and source_id in existing
        existing_title = self._title_for(source_id) if conflict else None
        base = source_id if source_valid else slug_or_novel(title)
        suggested = allocate_new_project_id(base, existing)
        inventory = validated.manifest.get("inventory") if isinstance(validated.manifest.get("inventory"), dict) else {}
        return ProjectPackageInspectResult(
            path=str(validated.path),
            format=str(validated.manifest.get("format") or ""),
            schema_version=int(validated.manifest.get("schema_version") or 1),
            exported_at=str(validated.manifest.get("exported_at") or ""),
            source_project_id=source_id,
            title=title,
            inventory=dict(inventory),
            conflict=conflict,
            existing_title=existing_title,
            source_project_id_valid=source_valid,
            suggested_new_project_id=suggested,
            warnings=list(validated.warnings),
        )

    def unpack(
        self,
        package_path: str | Path,
        *,
        mode: str,
        confirm_text: str = "",
        new_project_id: str = "",
    ) -> ProjectPackageImportResult:
        if mode not in IMPORT_MODES:
            raise StorageError("未知的导入方式。")
        # Re-run the same checks as inspect: the ZIP may have been swapped in between.
        validated = _validate_package_file(package_path)
        source_id = str(validated.project_meta.get("project_id") or "")
        title = str(validated.project_meta.get("title") or source_id)
        source_valid = _project_id_is_valid(source_id)
        existing = self._existing_ids()
        conflict = source_valid and source_id in existing
        if mode == "keep_id":
            if not source_valid:
                raise StorageError("项目编号不可用，请改为作为新作品导入。")
            if conflict:
                raise StorageError("项目库中已有相同编号，不能沿用原编号。")
            return self._unpack_new_directory(validated, target_id=source_id, mode=mode, title=title, source_id=source_id)
        if mode == "new_id":
            requested = str(new_project_id or "").strip()
            base = source_id if source_valid else slug_or_novel(title)
            if requested and requested not in existing and _project_id_is_valid(requested):
                target_id = requested
            else:
                # Someone may have created requested between inspect and unpack; skip to the next id.
                target_id = allocate_new_project_id(base, existing)
            return self._unpack_new_directory(validated, target_id=target_id, mode=mode, title=title, source_id=source_id)
        if str(confirm_text or "").strip() != OVERWRITE_CONFIRM_PHRASE:
            raise StorageError("未输入「确认覆盖」，已取消。")
        if not source_valid:
            raise StorageError("项目编号不可用，请改为作为新作品导入。")
        if not conflict:
            raise StorageError("项目库中没有可覆盖的同编号作品。")
        return self._unpack_overwrite(validated, project_id=source_id, title=title)

    def restore_pre_import_overwrite(self, project_id: str, checkpoint_path: str | Path) -> dict[str, Any]:
        """Roll back an overwrite: restore checkpoint files, then retire extras the checkpoint never had.

        `ProjectStore.restore_checkpoint` only writes listed files; leftover package-only
        data files would remain. This helper is package-specific and does not change
        global restore_checkpoint behaviour.
        """
        store = self.registry.open_project(project_id)
        try:
            with store.lock():
                result = store.restore_checkpoint(checkpoint_path)
                listed = _checkpoint_listed_paths(store, checkpoint_path)
                _retire_unlisted_data_files(store, listed, keep_secrets=True)
        except ProjectLockError as exc:
            raise StorageError("作品正在保存或生成，请稍后重试。") from exc
        return result

    def _unpack_new_directory(
        self,
        validated: _ValidatedPackage,
        *,
        target_id: str,
        mode: str,
        title: str,
        source_id: str,
    ) -> ProjectPackageImportResult:
        if not _project_id_is_valid(target_id):
            raise StorageError("项目编号不可用，请改为作为新作品导入。")
        projects_root = self.registry.projects_root
        projects_root.mkdir(parents=True, exist_ok=True)
        target = projects_root / target_id
        if target.exists():
            raise StorageError("项目库中已有相同编号，不能沿用原编号。")
        # Leading-dot name fails validate_project_id, so registry discovery skips it.
        # Same volume as projects_root: os.replace is a rename, not a cross-drive copy.
        staging = projects_root / f".importing_{utc_stamp()}"
        try:
            _write_members_to_root(validated.files, root=staging)
            _rewrite_project_id(staging, target_id)
            if target.exists():
                raise StorageError("项目库中已有相同编号，不能沿用原编号。")
            os.replace(staging, target)
        except Exception:
            # Leave `.importing_*` behind; discovery skips leading-dot names.
            raise
        # Only now is the directory a real project id — open() would have rejected the staging name.
        store = ProjectStore.open(projects_root, target_id)
        store.initialize()
        store.migrate_config()
        meta = store.read_project_meta()
        self.registry._upsert_entry(
            {
                "project_id": target_id,
                "title": str(meta.get("title") or title or target_id),
                "path": str(store.root),
                "created_at": str(meta.get("created_at") or ""),
                "updated_at": str(meta.get("updated_at") or utc_stamp()),
            }
        )
        return ProjectPackageImportResult(
            mode=mode,
            project_id=target_id,
            title=str(meta.get("title") or title or target_id),
            source_project_id=source_id,
            checkpoint=None,
        )

    def _unpack_overwrite(
        self,
        validated: _ValidatedPackage,
        *,
        project_id: str,
        title: str,
    ) -> ProjectPackageImportResult:
        store = self.registry.open_project(project_id)
        try:
            with store.lock():
                checkpoint = store.create_checkpoint(label="pre_import_overwrite", include_secrets=False)
                listed = set(validated.files)
                for posix, data in validated.files.items():
                    if posix == "data/secrets.local.json":
                        continue
                    relative = safe_archive_relative_path(posix)
                    dest = store.root / relative
                    store._atomic_write_bytes(dest, data, retire_existing=True)
                # Membership must use as_posix(); str(Path) on Windows is backslash and would
                # retire every just-written package file as "extra".
                _retire_unlisted_data_files(store, listed, keep_secrets=True)
                store.initialize()
                store.migrate_config()
                meta = store.read_project_meta()
                self.registry._upsert_entry(
                    {
                        "project_id": project_id,
                        "title": str(meta.get("title") or title or project_id),
                        "path": str(store.root),
                        "created_at": str(meta.get("created_at") or ""),
                        "updated_at": utc_stamp(),
                    }
                )
        except ProjectLockError as exc:
            raise StorageError("作品正在保存或生成，请稍后重试。") from exc
        except OSError as exc:
            raise _translate_os_error(exc) from exc
        meta = store.read_project_meta()
        return ProjectPackageImportResult(
            mode="overwrite",
            project_id=project_id,
            title=str(meta.get("title") or title or project_id),
            source_project_id=project_id,
            checkpoint=checkpoint,
        )

    def _existing_ids(self) -> set[str]:
        ids = {str(item.get("project_id") or "") for item in self.registry.list_projects()}
        root = self.registry.projects_root
        if root.exists():
            for child in root.iterdir():
                if child.is_dir() and child.name:
                    ids.add(child.name)
        return {item for item in ids if item}

    def _title_for(self, project_id: str) -> str:
        for item in self.registry.list_projects():
            if str(item.get("project_id") or "") == project_id:
                return str(item.get("title") or project_id)
        return project_id


def slug_or_novel(title: str) -> str:
    """Prefer a valid project_id as-is.

    Do not call `_slug_project_id`: it lowercases and strips CJK, collapsing many
    titles to `novel`. `validate_project_id` treats CJK as alnum, matching on-disk ids.
    """
    text = str(title or "").strip()
    try:
        validate_project_id(text)
        return text
    except InvalidProjectIdError:
        pass
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_-")[:24]
    if not slug or not slug[0].isalnum():
        slug = "novel"
    try:
        validate_project_id(slug)
        return slug
    except InvalidProjectIdError:
        return "novel"


def allocate_new_project_id(base: str, existing: set[str]) -> str:
    """Copies always start at `{base}_2` so a keep_id original stays distinguishable."""
    n = 2
    candidate = f"{base}_{n}"
    while candidate in existing:
        n += 1
        candidate = f"{base}_{n}"
    return candidate


def is_excluded_from_portable_archive(relative: Path, *, include_secrets: bool = False) -> bool:
    """Checkpoint exclusions plus package denylist. Not an alias of the checkpoint helper."""
    if is_excluded_from_checkpoint(relative, include_secrets=include_secrets):
        return True
    name = relative.name
    lower = name.lower()
    if lower.endswith((".nawpkg", ".zip", ".env")):
        return True
    if "secrets" in lower and lower.endswith(".json"):
        return True
    if lower == CHECKPOINT_MANIFEST_NAME:
        return True
    return False


def wash_config_bytes(raw: bytes) -> bytes:
    """Strip plaintext api_key from model roles. Hash/write these bytes, never the disk file."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    roles = payload.get("model_roles")
    if isinstance(roles, dict):
        for role_value in roles.values():
            if not isinstance(role_value, dict):
                continue
            role_value.pop("api_key", None)
            settings = role_value.get("settings")
            if isinstance(settings, dict):
                settings.pop("api_key", None)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return text.encode("utf-8")


def _collect_portable_files(store: ProjectStore) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    entries: list[dict[str, Any]] = []
    overrides: dict[str, bytes] = {}
    for path in sorted(store.root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(store.root)
        if is_excluded_from_portable_archive(relative, include_secrets=False):
            continue
        posix = relative.as_posix()
        if posix == "data/config.json":
            # Must writestr washed bytes. archive.write(disk file) would pack a leftover api_key.
            data = wash_config_bytes(path.read_bytes())
            overrides[posix] = data
        else:
            data = path.read_bytes()
        entries.append(
            {
                "path": posix,
                "size": len(data),
                "sha256": sha256(data).hexdigest(),
            }
        )
    return entries, overrides


def _write_package_zip(
    target: Path,
    manifest_bytes: bytes,
    entries: list[dict[str, Any]],
    store: ProjectStore,
    overrides: dict[str, bytes],
) -> None:
    # Same-directory tmp so os.replace stays on one volume (project libs are often not on C:).
    tmp = target.parent / f".{target.name}.tmp"
    if tmp.exists():
        retire_path(tmp)
    try:
        # Open writable so fsync works on Windows (a read-only handle raises EBADF).
        with open(tmp, "wb") as handle:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(PACKAGE_MANIFEST_NAME, manifest_bytes)
                for item in entries:
                    posix = str(item["path"])
                    if posix in overrides:
                        archive.writestr(posix, overrides[posix])
                    else:
                        archive.write(store.root / posix, arcname=posix)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except Exception:
        if tmp.exists():
            retire_path(tmp)
        raise


def _validate_package_file(package_path: str | Path) -> _ValidatedPackage:
    source = Path(package_path).expanduser().resolve()
    if not source.is_file():
        raise StorageError("没有找到作品包文件。")
    try:
        archive = zipfile.ZipFile(source, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise StorageError("无法作为作品包打开。") from exc
    try:
        return _validate_open_archive(source, archive)
    finally:
        archive.close()


def _validate_open_archive(package_path: Path, archive: zipfile.ZipFile) -> _ValidatedPackage:
    names = archive.namelist()
    if len(names) > MAX_PACKAGE_FILES + 1:
        raise StorageError("作品包过大或文件过多，已拒绝导入。")
    name_set = set(names)
    if CHECKPOINT_MANIFEST_NAME in name_set:
        raise StorageError("这是内部回滚检查点，不是作品包。")
    if PACKAGE_MANIFEST_NAME not in name_set:
        raise StorageError("没有找到作品包清单。")
    try:
        manifest = json.loads(archive.read(PACKAGE_MANIFEST_NAME).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        raise StorageError("没有找到作品包清单。") from exc
    if not isinstance(manifest, dict):
        raise StorageError("没有找到作品包清单。")
    try:
        schema_version = int(manifest.get("schema_version") or 0)
    except (TypeError, ValueError) as exc:
        raise StorageError("作品包版本不受支持，请升级软件后再导入。") from exc
    if str(manifest.get("format") or "") != PACKAGE_FORMAT or schema_version != 1:
        raise StorageError("作品包版本不受支持，请升级软件后再导入。")
    if manifest.get("include_secrets") is not False:
        raise StorageError("作品包含有密钥文件，已拒绝导入。")
    advertised = 0
    for info in archive.infolist():
        if info.is_dir() or info.filename == PACKAGE_MANIFEST_NAME:
            continue
        advertised += max(0, int(info.file_size or 0))
        if advertised > MAX_PACKAGE_UNCOMPRESSED_BYTES:
            raise StorageError("作品包过大或文件过多，已拒绝导入。")
    files_spec = manifest.get("files")
    if not isinstance(files_spec, list):
        raise StorageError("作品包校验失败：文件清单不一致。")
    listed: list[str] = []
    for item in files_spec:
        if not isinstance(item, dict):
            raise StorageError("作品包校验失败：文件清单不一致。")
        posix = safe_archive_relative_path(str(item.get("path") or "")).as_posix()
        listed.append(posix)
    if len(listed) != len(set(listed)):
        raise StorageError("作品包校验失败：文件清单不一致。")
    members: list[str] = []
    zip_name_by_posix: dict[str, str] = {}
    for name in names:
        if name == PACKAGE_MANIFEST_NAME:
            continue
        if name.endswith("/"):
            raise StorageError("作品包校验失败：文件清单不一致。")
        posix = safe_archive_relative_path(name).as_posix()
        if _hits_secret_denylist(posix):
            raise StorageError("作品包含有密钥文件，已拒绝导入。")
        members.append(posix)
        zip_name_by_posix[posix] = name
    if set(members) != set(listed):
        raise StorageError("作品包校验失败：文件清单不一致。")
    file_bytes: dict[str, bytes] = {}
    actual = 0
    spec_by_path = {
        safe_archive_relative_path(str(item.get("path") or "")).as_posix(): item for item in files_spec
    }
    for posix in listed:
        data = archive.read(zip_name_by_posix[posix])
        actual += len(data)
        if actual > MAX_PACKAGE_UNCOMPRESSED_BYTES:
            raise StorageError("作品包过大或文件过多，已拒绝导入。")
        item = spec_by_path[posix]
        expected_sha = str(item.get("sha256") or "")
        try:
            expected_size = int(item.get("size") or -1)
        except (TypeError, ValueError):
            expected_size = -1
        if sha256(data).hexdigest() != expected_sha or len(data) != expected_size:
            raise StorageError("作品包校验失败：文件哈希不一致。")
        file_bytes[posix] = data
    project_raw = file_bytes.get("project.json")
    if not project_raw:
        raise StorageError("作品包缺少 project.json。")
    try:
        project_meta = json.loads(project_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageError("作品包缺少 project.json。") from exc
    if not isinstance(project_meta, dict) or not str(project_meta.get("project_id") or "").strip():
        raise StorageError("作品包缺少项目编号。")
    manifest_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    if str(manifest_source.get("project_id") or "") != str(project_meta.get("project_id") or ""):
        raise StorageError("作品包清单与 project.json 的编号不一致。")
    return _ValidatedPackage(
        path=package_path,
        manifest=manifest,
        files=file_bytes,
        project_meta=project_meta,
        warnings=_inspect_warnings(file_bytes.get("data/config.json")),
    )


def _inspect_warnings(config_bytes: bytes | None) -> list[str]:
    warnings: list[str] = []
    if not config_bytes:
        return warnings
    try:
        config = json.loads(config_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return warnings
    if not isinstance(config, dict):
        return warnings
    roles = config.get("model_roles")
    if isinstance(roles, dict):
        for role_value in roles.values():
            if isinstance(role_value, dict) and str(role_value.get("api_key_ref") or "").strip():
                warnings.append("dangling_api_key_ref")
                break
    try:
        schema = int(config.get("schema_version") or 0)
    except (TypeError, ValueError):
        schema = 0
    if schema and schema < CURRENT_CONFIG_SCHEMA_VERSION:
        warnings.append("config_schema_older")
    return warnings


def _hits_secret_denylist(posix: str) -> bool:
    relative = Path(posix)
    name = relative.name.lower()
    if name == "secrets.local.json" or posix == "data/secrets.local.json":
        return True
    if "secrets" in name and name.endswith(".json"):
        return True
    if name.endswith(".env") or name == ".env":
        return True
    if name.endswith((".nawpkg", ".zip")):
        return True
    if name == CHECKPOINT_MANIFEST_NAME:
        return True
    return False


def _write_members_to_root(files: dict[str, bytes], *, root: Path) -> None:
    # Never ProjectStore.open(staging.name): leading-dot ids are invalid, and
    # opening the *target* id here would make a discoverable half-written project.
    root.mkdir(parents=True, exist_ok=True)
    jail = root.resolve()
    for posix, data in files.items():
        if posix == "data/secrets.local.json":
            continue
        relative = safe_archive_relative_path(posix)
        dest = (root / relative).resolve()
        try:
            dest.relative_to(jail)
        except ValueError as exc:
            raise StorageError(f"Unsafe archive path: {posix!r}") from exc
        atomic_write_bytes_file(dest, data, root=jail, retire_existing=False)


def _rewrite_project_id(staging: Path, target_id: str) -> None:
    path = staging / "project.json"
    if not path.exists():
        raise StorageError("作品包缺少 project.json。")
    meta = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise StorageError("作品包缺少 project.json。")
    meta["project_id"] = target_id
    meta["updated_at"] = utc_stamp()
    data = (json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes_file(path, data, root=staging.resolve(), retire_existing=True)


def _retire_unlisted_data_files(store: ProjectStore, listed: set[str], *, keep_secrets: bool) -> None:
    if not store.data_dir.exists():
        return
    for path in store.data_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(store.root).as_posix()
        if keep_secrets and relative == "data/secrets.local.json":
            continue
        if path.name.endswith(".trash"):
            continue
        if relative not in listed:
            retire_path(path)


def _checkpoint_listed_paths(store: ProjectStore, checkpoint_path: str | Path) -> set[str]:
    source = store._resolve_owned_path(checkpoint_path)
    with zipfile.ZipFile(source, "r") as archive:
        manifest = json.loads(archive.read(CHECKPOINT_MANIFEST_NAME).decode("utf-8"))
    files = manifest.get("files") if isinstance(manifest, dict) else None
    listed: set[str] = set()
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and item.get("path"):
                listed.add(safe_archive_relative_path(str(item["path"])).as_posix())
    return listed


def _resolve_output_path(output_path: str | Path) -> Path:
    target = Path(output_path).expanduser()
    if target.suffix.lower() not in {".nawpkg", ".zip"}:
        target = target.with_suffix(".nawpkg")
    return target.resolve()


def _reject_output_inside_project(store: ProjectStore, target: Path) -> None:
    try:
        target.relative_to(store.root.resolve())
    except ValueError:
        return
    raise StorageError("不能把作品包保存到作品目录内。")


def _project_id_is_valid(project_id: str) -> bool:
    try:
        validate_project_id(project_id)
        return True
    except InvalidProjectIdError:
        return False


def _config_schema_version(config_bytes: bytes | None) -> int:
    if not config_bytes:
        return CURRENT_CONFIG_SCHEMA_VERSION
    try:
        payload = json.loads(config_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return CURRENT_CONFIG_SCHEMA_VERSION
    if not isinstance(payload, dict):
        return CURRENT_CONFIG_SCHEMA_VERSION
    try:
        return int(payload.get("schema_version") or CURRENT_CONFIG_SCHEMA_VERSION)
    except (TypeError, ValueError):
        return CURRENT_CONFIG_SCHEMA_VERSION


def _inventory_for(store: ProjectStore, entries: list[dict[str, Any]]) -> dict[str, Any]:
    def load(name: str) -> dict[str, Any]:
        path = store.data_dir / name
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def count(payload: dict[str, Any], *keys: str) -> int:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 0

    return {
        "confirmed_chapter_count": count(load("confirmed_chapters.json"), "chapters", "items"),
        "draft_count": count(load("drafts_index.json"), "drafts", "items"),
        "review_count": count(load("reviews_index.json"), "reviews", "items"),
        "planning_item_count": count(load("planning_library.json"), "items"),
        "memory_bank_item_count": count(load("memory_bank.json"), "items"),
        "file_count": len(entries),
        "bytes": sum(int(item.get("size") or 0) for item in entries),
    }


def _workbench_version() -> str:
    try:
        from importlib.metadata import version

        return version("novel-agent-workbench")
    except Exception:
        return "0.1.0"


def _translate_os_error(exc: OSError) -> StorageError:
    if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32, 33}:
        return StorageError("文件被占用，请关闭后重试。")
    return StorageError(str(exc))
