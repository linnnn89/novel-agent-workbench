from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import ProjectStore
from novel_agent_workbench.config import CURRENT_CONFIG_SCHEMA_VERSION, DATA_FILE_DEFAULTS, FORMAL_CONTEXT_PRIORITY_ORDER


class ProjectFoundationTest(unittest.TestCase):
    def test_new_project_has_default_config_and_placeholder_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            config = store.read_config()
            self.assertEqual(config["schema_version"], CURRENT_CONFIG_SCHEMA_VERSION)
            self.assertEqual(set(config["model_roles"]), {"writer", "scorer", "reviser"})
            self.assertEqual(config["active_workflow_preset_id"], "manual_studio")
            self.assertEqual(
                config["context_policy"]["formal_context_policy"]["priority_order"],
                FORMAL_CONTEXT_PRIORITY_ORDER,
            )
            self.assertEqual(
                set(config["context_policy"]["formal_context_policy"]["categories"]),
                set(FORMAL_CONTEXT_PRIORITY_ORDER),
            )
            self.assertEqual(
                {item["id"] for item in config["workflow_presets"]},
                {"classic_direct", "manual_studio", "auto_pipeline"},
            )

            for name in DATA_FILE_DEFAULTS:
                self.assertTrue(store.data_file_path(name).exists(), name)

    def test_migration_fills_legacy_config_and_creates_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_config({"schema_version": 0, "context_policy": {"memory_bank_enabled": True}})
            store.write_secrets({"api_key": "sk-test-secret"})

            result = store.migrate_config()
            config = store.read_config()

            self.assertTrue(result["changed"])
            self.assertEqual(config["schema_version"], CURRENT_CONFIG_SCHEMA_VERSION)
            self.assertTrue(config["context_policy"]["memory_bank_enabled"])
            self.assertEqual(
                config["context_policy"]["formal_context_policy"]["priority_order"],
                FORMAL_CONTEXT_PRIORITY_ORDER,
            )
            self.assertIn("writer", config["model_roles"])
            self.assertTrue(result["checkpoint"]["path"].endswith(".zip"))
            self.assertTrue(Path(result["checkpoint"]["path"]).exists())
            self.assertNotIn("sk-test-secret", store.config_path.read_text(encoding="utf-8"))

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_config({"schema_version": 0})

            first = store.migrate_config()
            first_config = store.read_config()
            second = store.migrate_config()
            second_config = store.read_config()

            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual(first_config, second_config)

    def test_migration_checkpoint_excludes_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_config({"schema_version": 0})
            store.write_secrets({"api_key": "sk-test-secret"})

            result = store.migrate_config()

            with zipfile.ZipFile(Path(result["checkpoint"]["path"]), "r") as archive:
                names = set(archive.namelist())
                content = "\n".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in names
                    if name.endswith(".json")
                )

            self.assertNotIn("data/secrets.local.json", names)
            self.assertNotIn("sk-test-secret", content)

    def test_migration_checkpoint_is_taken_before_default_files_are_added(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "legacy")
            store.data_dir.mkdir(parents=True)
            store.config_path.write_text('{"schema_version": 0}\n', encoding="utf-8")

            result = store.migrate_config()

            with zipfile.ZipFile(Path(result["checkpoint"]["path"]), "r") as archive:
                names = set(archive.namelist())

            self.assertIn("data/config.json", names)
            self.assertNotIn("data/planning_library.json", names)
            self.assertTrue(store.data_file_path("planning_library.json").exists())

    def test_migration_creates_missing_project_meta_after_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "legacy")
            store.data_dir.mkdir(parents=True)
            store.config_path.write_text('{"schema_version": 0}\n', encoding="utf-8")

            result = store.migrate_config()

            self.assertTrue(result["created_project_meta"])
            self.assertEqual(store.read_project_meta()["project_id"], "legacy")
            with zipfile.ZipFile(Path(result["checkpoint"]["path"]), "r") as archive:
                names = set(archive.namelist())
            self.assertNotIn("project.json", names)

    def test_update_secrets_and_public_state_never_return_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            store.update_secrets({"api_key": "sk-test-secret", "short": "abcd"})
            state = store.public_state()
            state_text = json.dumps(state, ensure_ascii=False)

            self.assertEqual(store.read_secrets()["api_key"], "sk-test-secret")
            self.assertNotIn("sk-test-secret", state_text)
            self.assertTrue(state["secrets"]["api_key"]["has_value"])
            self.assertEqual(state["secrets"]["api_key"]["masked"], "sk-****cret")
            self.assertEqual(state["secrets"]["short"]["masked"], "****")
            self.assertNotIn("sk-test-secret", store.config_path.read_text(encoding="utf-8"))

    def test_checkpoint_excludes_backups_and_trash_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_config({"schema_version": CURRENT_CONFIG_SCHEMA_VERSION, "marker": "first"})
            store.write_config({"schema_version": CURRENT_CONFIG_SCHEMA_VERSION, "marker": "second"})
            trash_file = store.data_dir / "old_note.txt.trash"
            trash_file.write_text("discarded but recoverable", encoding="utf-8")

            checkpoint = store.create_checkpoint(label="clean")

            with zipfile.ZipFile(Path(checkpoint["path"]), "r") as archive:
                names = set(archive.namelist())

            self.assertFalse(any(name.startswith("backups/") for name in names))
            self.assertNotIn("data/old_note.txt.trash", names)


if __name__ == "__main__":
    unittest.main()
