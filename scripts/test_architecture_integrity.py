"""Backup economy and isolation of the daily project overview."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.memory_bank import MemoryBankService
from novel_agent_workbench.modern_desktop import WorkbenchBridge
from novel_agent_workbench.planning_library import PlanningLibraryService
from novel_agent_workbench.storage import ProjectStore


class ArchitectureIntegrityTests(unittest.TestCase):
    def test_memory_edit_keeps_one_checkpoint_and_unchanged_save_keeps_backups(self):
        with tempfile.TemporaryDirectory(prefix="novel-memory-backups-") as temporary:
            api = WorkbenchBridge(projects_root=Path(temporary), repo_root=Path(temporary))
            api.app.create_project("test")
            store = ProjectStore.open(temporary, "test")
            memory = MemoryBankService(store)
            memory.ensure_main_memory_item()
            memory.set_memory_text("main_memory_bank", "Original memory.")
            memory.set_memory_item_enabled("main_memory_bank", enabled=False)
            path = store.data_file_path("memory_bank.json")
            payload = {"project_id": "test", "text": "Changed memory.", "enabled": True,
                       "target_tokens": 16000, "chapter_ids": ["chapter_1"]}
            checkpoints = set(store.backups_dir.rglob("*.zip"))
            result = api.save_memory_workspace(payload)
            self.assertTrue(result["ok"], result)
            item = json.loads(path.read_text(encoding="utf-8"))["items"][0]
            self.assertEqual((item["text"], item["enabled"], item["target_token_budget"], item["source_chapter_ids"]),
                             ("Changed memory.", True, 16000, ["chapter_1"]))
            self.assertEqual(len(set(store.backups_dir.rglob("*.zip")) - checkpoints), 1)
            saved_bytes = path.read_bytes()
            backups = {p.relative_to(store.backups_dir): p.read_bytes() for p in store.backups_dir.rglob("*") if p.is_file()}
            self.assertTrue(api.save_memory_workspace(payload)["ok"])
            self.assertEqual(path.read_bytes(), saved_bytes)
            self.assertEqual(backups, {p.relative_to(store.backups_dir): p.read_bytes() for p in store.backups_dir.rglob("*") if p.is_file()})

            checkpoints = set(store.backups_dir.rglob("*.zip"))
            self.assertTrue(api.save_memory_workspace({**payload, "enabled": False})["ok"])
            self.assertEqual(len(set(store.backups_dir.rglob("*.zip")) - checkpoints), 1,
                             "A flags-only change still needs its own pre-change checkpoint")

    def test_unchanged_planning_save_and_flags_keep_existing_versions(self):
        with tempfile.TemporaryDirectory(prefix="novel-planning-backups-") as temporary:
            store = ProjectStore.open(temporary, "test")
            store.initialize()
            planning = PlanningLibraryService(store)
            fields = {"text": "A concrete outline.", "title": "Outline", "active": True}
            planning.create_planning_item("outline", **fields)
            path = store.data_file_path("planning_library.json")
            before = path.read_bytes()
            backups = {p.relative_to(store.backups_dir): p.read_bytes() for p in store.backups_dir.rglob("*") if p.is_file()}
            planning.update_planning_item("outline", **fields)
            planning.set_planning_item_active("outline", active=True)
            planning.set_planning_item_enabled("outline", enabled=True)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(backups, {p.relative_to(store.backups_dir): p.read_bytes() for p in store.backups_dir.rglob("*") if p.is_file()})
            checkpoints = set(store.backups_dir.rglob("*.zip"))
            planning.update_planning_item("outline", **{**fields, "text": "An updated outline."})
            self.assertEqual(len(set(store.backups_dir.rglob("*.zip")) - checkpoints), 1)
            self.assertEqual(planning.read_planning_item("outline", include_text=True)["text"], "An updated outline.")

    def test_daily_overview_ignores_broken_advanced_record_but_diagnostics_reports_it(self):
        with tempfile.TemporaryDirectory(prefix="novel-overview-") as temporary:
            api = WorkbenchBridge(projects_root=Path(temporary), repo_root=Path(temporary))
            api.app.create_project("test")
            store = ProjectStore.open(temporary, "test")
            DraftGenerationService(store).save_provider_draft_version(
                chapter_id="chapter_1", title="Chapter one", content="A draft.",
                provider_role="writer", provider="mock", model="mock")
            normal = api.project_overview("test")
            self.assertTrue(normal["ok"])
            self.assertEqual(normal["data"]["draft_count"], 1)
            self.assertEqual(normal["data"]["chapter_count"], 1)
            advanced = store.data_dir / "final_provider_real_executions_index.json"
            advanced.write_text("{broken fixture", encoding="utf-8")
            self.assertEqual(api.project_overview("test"), normal)
            self.assertEqual(advanced.read_text(encoding="utf-8"), "{broken fixture")
            with self.assertRaises(json.JSONDecodeError):
                api.app.project_state("test")


if __name__ == "__main__":
    unittest.main()
