from __future__ import annotations

import inspect
import unittest

from novel_agent_workbench.desktop_app import (
    EDITOR_QUICK_ACTIONS,
    INSPECTOR_MIN_WIDTH,
    SAVED_SECRET_MASK,
    SIDEBAR_MIN_WIDTH,
    WorkbenchDesktopApp,
    format_provider_roles_compact,
    model_connection_form_state,
    parse_tree_node_id,
    project_placeholder_node_id,
    visible_character_count,
)


class DesktopWorkspaceHelperTests(unittest.TestCase):
    def test_visible_character_count_ignores_layout_whitespace(self) -> None:
        self.assertEqual(visible_character_count("第一章\n\n风 起 了。"), 7)

    def test_lazy_tree_placeholder_cannot_be_opened_as_project_content(self) -> None:
        node_id = project_placeholder_node_id("novel-1")
        self.assertEqual(parse_tree_node_id(node_id), ("", "", ""))

    def test_provider_summary_never_exposes_secret_fields(self) -> None:
        text = format_provider_roles_compact(
            {
                "writer": {
                    "configured": True,
                    "provider": "openai_compatible",
                    "model": "writer-model",
                    "masked_key": "SENTINEL_SECRET_VALUE",
                }
            }
        )
        self.assertIn("正文生成 · 已配置", text)
        self.assertIn("writer-model", text)
        self.assertNotIn("SENTINEL_SECRET_VALUE", text)

    def test_model_form_keeps_saved_key_masked(self) -> None:
        state = model_connection_form_state(
            {
                "provider": "openai_compatible",
                "model": "writer-model",
                "base_url": "https://example.invalid/v1",
                "api_key_ref": "project_secret.writer_openai_compatible_api_key",
            }
        )
        self.assertEqual(state["api_key_display"], SAVED_SECRET_MASK)
        self.assertNotIn("project_secret", str(state))

    def test_editor_exposes_rewrite_and_review_refine_as_quick_actions(self) -> None:
        labels = {label for _action, label in EDITOR_QUICK_ACTIONS}
        self.assertIn("重新生成（随机）", labels)
        self.assertIn("根据审稿意见精修", labels)

    def test_inspector_is_narrower_than_the_project_sidebar(self) -> None:
        self.assertLess(INSPECTOR_MIN_WIDTH, SIDEBAR_MIN_WIDTH)

    def test_model_connection_window_keeps_footer_visible(self) -> None:
        source = inspect.getsource(WorkbenchDesktopApp.configure_model_connection)

        self.assertIn('geometry="700x640"', source)
        self.assertIn("minsize=(640, 600)", source)
        self.assertIn('text="保存设置"', source)

    def test_all_windows_are_resizable_through_the_shared_factory(self) -> None:
        app_source = inspect.getsource(WorkbenchDesktopApp)
        factory_source = inspect.getsource(WorkbenchDesktopApp._secondary_window)

        self.assertEqual(app_source.count("tk.Toplevel("), 1)
        self.assertIn("window.resizable(True, True)", factory_source)
        self.assertIn("self.resizable(True, True)", app_source)


if __name__ == "__main__":
    unittest.main()
