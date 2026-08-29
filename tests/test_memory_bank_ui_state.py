from __future__ import annotations

import json
import subprocess
import sys
import unittest


class MemoryBankUiStateTests(unittest.TestCase):
    def test_selection_order_labels_and_snapshot_match_editor_behavior(self) -> None:
        from novel_agent_workbench.memory_bank_ui_state import (
            checked_memory_chapter_ids,
            checked_memory_chapters_label,
            memory_chapter_row_label,
            memory_editor_snapshot,
        )

        chapters = [
            {"chapter_id": "chapter_003", "title": "转折", "committed_at": "2026-08-30T09:00:00Z"},
            {"chapter_id": "chapter_001", "title": "开端", "committed_at": "2026-08-28T09:00:00Z"},
        ]
        checked = {"chapter_001", "chapter_003", "chapter_999"}

        ordered = checked_memory_chapter_ids(chapters, checked)
        snapshot = memory_editor_snapshot(
            text="  长期记忆  ",
            include_context=True,
            target_tokens="8000",
            chapter_ids=ordered,
        )

        self.assertEqual(["chapter_003", "chapter_001"], ordered)
        self.assertTrue(memory_chapter_row_label(chapters[0], checked).startswith("✓  第 003 章"))
        self.assertEqual("第 003 章、第 001 章", checked_memory_chapters_label(ordered))
        self.assertEqual(
            {
                "text": "长期记忆",
                "include_context": True,
                "target_tokens": 8000,
                "checked_chapter_ids": ["chapter_003", "chapter_001"],
            },
            snapshot,
        )

    def test_invalid_tokens_and_unknown_chapters_fall_back_safely(self) -> None:
        from novel_agent_workbench.memory_bank import DEFAULT_MEMORY_TARGET_TOKENS
        from novel_agent_workbench.memory_bank_ui_state import (
            checked_memory_chapter_ids,
            checked_memory_chapters_label,
            memory_editor_snapshot,
        )

        self.assertEqual([], checked_memory_chapter_ids([], {"chapter_999"}))
        self.assertEqual("尚未勾选章节", checked_memory_chapters_label([]))
        long_label = checked_memory_chapters_label([f"chapter_{index:03d}" for index in range(1, 7)])
        self.assertTrue(long_label.endswith("等 6 章"))
        self.assertNotIn("第 006 章", long_label)
        self.assertEqual(
            DEFAULT_MEMORY_TARGET_TOKENS,
            memory_editor_snapshot(
                text="",
                include_context=False,
                target_tokens="not-a-number",
                chapter_ids=[],
            )["target_tokens"],
        )

    def test_state_module_import_does_not_load_tkinter(self) -> None:
        script = "\n".join(
            [
                "import importlib",
                "import json",
                "import sys",
                "importlib.import_module('novel_agent_workbench.memory_bank_ui_state')",
                "print(json.dumps({'tkinter_loaded': 'tkinter' in sys.modules}))",
            ]
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertFalse(json.loads(completed.stdout)["tkinter_loaded"])


if __name__ == "__main__":
    unittest.main()
