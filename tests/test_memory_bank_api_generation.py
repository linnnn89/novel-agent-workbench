from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_agent_workbench.application_service import WorkbenchApplicationService


class MemoryBankApiGenerationTests(unittest.TestCase):
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
            self.assertGreater(preview["sampling"]["max_tokens"], 800)
            self.assertIn("长期记忆整理助手", preview["messages"][0]["content"])
            self.assertIn("<<<CHAPTER 1", preview["messages"][1]["content"])
            self.assertIn("旧钥匙", preview["messages"][1]["content"])
            self.assertTrue(preview["metadata"]["memory_bank_generation"])

            result = app.generate_memory_bank_text(
                "novel_a",
                current_memory="",
                chapters=chapters,
                target_token_budget=800,
            )
            self.assertEqual(result["provider"], "mock")
            self.assertIn("MOCK writer draft placeholder", result["text"])
            self.assertEqual(result["request_summary"]["provider_request_role"], "writer")
            self.assertEqual(result["request_summary"]["source_chapter_ids"], ["chapter_001"])

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
