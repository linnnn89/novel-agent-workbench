from __future__ import annotations

import unittest

from novel_agent_workbench.modern_desktop import WindowCloseSaveCoordinator


class FakeWindow:
    def __init__(self) -> None:
        self.callback = None
        self.destroy_count = 0
        self.evaluated_scripts: list[str] = []

    def evaluate_js(self, script: str, callback=None) -> None:
        self.evaluated_scripts.append(script)
        self.callback = callback

    def destroy(self) -> None:
        self.destroy_count += 1

    def run_js(self, _script: str) -> None:
        return None


class WindowCloseSaveCoordinatorTests(unittest.TestCase):
    def test_window_closes_only_after_final_save_succeeds(self) -> None:
        window = FakeWindow()
        coordinator = WindowCloseSaveCoordinator(window)

        self.assertFalse(coordinator.on_closing())
        self.assertFalse(coordinator.on_closing())
        self.assertEqual(0, window.destroy_count)
        self.assertIsNotNone(window.callback)

        window.callback({"ok": True})

        self.assertEqual(1, window.destroy_count)
        self.assertTrue(coordinator.on_closing())

    def test_failed_final_save_keeps_window_open_and_allows_retry(self) -> None:
        window = FakeWindow()
        coordinator = WindowCloseSaveCoordinator(window)

        self.assertFalse(coordinator.on_closing())
        window.callback({"ok": False, "error": "disk full"})

        self.assertEqual(0, window.destroy_count)
        self.assertFalse(coordinator.on_closing())
        self.assertEqual(2, len(window.evaluated_scripts))


if __name__ == "__main__":
    unittest.main()
