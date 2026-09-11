"""Ordering and recovery regressions with real isolated project files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.context_assembler import recent_confirmed_entries
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.storage import ProjectStore, StorageError


class IterationIntegrityTests(unittest.TestCase):
    def test_previous_chapters_follow_story_order_and_exclude_future(self):
        entries = [{"chapter_id": value} for value in ("chapter_3", "chapter_01", "chapter_10", "chapter_02")]
        ids = lambda target, count: [item["chapter_id"] for item in recent_confirmed_entries(entries, chapter_id=target, count=count)]
        self.assertEqual(ids("chapter_2", 3), ["chapter_01"])
        self.assertEqual(ids("chapter_8", 2), ["chapter_02", "chapter_3"])
        self.assertEqual(ids("chapter_1", 2), [])
        self.assertEqual(ids("", 2), ["chapter_3", "chapter_10"])
        self.assertEqual(ids("chapter_8", 0), [])
        with self.assertRaisesRegex(ValueError, "自定义章节"):
            ids("epilogue", 2)

    def test_history_restore_validates_before_writes_and_preserves_original(self):
        with tempfile.TemporaryDirectory(prefix="novel-history-") as temporary:
            root = Path(temporary)
            app = WorkbenchApplicationService.open(root)
            app.create_project("original", title="恢复测试")
            store = ProjectStore.open(root, "original")
            drafts = DraftGenerationService(store)
            draft = drafts.save_provider_draft_version(chapter_id="chapter_1", title="旧城", content="备份时的正文。", provider_role="writer", provider="mock", model="mock")
            store.write_json(store.data_file_path("memory_bank.json"), {"items": [{"memory_id": "main_memory_bank", "text": "备份时的记忆。"}]})
            store.write_json(store.secrets_path, {"test_key": "local-test-secret"})
            config = store.read_json(store.config_path)
            config.setdefault("model_roles", {}).setdefault("writer", {})["api_key"] = "legacy-test-secret"
            store.write_json(store.config_path, config)
            checkpoint = store.create_checkpoint(label="pre_delete_chapter_1_drafts", include_secrets=True)
            backup = Path(checkpoint["path"])
            backup_id = backup.relative_to(root).as_posix()
            drafts.update_draft_content(draft.draft_id, text="当前正文不能被覆盖。")
            before = {path.relative_to(store.root).as_posix(): path.read_bytes() for path in store.root.rglob("*") if path.is_file()}
            preview = app.inspect_history_backup(backup_id)
            self.assertTrue(preview["validated"])
            self.assertEqual(preview["draft_count"], 1)
            result = app.restore_history_backup(backup_id)
            recovered = ProjectStore.open(root, result["project_id"])
            self.assertNotEqual(result["project_id"], "original")
            self.assertIn("恢复副本", recovered.read_project_meta()["title"])
            self.assertEqual(DraftGenerationService(recovered).read_draft(draft.draft_id)["content"], "备份时的正文。")
            self.assertEqual(recovered.read_json(recovered.data_file_path("memory_bank.json"))["items"][0]["text"], "备份时的记忆。")
            self.assertNotIn("local-test-secret", recovered.secrets_path.read_text(encoding="utf-8"))
            self.assertNotIn("legacy-test-secret", recovered.config_path.read_text(encoding="utf-8"))
            self.assertEqual(before, {path.relative_to(store.root).as_posix(): path.read_bytes() for path in store.root.rglob("*") if path.is_file()})
            with zipfile.ZipFile(backup) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            members["data/memory_bank.json"] = b'{"items":[]}'
            damaged = backup.with_name("damaged.zip")
            with zipfile.ZipFile(damaged, "w") as archive:
                for name, data in members.items():
                    archive.writestr(name, data)
            roots_before = {path.name for path in root.iterdir()}
            with self.assertRaises(StorageError):
                app.restore_history_backup(damaged.relative_to(root).as_posix())
            with self.assertRaises(StorageError):
                app.restore_history_backup("../outside.zip")
            self.assertEqual(roots_before, {path.name for path in root.iterdir()})
            self.assertEqual(drafts.read_draft(draft.draft_id)["content"], "当前正文不能被覆盖。")


if __name__ == "__main__":
    unittest.main()
