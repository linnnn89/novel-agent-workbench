from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
import unittest


class ClassicUiThemeTests(unittest.TestCase):
    def test_theme_applies_core_colors_and_styles(self) -> None:
        from novel_agent_workbench.classic_ui_theme import PALETTE, configure_classic_theme

        root = tk.Tk()
        root.withdraw()
        try:
            style = configure_classic_theme(root)

            self.assertEqual(PALETTE["app_bg"], root.cget("background"))
            self.assertEqual(PALETTE["accent"], style.lookup("Primary.TButton", "background"))
            self.assertEqual(PALETTE["success"], style.lookup("Confirm.TButton", "background"))
            self.assertEqual("32", str(style.lookup("Treeview", "rowheight")))
        finally:
            root.destroy()

    def test_theme_import_does_not_load_desktop_entry(self) -> None:
        # Theme configuration is a one-way classic-UI dependency, not an app-service entry point.
        script = "\n".join(
            [
                "import importlib",
                "import json",
                "import sys",
                "importlib.import_module('novel_agent_workbench.classic_ui_theme')",
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
        result = json.loads(completed.stdout)

        self.assertFalse(result["desktop_app"])

    def test_classic_entry_reexports_theme_tokens(self) -> None:
        from novel_agent_workbench import classic_ui_theme, desktop_app

        self.assertIs(classic_ui_theme.PALETTE, desktop_app.PALETTE)
        self.assertIs(classic_ui_theme.FONT_BASE, desktop_app.FONT_BASE)


if __name__ == "__main__":
    unittest.main()
