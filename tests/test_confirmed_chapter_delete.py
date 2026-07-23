from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.chapters import ChapterWorkflowError
from novel_agent_workbench.desktop_app import WorkbenchDesktopApp
from novel_agent_workbench.drafts import DraftGenerationError


class ConfirmedChapterDeleteTests(unittest.TestCase):
    def test_delete_confirmed_chapter_removes_entire_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_root = Path(temp_dir) / "projects"
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("novel_a", title="Novel A")
            project_root = projects_root / "novel_a"
            data_dir = project_root / "data"
            drafts_dir = data_dir / "drafts"
            confirmed_dir = data_dir / "confirmed_chapters"
            drafts_dir.mkdir(parents=True, exist_ok=True)
            confirmed_dir.mkdir(parents=True, exist_ok=True)

            draft_path = drafts_dir / "chapter_001__ver1__draft_a.json"
            draft_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "committed",
                        "draft_id": "draft_a",
                        "chapter_id": "chapter_001",
                        "title": "开端",
                        "version": 1,
                        "version_label": "ver1",
                        "created_at": "20260601T000000000000Z",
                        "committed_at": "20260601T000001000000Z",
                        "committed_chapter_id": "chapter_001",
                        "content": "定稿正文",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "drafts_index.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "drafts": [
                            {
                                "draft_id": "draft_a",
                                "chapter_id": "chapter_001",
                                "title": "开端",
                                "created_at": "20260601T000000000000Z",
                                "status": "committed",
                                "version": 1,
                                "version_label": "ver1",
                                "path": "data/drafts/chapter_001__ver1__draft_a.json",
                                "committed_at": "20260601T000001000000Z",
                                "committed_chapter_id": "chapter_001",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            confirmed_path = confirmed_dir / "chapter_001.json"
            confirmed_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "chapter_id": "chapter_001",
                        "title": "开端",
                        "source_draft_id": "draft_a",
                        "committed_at": "20260601T000001000000Z",
                        "content": "定稿正文",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "confirmed_chapters.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "chapters": [
                            {
                                "chapter_id": "chapter_001",
                                "title": "开端",
                                "source_draft_id": "draft_a",
                                "committed_at": "20260601T000001000000Z",
                                "path": "data/confirmed_chapters/chapter_001.json",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "chapters_workflow.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "chapters": [
                            {
                                "chapter_id": "chapter_001",
                                "title": "开端",
                                "status": "committed",
                                "created_at": "20260601T000000000000Z",
                                "updated_at": "20260601T000001000000Z",
                                "latest_draft_id": "draft_a",
                                "confirmed_chapter_id": "chapter_001",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = app.delete_confirmed_chapter("novel_a", "chapter_001")

            self.assertTrue(result["deleted"])
            self.assertEqual(result["source_draft_id"], "draft_a")
            self.assertEqual(result["deleted_draft_ids"], ["draft_a"])
            self.assertEqual(app.list_confirmed_chapters("novel_a"), [])
            with self.assertRaises(DraftGenerationError):
                app.read_confirmed_chapter("novel_a", "chapter_001")
            self.assertFalse(confirmed_path.exists())
            self.assertTrue(list(confirmed_dir.glob("chapter_001.json.*.trash")))

            self.assertEqual(app.list_drafts("novel_a"), [])
            with self.assertRaises(DraftGenerationError):
                app.read_draft("novel_a", "draft_a")
            self.assertFalse(draft_path.exists())
            self.assertTrue(list(drafts_dir.glob("chapter_001__ver1__draft_a.json.*.trash")))

            with self.assertRaises(ChapterWorkflowError):
                app.chapter_status("novel_a", "chapter_001")

            commit_log = json.loads((data_dir / "commit_log.json").read_text(encoding="utf-8"))
            self.assertEqual(commit_log["commits"][-1]["status"], "confirmed_deleted")
            self.assertEqual(commit_log["commits"][-1]["deleted_draft_count"], 1)

    def test_ui_exposes_separate_confirmed_delete_action(self) -> None:
        menu_source = inspect.getsource(WorkbenchDesktopApp.show_project_context_menu)
        self.assertIn("删除已确认章节", menu_source)
        self.assertIn("delete_confirmed_chapter_dialog", menu_source)

        dialog_source = inspect.getsource(WorkbenchDesktopApp.delete_confirmed_chapter_dialog)
        self.assertIn("确认删除定稿", dialog_source)
        self.assertIn("删除整个章节", dialog_source)
        self.assertIn("delete_confirmed_chapter", dialog_source)


if __name__ == "__main__":
    unittest.main()
