from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from novel_agent_workbench.desktop_app import WorkbenchDesktopApp, format_draft_regeneration_prompt


class DraftRegenerationPromptTests(unittest.TestCase):
    def test_regeneration_prompt_does_not_include_previous_draft_text(self) -> None:
        prompt = format_draft_regeneration_prompt(
            chapter_id="chapter_004",
            title="常伪佛昨晚那个",
            instruction="加强动作张力。",
            default_prompt="保持中文网文叙事节奏。",
        )

        self.assertIn("当作尚未写过", prompt)
        self.assertIn("重新生成一个全新草稿", prompt)
        self.assertIn("chapter_004", prompt)
        self.assertIn("保持中文网文叙事节奏", prompt)
        self.assertIn("加强动作张力", prompt)
        self.assertIn("不要参考上一版正文", prompt)
        self.assertNotIn("【上一版稿件】", prompt)
        self.assertNotIn("旧钥匙", prompt)

    def test_desktop_rewrite_uses_regeneration_prompt_without_source_body(self) -> None:
        source = inspect.getsource(WorkbenchDesktopApp.rewrite_current_draft)

        self.assertIn("format_draft_regeneration_prompt", source)
        self.assertIn("previous_draft_body_excluded", source)
        self.assertIn("desktop_regenerate_chapter", source)
        self.assertNotIn("【上一版稿件】", source)
        self.assertNotIn("source_text", source)


if __name__ == "__main__":
    unittest.main()
