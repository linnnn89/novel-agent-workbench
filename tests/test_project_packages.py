from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.project_packages import (
    PACKAGE_FORMAT,
    PACKAGE_MANIFEST_NAME,
    ProjectPackageService,
    allocate_new_project_id,
    slug_or_novel,
)
from novel_agent_workbench.storage import ProjectRegistry, StorageError, utc_stamp


class ProjectPackageServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "workspace_projects"
        self.registry = ProjectRegistry.open(self.root)
        self.registry.initialize()
        self.service = ProjectPackageService(self.registry)
        self.app = WorkbenchApplicationService(self.registry)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _create(self, project_id: str, title: str = "") -> None:
        self.registry.create_project(project_id, title=title or project_id)

    def _pack(self, project_id: str, name: str = "book.nawpkg") -> Path:
        out = Path(self._tmp.name) / name
        self.service.pack(project_id, out)
        return out

    def test_roundtrip_keep_id_and_empty_outline_export(self) -> None:
        self._create("alpha", "空大纲")
        package = self._pack("alpha", "empty.nawpkg")
        self.assertTrue(package.is_file())
        dest_root = Path(self._tmp.name) / "other_lib"
        other = ProjectPackageService(ProjectRegistry.open(dest_root))
        imported = other.unpack(package, mode="keep_id")
        self.assertEqual("alpha", imported.project_id)
        self.assertEqual("keep_id", imported.mode)
        store = other.registry.open_project("alpha")
        self.assertEqual("空大纲", store.read_project_meta().get("title"))
        self.assertTrue((store.data_dir / "secrets.local.json").exists())

    def test_new_id_skips_occupied_suffixes(self) -> None:
        self._create("novel", "一")
        self._create("novel_2", "二")
        package = self._pack("novel")
        imported = self.service.unpack(package, mode="new_id")
        self.assertEqual("novel_3", imported.project_id)

    def test_api_key_and_env_and_secrets_never_enter_package(self) -> None:
        self._create("leaky")
        store = self.registry.open_project("leaky")
        config = store.read_config()
        config["model_roles"]["writer"]["api_key"] = "sk-leaked-test-key-please-hide"
        config["model_roles"]["writer"]["settings"]["api_key"] = "sk-settings-leak"
        store.write_config(config)
        store.write_secrets({"writer": "real-secret-value"})
        (store.data_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
        (store.data_dir / "my_secrets.json").write_text('{"k":"v"}', encoding="utf-8")
        package = self._pack("leaky", "leaky.nawpkg")
        raw = package.read_bytes()
        self.assertNotIn(b"sk-leaked-test-key-please-hide", raw)
        self.assertNotIn(b"sk-settings-leak", raw)
        self.assertNotIn(b"real-secret-value", raw)
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
        self.assertNotIn("data/secrets.local.json", names)
        self.assertNotIn("data/.env", names)
        self.assertNotIn("data/my_secrets.json", names)
        imported = self.service.unpack(package, mode="new_id")
        restored = self.registry.open_project(imported.project_id).read_config()
        writer = restored["model_roles"]["writer"]
        self.assertNotIn("api_key", writer)
        self.assertNotIn("api_key", writer.get("settings") or {})

    def test_output_inside_project_is_rejected(self) -> None:
        self._create("inside")
        store = self.registry.open_project("inside")
        with self.assertRaisesRegex(StorageError, "不能把作品包保存到作品目录内"):
            self.service.pack("inside", store.root / "book.nawpkg")

    def test_overwrite_requires_phrase_keeps_secrets_and_posix_membership(self) -> None:
        self._create("same", "旧标题")
        target = self.registry.open_project("same")
        target.write_secrets({"writer": "keep-me"})
        (target.data_dir / "orphan.json").write_text('{"orphan": true}', encoding="utf-8")
        self._create("source", "新标题")
        source = self.registry.open_project("source")
        (source.data_dir / "from_package.json").write_text('{"from": "package"}', encoding="utf-8")
        # Force the package to advertise project_id=same so overwrite hits this row.
        package = Path(self._tmp.name) / "same.nawpkg"
        packed = Path(self._tmp.name) / "source.nawpkg"
        self.service.pack("source", packed)
        self._relabel_package_id(packed, package, "same", "新标题")
        with self.assertRaisesRegex(StorageError, "确认覆盖"):
            self.service.unpack(package, mode="overwrite", confirm_text="")
        self.assertTrue((target.data_dir / "orphan.json").exists())
        result = self.service.unpack(package, mode="overwrite", confirm_text="确认覆盖")
        self.assertEqual("overwrite", result.mode)
        self.assertTrue((target.data_dir / "from_package.json").exists())
        self.assertFalse((target.data_dir / "orphan.json").exists())
        self.assertEqual({"writer": "keep-me"}, target.read_secrets())
        checkpoint_path = result.checkpoint["path"]
        self.service.restore_pre_import_overwrite("same", checkpoint_path)
        self.assertTrue((target.data_dir / "orphan.json").exists())
        self.assertFalse((target.data_dir / "from_package.json").exists())
        self.assertEqual({"writer": "keep-me"}, target.read_secrets())

    def test_staging_failure_leaves_only_importing_dir(self) -> None:
        self._create("origin")
        package = self._pack("origin", "origin.nawpkg")
        dest_root = Path(self._tmp.name) / "fresh_lib"
        other_registry = ProjectRegistry.open(dest_root)
        other_registry.initialize()
        other = ProjectPackageService(other_registry)
        calls = {"n": 0}
        real = __import__("novel_agent_workbench.project_packages", fromlist=["atomic_write_bytes_file"]).atomic_write_bytes_file

        def boom(path, data, *, root, retire_existing=False):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("injected")
            return real(path, data, root=root, retire_existing=retire_existing)

        with patch("novel_agent_workbench.project_packages.atomic_write_bytes_file", boom):
            with self.assertRaises(OSError):
                other.unpack(package, mode="keep_id")
        self.assertFalse((dest_root / "origin").exists())
        leftovers = [child.name for child in dest_root.iterdir() if child.name.startswith(".importing_")]
        self.assertTrue(leftovers)

    def test_swapped_zip_with_secrets_does_not_write_project(self) -> None:
        self._create("origin")
        package = self._pack("origin", "swap.nawpkg")
        inspect = self.service.inspect(package)
        self.assertEqual("origin", inspect.source_project_id)
        self._handcraft(
            package,
            project_id="origin",
            title="恶意",
            extra_files={"data/secrets.local.json": b'{"writer":"stolen"}'},
        )
        dest_root = Path(self._tmp.name) / "swap_lib"
        other = ProjectPackageService(ProjectRegistry.open(dest_root))
        other.registry.initialize()
        with self.assertRaisesRegex(StorageError, "密钥"):
            other.unpack(package, mode="keep_id")
        self.assertFalse((dest_root / "origin").exists())

    def test_zip_slip_and_checkpoint_rejected(self) -> None:
        slip = Path(self._tmp.name) / "slip.nawpkg"
        project = {"project_id": "ok", "title": "ok", "schema_version": 1}
        payload = json.dumps(project).encode("utf-8")
        files = {
            "project.json": payload,
            "../evil.json": b"nope",
        }
        self._write_raw_zip(slip, files, source_id="ok")
        with self.assertRaises(StorageError):
            self.service.inspect(slip)
        self._create("cp")
        store = self.registry.open_project("cp")
        checkpoint = store.create_checkpoint(label="manual")
        with self.assertRaisesRegex(StorageError, "检查点"):
            self.service.inspect(checkpoint["path"])

    def test_illegal_id_keep_id_fails_new_id_succeeds(self) -> None:
        package = Path(self._tmp.name) / "bad.nawpkg"
        self._handcraft(package, project_id="bad id", title="坏编号")
        inspect = self.service.inspect(package)
        self.assertFalse(inspect.source_project_id_valid)
        self.assertTrue(inspect.suggested_new_project_id)
        with self.assertRaisesRegex(StorageError, "项目编号不可用"):
            self.service.unpack(package, mode="keep_id")
        imported = self.service.unpack(package, mode="new_id")
        self.assertNotEqual("bad id", imported.project_id)
        self.registry.open_project(imported.project_id)

    def test_manifest_project_id_mismatch(self) -> None:
        package = Path(self._tmp.name) / "mismatch.nawpkg"
        self._handcraft(package, project_id="one", title="一", manifest_source_id="two")
        with self.assertRaisesRegex(StorageError, "编号不一致"):
            self.service.inspect(package)

    def test_actual_read_cap_aborts(self) -> None:
        self._create("big")
        package = self._pack("big", "big.nawpkg")
        with patch("novel_agent_workbench.project_packages.MAX_PACKAGE_UNCOMPRESSED_BYTES", 8):
            with self.assertRaisesRegex(StorageError, "过大或文件过多"):
                self.service.inspect(package)

    def test_allocate_helpers(self) -> None:
        self.assertEqual("MyNovel", slug_or_novel("MyNovel"))
        # 现网 project_id 允许中文（str.isalnum），所以中文标题沿用为编号，不塌成 novel。
        self.assertEqual("贞操逆转世界", slug_or_novel("贞操逆转世界"))
        self.assertEqual("novel", slug_or_novel("***"))
        self.assertEqual("novel_3", allocate_new_project_id("novel", {"novel", "novel_2"}))

    def test_facade_and_cli_roundtrip(self) -> None:
        self.app.create_project("via_app", title="门面")
        out = Path(self._tmp.name) / "via.nawpkg"
        exported = self.app.export_project_package("via_app", out)
        self.assertEqual("via_app", exported["project_id"])
        inspected = self.app.inspect_project_package(out)
        self.assertEqual(PACKAGE_FORMAT, inspected["format"])
        other_root = Path(self._tmp.name) / "cli_lib"
        from novel_agent_workbench.cli import build_parser, run_command

        parser = build_parser()
        other_app = WorkbenchApplicationService.open(other_root)
        other_app.registry.initialize()
        imported = other_app.import_project_package(out, mode="keep_id")
        self.assertEqual("via_app", imported["project_id"])
        args = parser.parse_args(
            ["--projects-root", str(other_root), "inspect-project-package", str(out)]
        )
        listed = run_command(args)
        self.assertEqual("via_app", listed["source_project_id"])

    def _relabel_package_id(self, source: Path, dest: Path, project_id: str, title: str) -> None:
        with zipfile.ZipFile(source, "r") as archive:
            names = archive.namelist()
            payload = {name: archive.read(name) for name in names}
        meta = json.loads(payload["project.json"].decode("utf-8"))
        meta["project_id"] = project_id
        meta["title"] = title
        payload["project.json"] = (json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        manifest = json.loads(payload[PACKAGE_MANIFEST_NAME].decode("utf-8"))
        manifest["source"]["project_id"] = project_id
        manifest["source"]["title"] = title
        files = []
        for item in manifest["files"]:
            data = payload[item["path"]]
            files.append({"path": item["path"], "size": len(data), "sha256": sha256(data).hexdigest()})
        manifest["files"] = files
        payload[PACKAGE_MANIFEST_NAME] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in payload.items():
                archive.writestr(name, data)

    def _handcraft(
        self,
        path: Path,
        *,
        project_id: str,
        title: str,
        extra_files: dict[str, bytes] | None = None,
        manifest_source_id: str | None = None,
        include_secrets: bool = False,
    ) -> None:
        project = {
            "project_id": project_id,
            "title": title,
            "schema_version": 1,
            "created_at": utc_stamp(),
            "updated_at": utc_stamp(),
        }
        config = {"schema_version": 4, "model_roles": {}}
        files: dict[str, bytes] = {
            "project.json": (json.dumps(project, ensure_ascii=False) + "\n").encode("utf-8"),
            "data/config.json": (json.dumps(config, ensure_ascii=False) + "\n").encode("utf-8"),
        }
        if extra_files:
            files.update(extra_files)
        self._write_raw_zip(
            path,
            files,
            source_id=manifest_source_id if manifest_source_id is not None else project_id,
            include_secrets=include_secrets,
            title=title,
        )

    def _write_raw_zip(
        self,
        path: Path,
        files: dict[str, bytes],
        *,
        source_id: str,
        include_secrets: bool = False,
        title: str = "",
    ) -> None:
        entries = [{"path": name, "size": len(data), "sha256": sha256(data).hexdigest()} for name, data in files.items()]
        manifest = {
            "format": PACKAGE_FORMAT,
            "schema_version": 1,
            "package_id": "t",
            "exported_at": "t",
            "workbench_version": "0.1.0",
            "source": {
                "project_id": source_id,
                "title": title or source_id,
                "project_schema_version": 1,
                "config_schema_version": 4,
            },
            "include_secrets": include_secrets,
            "exclusions": [],
            "inventory": {"file_count": len(entries), "bytes": sum(item["size"] for item in entries)},
            "files": entries,
        }
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(PACKAGE_MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
            for name, data in files.items():
                archive.writestr(name, data)


if __name__ == "__main__":
    unittest.main()
