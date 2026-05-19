from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import WorkbenchApplicationService, profile_corpus
from novel_agent_workbench.cli import main


class CorpusProfilerTest(unittest.TestCase):
    def test_profile_corpus_returns_metadata_without_chapter_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.txt"
            body = "\n".join(
                [
                    "【内容简介】",
                    "第一章 AlphaTestTitle",
                    "明河说道：“今天去训练场。”",
                    "青岚问：“真的吗？”",
                    "第二章 BetaTestTitle",
                    "明河笑道：“出发。”",
                    "普通叙述段落。",
                ]
            )
            path.write_bytes(body.encode("gb18030"))

            result = profile_corpus(path, max_name_candidates=5).to_dict()
            result_text = json.dumps(result, ensure_ascii=False)

            self.assertEqual(result["encoding"]["detected"], "gb18030")
            self.assertEqual(result["structure"]["strict_chapter_heading_count"], 2)
            self.assertEqual(result["chapter_stats"]["count"], 2)
            self.assertGreater(result["dialogue_proxy"]["dialogue_like_line_count"], 0)
            self.assertFalse(result["structure"]["heading_text_included"])
            self.assertFalse(result["safety"]["source_text_copied"])
            self.assertFalse(result["safety"]["provider_called"])
            self.assertFalse(result["safety"]["writes_project_files"])
            self.assertNotIn("AlphaTestTitle", result_text)
            self.assertNotIn("今天去训练场", result_text)

    def test_profile_corpus_facade_and_cli_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sample.txt"
            body = "\n".join(
                [
                    "第一章 Opening",
                    "Alice说道：“hello。”",
                    "第二章 Next",
                    "Alice问：“go?”",
                ]
            )
            path.write_text(body, encoding="utf-8")
            app = WorkbenchApplicationService.open(Path(temp) / "projects")

            facade = app.profile_corpus(path, max_name_candidates=3)
            code, stdout, stderr = run_cli(["--projects-root", str(Path(temp) / "projects"), "profile-corpus", str(path)])

            self.assertEqual(facade["encoding"]["detected"], "utf-8")
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["result"]["structure"]["strict_chapter_heading_count"], 2)
            self.assertNotIn("hello", stdout)
            self.assertNotIn("Opening", stdout)
            self.assertFalse((Path(temp) / "projects").exists())


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
