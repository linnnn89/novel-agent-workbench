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
from novel_agent_workbench.desktop_app import WorkbenchDesktopApp
from novel_agent_workbench.planning_library import PlanningLibraryError


class PlanningLibraryRecordsTests(unittest.TestCase):
    def test_delete_planning_item_removes_character_and_active_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_root = Path(temp_dir) / "projects"
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("novel_a", title="Novel A")
            app.create_planning_item(
                "novel_a",
                "character_plan_hero",
                text="主角林澈，目标是调查北塔。",
                title="林澈",
                item_type="character_plan",
                active=True,
                enabled=True,
            )
            app.create_planning_item(
                "novel_a",
                "world_plan_main",
                text="北塔会影响城市记忆。",
                title="北塔规则",
                item_type="world_plan",
                active=True,
                enabled=True,
            )

            deleted = app.delete_planning_item("novel_a", "character_plan_hero")

            self.assertEqual(deleted["planning_id"], "character_plan_hero")
            items = app.list_planning_items("novel_a", include_text=True)
            self.assertEqual([item["planning_id"] for item in items], ["world_plan_main"])
            with self.assertRaises(PlanningLibraryError):
                app.read_planning_item("novel_a", "character_plan_hero", include_text=True)

            library_path = projects_root / "novel_a" / "data" / "planning_library.json"
            library = json.loads(library_path.read_text(encoding="utf-8"))
            self.assertEqual(library["active_reference_ids"], ["world_plan_main"])

    def test_world_materials_ui_exposes_per_item_edit_delete_and_project_menu_entry(self) -> None:
        records_source = inspect.getsource(WorkbenchDesktopApp.show_planning_records_window)
        self.assertIn("编辑选中", records_source)
        self.assertIn("删除选中", records_source)
        self.assertIn("selected_planning_id", records_source)
        self.assertIn("delete_planning_item", records_source)

        dialog_source = inspect.getsource(WorkbenchDesktopApp.create_planning_item_dialog)
        self.assertIn("existing_item", dialog_source)

        menu_source = inspect.getsource(WorkbenchDesktopApp.show_project_context_menu)
        self.assertIn("世界观与人物", menu_source)
        self.assertIn("self.show_world_materials", menu_source)


if __name__ == "__main__":
    unittest.main()
