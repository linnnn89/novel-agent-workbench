from __future__ import annotations

import json
import subprocess
import sys
import unittest


class UiImportBoundaryTests(unittest.TestCase):
    def test_modern_desktop_import_does_not_load_tkinter(self) -> None:
        # Run in a fresh interpreter so earlier test imports cannot hide Tk coupling.
        script = "\n".join(
            [
                "import importlib",
                "import json",
                "import sys",
                "importlib.import_module('novel_agent_workbench.modern_desktop')",
                "print(json.dumps({'tkinter_loaded': 'tkinter' in sys.modules}))",
            ]
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)

        self.assertFalse(result["tkinter_loaded"])

    def test_classic_entry_reexports_shared_presenters(self) -> None:
        from novel_agent_workbench import desktop_app, ui_presenters

        # Existing callers keep their imports while both front ends share one implementation.
        shared_names = (
            "default_planning_id",
            "default_projects_root",
            "default_repo_root",
            "draft_status_label",
            "draft_version_text",
            "estimate_memory_text_tokens",
            "format_auto_memory_summary_confirmation",
            "format_context_package_preview",
            "format_diagnostic_details",
            "format_draft_regeneration_prompt",
            "format_memory_generation_manual_prompt",
            "format_memory_generation_request_preview",
            "format_project_summary",
            "format_prompt_preview",
            "format_provider_summary",
            "format_record_sections",
            "format_review_details",
            "latest_draft_title",
            "memory_progress_label",
            "memory_token_advice",
            "optional_float",
            "optional_int",
            "parse_optional_float",
            "parse_optional_int",
            "readable_chapter_label",
            "recommended_memory_chapter_ids",
            "sorted_draft_versions",
            "suggest_next_chapter_id",
            "visible_chapter_record_rows",
        )
        for name in shared_names:
            with self.subTest(name=name):
                self.assertIs(getattr(desktop_app, name), getattr(ui_presenters, name))


if __name__ == "__main__":
    unittest.main()
