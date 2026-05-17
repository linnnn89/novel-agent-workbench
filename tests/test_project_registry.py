from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import InvalidProjectIdError, ProjectRegistry, ProjectStore, StorageError
from novel_agent_workbench.storage import DEFAULT_PROJECTS_DIRNAME


class ProjectRegistryTest(unittest.TestCase):
    def test_default_registry_routes_to_workspace_projects(self) -> None:
        registry = ProjectRegistry.default()

        self.assertEqual(registry.projects_root.name, DEFAULT_PROJECTS_DIRNAME)
        self.assertTrue(str(registry.projects_root).endswith(r"novel_agent_workbench\workspace_projects"))

    def test_create_project_initializes_store_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = ProjectRegistry.open(Path(temp) / "workspace_projects")
            store = registry.create_project("alpha", title="Alpha Book")

            self.assertIsInstance(store, ProjectStore)
            self.assertTrue(store.project_meta_path.exists())
            self.assertEqual(store.read_project_meta()["title"], "Alpha Book")

            entries = registry.list_projects()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["project_id"], "alpha")
            self.assertEqual(entries[0]["title"], "Alpha Book")
            self.assertTrue(registry.registry_path.exists())

    def test_open_project_returns_existing_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = ProjectRegistry.open(Path(temp) / "workspace_projects")
            registry.create_project("alpha")

            opened = registry.open_project("alpha")

            self.assertEqual(opened.project_id, "alpha")
            self.assertEqual(opened.read_project_meta()["project_id"], "alpha")

    def test_open_missing_project_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = ProjectRegistry.open(Path(temp) / "workspace_projects")
            registry.initialize()

            with self.assertRaises(StorageError):
                registry.open_project("missing")

    def test_list_projects_discovers_valid_unindexed_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace_projects"
            registry = ProjectRegistry.open(root)
            orphan = ProjectStore.open(root, "orphan")
            orphan.initialize()
            meta = orphan.read_project_meta()
            meta["title"] = "Orphan Book"
            orphan.write_project_meta(meta)

            entries = registry.list_projects()

            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["project_id"], "orphan")
            self.assertEqual(entries[0]["title"], "Orphan Book")

    def test_registry_rejects_unsafe_project_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            registry = ProjectRegistry.open(Path(temp) / "workspace_projects")

            with self.assertRaises(InvalidProjectIdError):
                registry.create_project("../evil")

    def test_registry_public_api_has_no_hard_delete_method(self) -> None:
        public_methods = [
            name
            for name, value in inspect.getmembers(ProjectRegistry, predicate=inspect.isfunction)
            if not name.startswith("_")
        ]

        self.assertNotIn("delete", public_methods)
        self.assertNotIn("remove", public_methods)
        self.assertFalse(any(name.startswith("delete_") or name.startswith("remove_") for name in public_methods))


if __name__ == "__main__":
    unittest.main()
