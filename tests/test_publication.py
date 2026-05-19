from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import WorkbenchApplicationService, prepublish_check
from novel_agent_workbench.cli import main
from novel_agent_workbench.publication import REQUIRED_GITIGNORE_PATTERNS


class PublicationTest(unittest.TestCase):
    def test_prepublish_check_passes_clean_repo_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_gitignore(root)
            (root / "src").mkdir()
            (root / "src" / "safe.py").write_text("print('ok')\n", encoding="utf-8")

            result = prepublish_check(root, projects_root=root / "workspace_projects")

            self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False))

    def test_prepublish_check_fails_missing_gitignore_pattern_and_secret_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".gitignore").write_text("workspace_projects/\n", encoding="utf-8")
            (root / "secrets.local.json").write_text("{}", encoding="utf-8")

            result = prepublish_check(root, projects_root=root / "workspace_projects")
            codes = {finding["code"] for finding in result["findings"]}

            self.assertFalse(result["ok"])
            self.assertIn("gitignore_required_pattern_missing", codes)
            self.assertIn("repo_secret_file_present", codes)

    def test_prepublish_check_fails_runtime_corpus_sample_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_gitignore(root)
            projects_root = root / "workspace_projects"
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("demo")
            source = root / "source.txt"
            source.write_text("第一章 PublishAlpha\n明河说道：“发布前必须清理。”", encoding="utf-8")
            boundary = app.save_corpus_boundaries("demo", source)
            app.create_corpus_sample("demo", boundary["boundary_id"], source, ordinal=1, max_chars=10)

            result = prepublish_check(root, projects_root=projects_root)
            codes = {finding["code"] for finding in result["findings"]}
            result_text = json.dumps(result, ensure_ascii=False)

            self.assertFalse(result["ok"])
            self.assertIn("runtime_corpus_sample_present", codes)
            self.assertIn("project_audit_non_publishable_corpus_sample_present", codes)
            self.assertNotIn("发布前必须清理", result_text)

    def test_cli_prepublish_check_uses_projects_root_and_redacts_sample_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_gitignore(root)
            projects_root = root / "workspace_projects"
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("demo")
            source = root / "source.txt"
            source.write_text("第一章 CliPublishAlpha\n明河说道：“CLI发布前清理。”", encoding="utf-8")
            boundary = app.save_corpus_boundaries("demo", source)
            app.create_corpus_sample("demo", boundary["boundary_id"], source, ordinal=1, max_chars=10)

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    str(projects_root),
                    "prepublish-check",
                    "--repo-root",
                    str(root),
                ]
            )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertFalse(payload["result"]["ok"])
            self.assertNotIn("CLI发布前清理", stdout)


def write_gitignore(root: Path) -> None:
    root.joinpath(".gitignore").write_text("\n".join(REQUIRED_GITIGNORE_PATTERNS) + "\n", encoding="utf-8")


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
