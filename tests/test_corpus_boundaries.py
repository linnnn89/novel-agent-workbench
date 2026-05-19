from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import WorkbenchApplicationService
from novel_agent_workbench.cli import main


class CorpusBoundaryTest(unittest.TestCase):
    def test_save_corpus_boundaries_stores_offsets_without_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp) / "projects")
            app.create_project("demo")
            source = Path(temp) / "source.txt"
            body = "\n".join(
                [
                    "第一章 BoundaryAlphaTitle",
                    "明河说道：“第一段秘密。”",
                    "普通叙述段落。",
                    "第二章 BoundaryBetaTitle",
                    "青岚问：“第二段秘密。”",
                ]
            )
            source.write_text(body, encoding="utf-8")

            saved = app.save_corpus_boundaries("demo", source)
            items = app.list_corpus_boundaries("demo")
            artifact = app.read_corpus_boundaries("demo", saved["boundary_id"])
            state = app.project_state("demo")
            result_text = json.dumps(
                {"saved": saved, "items": items, "artifact": artifact, "state": state},
                ensure_ascii=False,
            )

            self.assertEqual(saved["status"], "boundaries_ready")
            self.assertEqual(saved["chapter_count"], 2)
            self.assertEqual(len(items), 1)
            self.assertEqual(len(artifact["boundaries"]), 2)
            self.assertGreater(artifact["boundaries"][0]["body_char_count"], 0)
            self.assertFalse(artifact["source"]["original_path_stored"])
            self.assertEqual(state["corpus_boundary_count"], 1)
            self.assertEqual(state["latest_corpus_boundary"]["boundary_id"], saved["boundary_id"])
            self.assertTrue(app.audit_project("demo")["ok"])
            self.assertNotIn("BoundaryAlphaTitle", result_text)
            self.assertNotIn("第一段秘密", result_text)
            self.assertNotIn(str(source), result_text)

    def test_cli_save_list_read_corpus_boundaries_excludes_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects_root = Path(temp) / "projects"
            source_dir = Path(temp) / "source"
            source_dir.mkdir()
            source = source_dir / "sample.txt"
            body = "\n".join(
                [
                    "第一章 CliBoundaryAlpha",
                    "明河说道：“边界台词。”",
                    "第二章 CliBoundaryBeta",
                    "普通叙述段落。",
                ]
            )
            source.write_text(body, encoding="utf-8")

            create_code, _, create_err = run_cli(
                ["--projects-root", str(projects_root), "create-project", "demo"]
            )
            save_code, save_out, save_err = run_cli(
                ["--projects-root", str(projects_root), "save-corpus-boundaries", "demo", str(source)]
            )
            boundary_id = json.loads(save_out)["result"]["boundary_id"]
            list_code, list_out, list_err = run_cli(
                ["--projects-root", str(projects_root), "list-corpus-boundaries", "demo"]
            )
            read_code, read_out, read_err = run_cli(
                ["--projects-root", str(projects_root), "read-corpus-boundaries", "demo", boundary_id]
            )
            combined = save_out + list_out + read_out

            self.assertEqual(create_code, 0, create_err)
            self.assertEqual(save_code, 0, save_err)
            self.assertEqual(list_code, 0, list_err)
            self.assertEqual(read_code, 0, read_err)
            self.assertNotIn("CliBoundaryAlpha", combined)
            self.assertNotIn("边界台词", combined)
            self.assertNotIn(str(source), combined)

    def test_audit_rejects_corpus_boundary_source_path_or_text_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp) / "projects")
            app.create_project("demo")
            source = Path(temp) / "source.txt"
            source.write_text("第一章 AuditBoundaryAlpha\n明河说道：“秘密。”", encoding="utf-8")
            saved = app.save_corpus_boundaries("demo", source)
            artifact_path = Path(saved["path"])
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            artifact["source"]["path"] = str(source)
            artifact["source"]["original_path_stored"] = True
            artifact["boundaries"][0]["heading_text"] = "AuditBoundaryAlpha"
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

            audit = app.audit_project("demo")
            codes = {finding["code"] for finding in audit["findings"]}

            self.assertFalse(audit["ok"])
            self.assertIn("corpus_boundary_source_path_stored", codes)
            self.assertIn("corpus_boundary_text_field_stored", codes)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
