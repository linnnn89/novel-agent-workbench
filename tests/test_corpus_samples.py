from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import CorpusSampleError, WorkbenchApplicationService
from novel_agent_workbench.cli import main


class CorpusSampleTest(unittest.TestCase):
    def test_create_corpus_sample_is_test_only_publish_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp) / "projects")
            app.create_project("demo")
            source = Path(temp) / "source.txt"
            body = "\n".join(
                [
                    "第一章 SampleAlphaTitle",
                    "明河说道：“测试样本文本第一段。”",
                    "普通叙述段落。",
                    "第二章 SampleBetaTitle",
                    "青岚问：“测试样本文本第二段。”",
                ]
            )
            source.write_text(body, encoding="utf-8")
            boundary = app.save_corpus_boundaries("demo", source)

            sample = app.create_corpus_sample("demo", boundary["boundary_id"], source, ordinal=1, max_chars=12)
            samples = app.list_corpus_samples("demo")
            redacted = app.read_corpus_sample("demo", sample["sample_id"])
            with_text = app.read_corpus_sample("demo", sample["sample_id"], include_text=True)
            state = app.project_state("demo")
            audit = app.audit_project("demo")
            result_text = json.dumps({"sample": sample, "samples": samples, "redacted": redacted, "state": state}, ensure_ascii=False)

            self.assertEqual(sample["status"], "sample_ready")
            self.assertTrue(sample["publish_blocker"])
            self.assertEqual(len(samples), 1)
            self.assertNotIn("sample_text", redacted)
            self.assertIn("sample_text", with_text)
            self.assertLessEqual(len(with_text["sample_text"]), 12)
            self.assertEqual(state["corpus_sample_count"], 1)
            self.assertEqual(state["latest_corpus_sample"]["sample_id"], sample["sample_id"])
            self.assertFalse(audit["ok"])
            self.assertIn("non_publishable_corpus_sample_present", {finding["code"] for finding in audit["findings"]})
            self.assertNotIn("测试样本文本", result_text)
            self.assertNotIn(str(source), result_text)

    def test_corpus_sample_rejects_hash_mismatch_and_oversize(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp) / "projects")
            app.create_project("demo")
            source = Path(temp) / "source.txt"
            source.write_text("第一章 HashAlpha\n明河说道：“原文。”", encoding="utf-8")
            other = Path(temp) / "other.txt"
            other.write_text("第一章 HashAlpha\n明河说道：“不同文本。”", encoding="utf-8")
            boundary = app.save_corpus_boundaries("demo", source)

            with self.assertRaises(CorpusSampleError):
                app.create_corpus_sample("demo", boundary["boundary_id"], other, ordinal=1, max_chars=20)
            with self.assertRaises(CorpusSampleError):
                app.create_corpus_sample("demo", boundary["boundary_id"], source, ordinal=1, max_chars=2001)

            self.assertEqual(app.list_corpus_samples("demo"), [])

    def test_cli_corpus_sample_redacts_text_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects_root = Path(temp) / "projects"
            source = Path(temp) / "source.txt"
            source.write_text(
                "第一章 CliSampleAlpha\n明河说道：“CLI测试样本文本。”\n第二章 CliSampleBeta\n普通叙述。",
                encoding="utf-8",
            )
            create_code, _, create_err = run_cli(["--projects-root", str(projects_root), "create-project", "demo"])
            boundary_code, boundary_out, boundary_err = run_cli(
                ["--projects-root", str(projects_root), "save-corpus-boundaries", "demo", str(source)]
            )
            boundary_id = json.loads(boundary_out)["result"]["boundary_id"]
            sample_code, sample_out, sample_err = run_cli(
                [
                    "--projects-root",
                    str(projects_root),
                    "create-corpus-sample",
                    "demo",
                    boundary_id,
                    str(source),
                    "--ordinal",
                    "1",
                    "--max-chars",
                    "10",
                ]
            )
            sample_id = json.loads(sample_out)["result"]["sample_id"]
            read_code, read_out, read_err = run_cli(
                ["--projects-root", str(projects_root), "read-corpus-sample", "demo", sample_id]
            )
            read_text_code, read_text_out, read_text_err = run_cli(
                ["--projects-root", str(projects_root), "read-corpus-sample", "demo", sample_id, "--include-text"]
            )

            self.assertEqual(create_code, 0, create_err)
            self.assertEqual(boundary_code, 0, boundary_err)
            self.assertEqual(sample_code, 0, sample_err)
            self.assertEqual(read_code, 0, read_err)
            self.assertEqual(read_text_code, 0, read_text_err)
            self.assertNotIn("CLI测试样本文本", sample_out + read_out)
            self.assertIn("CLI测试样本文本"[:4], read_text_out)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
