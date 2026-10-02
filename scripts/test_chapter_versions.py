"""Chapter defaults and single-version deletion use real isolated project files."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge


class ChapterVersionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.api = WorkbenchBridge(projects_root=root / "projects", repo_root=root,
                                   settings_path=root / "settings.json")
        self.api.app.create_project("test", title="章节隔离测试")
        self.store = self.api.app._open_store("test")
        self.drafts = DraftGenerationService(self.store)

    def draft(self, chapter="chapter_006", content="正文"):
        return self.drafts.save_provider_draft_version(
            chapter_id=chapter, title="测试章节", content=content,
            provider_role="writer", provider="mock", model="mock")

    def test_confirmed_chapter_does_not_restore_old_pending_id(self):
        draft = self.draft()
        original = {"chapter_id": "chapter_006", "title": "缓存标题", "prompt": "待提交要求"}
        self.store.write_json(self.store.data_dir / "pending_chapter_input.json", original)
        self.assertEqual(self.api.suggest_chapter("test")["data"]["chapter_id"], "chapter_006")
        self.assertTrue(self.api.confirm_draft("test", draft.draft_id)["ok"])
        self.assertEqual(self.api.suggest_chapter("test")["data"]["chapter_id"], "chapter_007")
        restored = self.api.chapter_input("test", "chapter_007", "", "新章默认",
                                         str(self.api.projects_root), True)
        self.assertEqual(restored["data"], {"chapter_id": "chapter_007", "title": "", "prompt": "新章默认"})
        # A restart must retain unfinished next-chapter input as before.
        restarted = WorkbenchBridge(projects_root=self.api.projects_root, repo_root=self.api.repo_root,
                                    settings_path=Path(self.temp.name) / "settings.json")
        self.assertEqual(restarted.suggest_chapter("test")["data"]["chapter_id"], "chapter_007")

    def test_delete_one_version_preserves_siblings_confirmed_and_related_files(self):
        first, second, third = self.draft(content="版本一"), self.draft(content="版本二"), self.draft(content="版本三")
        other = self.draft("chapter_007", "其他章节")
        self.assertTrue(self.api.confirm_draft("test", first.draft_id)["ok"])
        # Only exact draft links may be retired; chapter-only entries and siblings stay.
        for name, key, id_key in [("reviews_index.json", "reviews", "review_id"),
                                   ("revision_requests_index.json", "revision_requests", "revision_request_id")]:
            entries = []
            for label, draft_id in [("first", first.draft_id), ("second", second.draft_id),
                                    ("third", third.draft_id), ("legacy", "")]:
                path = self.store.data_dir / f"{key}_{label}.json"
                self.store.write_json(path, {"test": label})
                entries.append({id_key: label, "chapter_id": "chapter_006", "draft_id": draft_id,
                                "path": str(path)})
            self.store.write_json(self.store.data_dir / name, {"schema_version": 1, key: entries})
        result = self.api.delete_draft("test", second.draft_id)
        self.assertTrue(result["ok"], result)
        data = result["data"]["result"]
        self.assertEqual(data["deleted_draft_ids"], [second.draft_id])
        self.assertTrue(data["checkpoint"])
        self.assertTrue(all(Path(path).is_file() for path in data["retired_paths"]))
        self.assertEqual({d["draft_id"] for d in self.api.app.list_drafts("test")},
                         {first.draft_id, third.draft_id, other.draft_id})
        self.assertEqual([d["version_label"] for d in self.api.app.list_drafts("test")
                          if d["chapter_id"] == "chapter_006"], ["ver1", "ver3"])
        for name, key in [("reviews_index.json", "reviews"), ("revision_requests_index.json", "revision_requests")]:
            kept = self.store.read_json(self.store.data_dir / name)[key]
            self.assertEqual([d["draft_id"] for d in kept], [first.draft_id, third.draft_id, ""])
            self.assertTrue(all(Path(d["path"]).exists() for d in kept))
        before = self.api.app.read_confirmed_chapter("test", "chapter_006")
        protected = self.api.delete_draft("test", first.draft_id)
        self.assertFalse(protected["ok"], protected)
        self.assertEqual(self.api.app.read_confirmed_chapter("test", "chapter_006"), before)
        # Latest-version removal repairs workflow; deleting the last unconfirmed version removes its row.
        self.assertTrue(self.api.delete_draft("test", third.draft_id)["ok"])
        chapter = self.api.app.chapter_status("test", "chapter_006")
        self.assertEqual(chapter["latest_draft_id"], first.draft_id)
        self.assertEqual(chapter["status"], "committed")
        self.api._busy = True
        self.assertFalse(self.api.delete_draft("test", other.draft_id)["ok"])
        self.api._busy = False
        self.assertTrue(self.api.delete_draft("test", other.draft_id)["ok"])
        self.assertNotIn("chapter_007", [c["chapter_id"] for c in self.api.app.list_chapters("test")])


if __name__ == "__main__":
    unittest.main()
