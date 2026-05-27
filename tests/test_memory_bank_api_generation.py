from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.desktop_app import format_memory_generation_manual_prompt
from novel_agent_workbench.memory_bank import memory_auto_summary_candidate


class MemoryBankApiGenerationTests(unittest.TestCase):
    def test_auto_summary_candidate_batches_five_unsummarized_chapters(self) -> None:
        chapters = [{"chapter_id": f"chapter_{number:03d}", "title": f"Chapter {number}"} for number in range(1, 11)]

        waiting = memory_auto_summary_candidate({"text": "", "last_updated_chapter_number": 0}, chapters[:4])
        self.assertFalse(waiting["ready"])
        self.assertEqual(waiting["reason"], "waiting_for_batch")

        first_batch = memory_auto_summary_candidate({"text": "", "last_updated_chapter_number": 0}, chapters)
        self.assertTrue(first_batch["ready"])
        self.assertEqual(first_batch["source_chapter_ids"], [f"chapter_{number:03d}" for number in range(1, 6)])
        self.assertEqual(first_batch["remaining_after_batch"], 5)

        second_batch = memory_auto_summary_candidate({"text": "已有记忆", "last_updated_chapter_number": 5}, chapters)
        self.assertTrue(second_batch["ready"])
        self.assertEqual(second_batch["source_chapter_ids"], [f"chapter_{number:03d}" for number in range(6, 11)])

        progress_missing = memory_auto_summary_candidate({"text": "已有记忆"}, chapters)
        self.assertFalse(progress_missing["ready"])
        self.assertEqual(progress_missing["reason"], "manual_progress_missing")

    def test_application_auto_summary_candidate_reads_confirmed_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_root = Path(temp_dir) / "projects"
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("novel_a", title="Novel A")
            confirmed_path = projects_root / "novel_a" / "data" / "confirmed_chapters.json"
            confirmed_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "chapters": [
                            {"chapter_id": f"chapter_{number:03d}", "title": f"Chapter {number}"}
                            for number in range(1, 6)
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            candidate = app.memory_auto_summary_candidate("novel_a")
            self.assertTrue(candidate["ready"])
            self.assertEqual(candidate["source_chapter_ids"], [f"chapter_{number:03d}" for number in range(1, 6)])

    def test_preview_and_mock_generation_are_structured_and_not_auto_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = WorkbenchApplicationService.open(Path(temp_dir) / "projects")
            app.create_project("novel_a", title="Novel A")
            app.configure_mock_writer("novel_a", model="mock-writer")
            app.ensure_main_memory_item("novel_a")
            chapters = [
                {
                    "chapter_id": "chapter_001",
                    "title": "开端",
                    "content": "林澈在雨夜发现旧钥匙，确认父亲失踪和北塔有关。",
                }
            ]

            preview = app.preview_memory_generation_request(
                "novel_a",
                current_memory="",
                chapters=chapters,
                target_token_budget=800,
            )
            self.assertEqual(preview["provider_request_role"], "writer")
            self.assertEqual(preview["logical_role"], "writer")
            self.assertEqual(preview["sampling"]["temperature"], 0.2)
            self.assertEqual(preview["sampling"]["top_p"], 1.0)
            self.assertEqual(preview["sampling"]["max_tokens"], 8000)
            self.assertTrue(preview["sampling"]["stream"])
            self.assertIn("长期记忆维护助手", preview["messages"][0]["content"])
            self.assertIn("后续创作", preview["messages"][0]["content"])
            self.assertIn("<<<CHAPTER 1", preview["messages"][1]["content"])
            self.assertIn("旧钥匙", preview["messages"][1]["content"])
            self.assertIn("更新原则：", preview["messages"][1]["content"])
            self.assertIn("应优先记录：", preview["messages"][1]["content"])
            self.assertIn("压缩原则：", preview["messages"][1]["content"])
            self.assertIn("输出要求：", preview["messages"][1]["content"])
            self.assertIn("不要逐章流水账", preview["messages"][1]["content"])
            self.assertTrue(preview["metadata"]["memory_bank_generation"])
            manual_prompt = format_memory_generation_manual_prompt(preview)
            self.assertIn(preview["messages"][0]["content"], manual_prompt)
            self.assertIn(preview["messages"][1]["content"], manual_prompt)

            streamed_chunks: list[str] = []
            result = app.generate_memory_bank_text(
                "novel_a",
                current_memory="",
                chapters=chapters,
                target_token_budget=800,
                stream_callback=streamed_chunks.append,
            )
            self.assertEqual(result["provider"], "mock")
            self.assertIn("MOCK writer draft placeholder", result["text"])
            self.assertIn("MOCK writer draft placeholder", "".join(streamed_chunks))
            self.assertEqual(result["request_summary"]["provider_request_role"], "writer")
            self.assertEqual(result["request_summary"]["source_chapter_ids"], ["chapter_001"])
            self.assertEqual(result["request_summary"]["request_max_tokens"], 8000)
            self.assertTrue(result["request_summary"]["stream"])

            memory_item = app.read_memory_item("novel_a", "main_memory_bank", include_text=True)
            self.assertEqual(memory_item["text"], "")

            provider_log = Path(temp_dir) / "projects" / "novel_a" / "data" / "provider_call_log.json"
            log_text = provider_log.read_text(encoding="utf-8")
            log_data = json.loads(log_text)
            self.assertTrue(log_data)
            self.assertIn("memory_bank_generation", log_text)
            self.assertNotIn("旧钥匙", log_text)
            self.assertNotIn("林澈", log_text)


if __name__ == "__main__":
    unittest.main()
