from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import InvalidProjectIdError, ProjectLockError, ProjectStore, StorageError
from novel_agent_workbench.config import CURRENT_CONFIG_SCHEMA_VERSION
from novel_agent_workbench.storage import TRASH_SUFFIX


class ProjectStoreTest(unittest.TestCase):
    def test_initialize_creates_project_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            self.assertTrue(store.root.exists())
            self.assertTrue(store.data_dir.exists())
            self.assertTrue(store.backups_dir.exists())
            self.assertTrue(store.locks_dir.exists())
            self.assertEqual(store.read_project_meta()["project_id"], "demo")
            self.assertEqual(store.read_config()["schema_version"], CURRENT_CONFIG_SCHEMA_VERSION)
            self.assertEqual(store.read_secrets(), {})

    def test_write_and_read_json_with_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            store.write_config({"version": 1})
            store.write_config({"version": 2})

            self.assertEqual(store.read_config(), {"version": 2})
            backups = list(store.backups_dir.glob("*.bak"))
            self.assertTrue(backups)
            self.assertTrue(any("config.json" in item.name for item in backups))

    def test_secrets_are_separate_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            store.write_config({"llm": {"has_key": True}})
            store.write_secrets({"api_key": "sk-test-secret"})

            self.assertEqual(store.read_config(), {"llm": {"has_key": True}})
            self.assertEqual(store.read_secrets(), {"api_key": "sk-test-secret"})
            self.assertNotIn("sk-test-secret", store.config_path.read_text(encoding="utf-8"))

    def test_rejects_unsafe_project_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for project_id in ["", ".", "..", "../evil", r"..\evil", "evil/project", "evil:project", "bad name"]:
                with self.subTest(project_id=project_id):
                    with self.assertRaises(InvalidProjectIdError):
                        ProjectStore.open(Path(temp), project_id)

    def test_project_lock_prevents_duplicate_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with store.lock():
                with self.assertRaises(ProjectLockError):
                    with store.lock():
                        pass

            with store.lock():
                pass

            retired_locks = list(store.locks_dir.glob(f"project.lock.*{TRASH_SUFFIX}"))
            self.assertGreaterEqual(len(retired_locks), 2)

    def test_public_api_has_no_hard_delete_method(self) -> None:
        public_methods = [
            name
            for name, value in inspect.getmembers(ProjectStore, predicate=inspect.isfunction)
            if not name.startswith("_")
        ]

        self.assertNotIn("delete", public_methods)
        self.assertNotIn("remove", public_methods)
        self.assertFalse(any(name.startswith("delete_") or name.startswith("remove_") for name in public_methods))

    def test_checkpoint_excludes_secrets_by_default_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_config({"version": 1})
            store.write_secrets({"api_key": "sk-test-secret"})

            checkpoint = store.create_checkpoint(label="before change")

            checkpoint_path = Path(checkpoint["path"])
            self.assertTrue(checkpoint_path.exists())
            with zipfile.ZipFile(checkpoint_path, "r") as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("checkpoint_manifest.json").decode("utf-8"))

            self.assertIn("checkpoint_manifest.json", names)
            self.assertIn("data/config.json", names)
            self.assertIn("project.json", names)
            self.assertNotIn("data/secrets.local.json", names)
            self.assertFalse(manifest["include_secrets"])
            self.assertTrue(all("sha256" in item for item in manifest["files"]))

    def test_checkpoint_can_include_secrets_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_secrets({"api_key": "sk-test-secret"})

            checkpoint = store.create_checkpoint(label="with secrets", include_secrets=True)

            with zipfile.ZipFile(Path(checkpoint["path"]), "r") as archive:
                names = set(archive.namelist())

            self.assertIn("data/secrets.local.json", names)

    def test_restore_checkpoint_restores_files_and_retires_overwritten_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_config({"version": 1})
            checkpoint = store.create_checkpoint(label="before version 2")

            store.write_config({"version": 2})
            restored = store.restore_checkpoint(checkpoint["path"])

            self.assertEqual(store.read_config(), {"version": 1})
            self.assertIn("data/config.json", restored["restored_files"])
            retired_configs = list(store.data_dir.glob(f"config.json.*{TRASH_SUFFIX}"))
            self.assertTrue(retired_configs)
            self.assertTrue(any('"version": 2' in item.read_text(encoding="utf-8") for item in retired_configs))

    def test_restore_rejects_project_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = ProjectStore.open(Path(temp), "first")
            second = ProjectStore.open(Path(temp), "second")
            first.initialize()
            second.initialize()
            checkpoint = first.create_checkpoint(label="first only")

            with self.assertRaises(StorageError):
                second.restore_checkpoint(checkpoint["path"])

    def test_restore_rejects_unsafe_checkpoint_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            bad_zip = store.backups_dir / "bad.zip"
            with zipfile.ZipFile(bad_zip, "w") as archive:
                archive.writestr(
                    "checkpoint_manifest.json",
                    json.dumps(
                        {
                            "checkpoint_id": "bad",
                            "project_id": "demo",
                            "files": [{"path": "../escape.json", "size": 2, "sha256": "bad"}],
                        }
                    ),
                )
                archive.writestr("../escape.json", "{}")

            with self.assertRaises(StorageError):
                store.restore_checkpoint(bad_zip)


if __name__ == "__main__":
    unittest.main()
