"""Pending chapter inputs survive bridge restarts and unsuccessful requests."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.modern_desktop import WorkbenchBridge


class ChapterInputCacheTest(unittest.TestCase):
    def test_cache_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def bridge():
                return WorkbenchBridge(projects_root=root / "projects", repo_root=root,
                                       settings_path=root / "settings.json")
            api = bridge()
            api.app.create_project("test", title="缓存测试")
            def save(chapter="chapter_001", title="标题", prompt="未提交内容", restore=False):
                result = api.chapter_input("test", chapter, title, prompt, str(root / "projects"), restore)
                self.assertTrue(result["ok"], result)
                return result["data"]
            original = save()
            api = bridge()
            self.assertEqual(save(title="", prompt="默认", restore=True), original)
            with patch.object(api, "_run_job", side_effect=lambda name, worker, **kw: worker()), \
                 patch.object(api, "_stream_hooks", return_value=(None, None, lambda: None)), \
                 patch.object(type(api.app), "generate_context_draft") as generate:
                generate.side_effect = RuntimeError("模拟请求失败")
                with self.assertRaisesRegex(RuntimeError, "模拟请求失败"):
                    api.generate_draft("test", "chapter_001", "标题", "未提交内容")
                self.assertEqual(save(restore=True), original)
                generate.side_effect = None
                generate.return_value = {"output_incomplete": True}
                api.generate_draft("test", "chapter_001", "标题", "未提交内容")
                self.assertEqual(save(restore=True), original)
                generate.return_value = {"output_incomplete": False}
                api.generate_draft("test", "chapter_001", "标题", "未提交内容")
                self.assertEqual(save(title="", prompt="默认", restore=True)["prompt"], "默认")
            save()
            self.assertEqual(save("chapter_002", "", "下一章默认", True),
                             {"chapter_id": "chapter_002", "title": "", "prompt": "下一章默认"})


if __name__ == "__main__":
    unittest.main()
