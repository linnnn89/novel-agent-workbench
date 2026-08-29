"""Behavior tests for the classic Memory Bank window boundary."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch


def descendants(widget: tk.Misc):
    """Yield real child widgets so tests exercise the visible window surface."""
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class MemoryBankWindowBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        from novel_agent_workbench.desktop_app import WorkbenchDesktopApp

        self.projects_root = tempfile.TemporaryDirectory()
        self.app = WorkbenchDesktopApp(projects_root=Path(self.projects_root.name), repo_root=Path.cwd())
        self.app.withdraw()
        self.project_id = "memory-window-behavior"
        self.app.app.create_project(self.project_id, title="Memory Window Behavior")
        self.app.selected_project_id = self.project_id
        item = self.app.app.ensure_main_memory_item(self.project_id)
        self.app.app.set_memory_text(
            self.project_id,
            item["memory_id"],
            "基线记忆正文",
            source_chapter_ids=[],
            target_token_budget=5000,
        )

    def tearDown(self) -> None:
        self.app.destroy()
        self.projects_root.cleanup()

    def open_window(self) -> tuple[tk.Toplevel, tk.Text]:
        from novel_agent_workbench.desktop_app import APP_TITLE
        from novel_agent_workbench.memory_bank_window import open_memory_bank_window

        previous_children = set(self.app.winfo_children())
        open_memory_bank_window(self.app, self.project_id, app_title=APP_TITLE)
        self.app.update_idletasks()
        window = next(
            child
            for child in self.app.winfo_children()
            if child not in previous_children and isinstance(child, tk.Toplevel)
        )
        text_box = next(widget for widget in descendants(window) if isinstance(widget, tk.Text))
        return window, text_box

    @staticmethod
    def button(window: tk.Toplevel, text: str) -> ttk.Button:
        return next(
            widget
            for widget in descendants(window)
            if isinstance(widget, ttk.Button) and widget.cget("text") == text
        )

    def test_user_can_open_existing_memory_and_save_an_edit(self) -> None:
        window, text_box = self.open_window()

        self.assertEqual("基线记忆正文", text_box.get("1.0", "end-1c"))
        text_box.delete("1.0", tk.END)
        text_box.insert("1.0", "更新后的记忆正文")
        self.button(window, "保存记忆正文").invoke()
        self.app.update_idletasks()

        saved = self.app.app.ensure_main_memory_item(self.project_id)
        self.assertEqual("更新后的记忆正文", saved["text"])
        window.destroy()

    def test_canceling_unsaved_close_keeps_the_editable_window_open(self) -> None:
        window, text_box = self.open_window()
        text_box.delete("1.0", tk.END)
        text_box.insert("1.0", "尚未保存的修改")

        with patch("novel_agent_workbench.memory_bank_window.messagebox.askyesno", return_value=False) as confirm:
            self.button(window, "关闭").invoke()
            self.app.update_idletasks()

        self.assertEqual(1, confirm.call_count)
        self.assertEqual(1, window.winfo_exists())
        self.assertEqual("尚未保存的修改", text_box.get("1.0", "end-1c"))
        window.destroy()

    def test_desktop_compatibility_entry_opens_the_same_window(self) -> None:
        previous_children = set(self.app.winfo_children())
        self.app.show_memory_bank_window(self.project_id)
        self.app.update_idletasks()

        window = next(
            child
            for child in self.app.winfo_children()
            if child not in previous_children and isinstance(child, tk.Toplevel)
        )
        self.assertEqual("记忆银行", window.title())
        window.destroy()


class MemoryBankWindowBoundaryTests(unittest.TestCase):
    def test_import_has_no_runtime_reverse_dependency_and_legacy_helpers_remain_available(self) -> None:
        # A fresh interpreter catches cycles hidden by an already-imported desktop entry.
        script = "\n".join(
            [
                "import importlib",
                "import json",
                "import sys",
                "importlib.import_module('novel_agent_workbench.memory_bank_window')",
                "print(json.dumps({",
                "  'desktop_app': 'novel_agent_workbench.desktop_app' in sys.modules,",
                "}))",
            ]
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertFalse(json.loads(completed.stdout)["desktop_app"])

        from novel_agent_workbench import desktop_app, memory_bank_window

        self.assertIs(
            memory_bank_window.format_memory_compression_prompt,
            desktop_app.format_memory_compression_prompt,
        )
        self.assertIs(memory_bank_window.wrapped_row_positions, desktop_app.wrapped_row_positions)


if __name__ == "__main__":
    unittest.main()
