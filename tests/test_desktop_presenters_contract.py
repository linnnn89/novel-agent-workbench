from __future__ import annotations

import unittest

from novel_agent_workbench.desktop_app import (
    draft_version_text,
    estimate_memory_text_tokens,
    latest_draft_title,
    memory_progress_label,
    optional_float,
    optional_int,
    parse_optional_float,
    parse_optional_int,
    readable_chapter_label,
    recommended_memory_chapter_ids,
    sorted_draft_versions,
    suggest_next_chapter_id,
    visible_chapter_record_rows,
)


class DesktopPresenterContractTests(unittest.TestCase):
    """Characterize UI-facing values before moving their implementation."""

    def test_chapter_and_draft_presenters_keep_current_labels_and_order(self) -> None:
        drafts = [
            {"version": 2, "title": "Second", "created_at": "2026-01-02"},
            {"version": 1, "title": "First", "created_at": "2026-01-01"},
        ]

        ordered = sorted_draft_versions(drafts)

        self.assertEqual([1, 2], [item["version"] for item in ordered])
        self.assertEqual("Second", latest_draft_title(ordered))
        self.assertEqual("ver2", draft_version_text(ordered[-1]))
        self.assertEqual("第 007 章", readable_chapter_label("chapter_007"))

    def test_confirmed_and_planned_chapters_remain_visible(self) -> None:
        chapters = [
            {"chapter_id": "chapter_001", "status": "confirmed"},
            {"chapter_id": "chapter_002", "status": "planned"},
            {"chapter_id": "chapter_003", "status": "unused"},
        ]

        rows = visible_chapter_record_rows(
            chapters,
            drafts=[],
            confirmed=[{"chapter_id": "chapter_001"}],
        )

        self.assertEqual(["chapter_001", "chapter_002"], [row["chapter_id"] for row in rows])

    def test_memory_progress_recommends_only_unprocessed_confirmed_chapters(self) -> None:
        memory = {
            "text": "已有记忆",
            "last_updated_chapter_id": "chapter_002",
            "last_updated_chapter_number": 2,
        }
        chapters = [
            {"chapter_id": "chapter_001"},
            {"chapter_id": "chapter_003"},
            {"chapter_id": "chapter_004"},
        ]

        self.assertEqual(["chapter_003", "chapter_004"], recommended_memory_chapter_ids(memory, chapters))
        self.assertIn("第 003 章开始", memory_progress_label(memory, chapters))
        self.assertGreater(estimate_memory_text_tokens("中文 and English"), 0)

    def test_empty_or_invalid_numeric_inputs_keep_safe_boundaries(self) -> None:
        self.assertIsNone(parse_optional_int("", "数量"))
        self.assertEqual(12, parse_optional_int("12", "数量"))
        self.assertEqual(0.25, parse_optional_float("0.25", "温度"))
        self.assertIsNone(optional_int(True))
        self.assertIsNone(optional_float(False))

        with self.assertRaisesRegex(ValueError, "数量 必须是整数"):
            parse_optional_int("1.5", "数量")
        with self.assertRaisesRegex(ValueError, "温度 不能小于 0"):
            parse_optional_float("-0.1", "温度")

    def test_next_chapter_reuses_an_empty_retriable_slot(self) -> None:
        chapters = [
            {"chapter_id": "chapter_001", "status": "confirmed", "confirmed_chapter_id": "confirmed_1"},
            {"chapter_id": "chapter_002", "status": "blocked", "latest_draft_id": ""},
            {"chapter_id": "chapter_003", "status": "confirmed", "confirmed_chapter_id": "confirmed_3"},
        ]

        self.assertEqual("chapter_002", suggest_next_chapter_id(chapters))


if __name__ == "__main__":
    unittest.main()
