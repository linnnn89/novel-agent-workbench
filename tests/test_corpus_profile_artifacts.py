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


class CorpusProfileArtifactTest(unittest.TestCase):
    def test_save_corpus_profile_is_persistent_but_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp) / "projects")
            app.create_project("demo")
            source = Path(temp) / "source.txt"
            body = "\n".join(
                [
                    "第一章 ArtifactAlphaTitle",
                    "明河说道：“今天去训练场。”",
                    "第二章 ArtifactBetaTitle",
                    "青岚问：“继续吗？”",
                ]
            )
            source.write_text(body, encoding="utf-8")

            saved = app.save_corpus_profile("demo", source, max_name_candidates=5)
            profiles = app.list_corpus_profiles("demo")
            artifact = app.read_corpus_profile("demo", saved["profile_id"])
            state = app.project_state("demo")
            result_text = json.dumps(
                {"saved": saved, "profiles": profiles, "artifact": artifact, "state": state},
                ensure_ascii=False,
            )

            self.assertEqual(saved["status"], "profile_ready")
            self.assertEqual(len(profiles), 1)
            self.assertEqual(artifact["structure"]["strict_chapter_heading_count"], 2)
            self.assertFalse(artifact["source"]["original_path_stored"])
            self.assertFalse(artifact["name_candidates"]["top_included"])
            self.assertEqual(state["corpus_profile_count"], 1)
            self.assertEqual(state["latest_corpus_profile"]["profile_id"], saved["profile_id"])
            self.assertTrue(app.audit_project("demo")["ok"])
            self.assertNotIn("ArtifactAlphaTitle", result_text)
            self.assertNotIn("今天去训练场", result_text)
            self.assertNotIn("明河", result_text)
            self.assertNotIn(str(source), result_text)

    def test_audit_rejects_corpus_profile_source_path_or_candidate_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp) / "projects")
            app.create_project("demo")
            source = Path(temp) / "source.txt"
            source.write_text("第一章 AuditAlphaTitle\n明河说道：“秘密。”", encoding="utf-8")
            saved = app.save_corpus_profile("demo", source)
            artifact_path = Path(saved["path"])
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            artifact["source"]["path"] = str(source)
            artifact["source"]["original_path_stored"] = True
            artifact["name_candidates"]["top"] = [{"name": "明河", "count": 1}]
            artifact["name_candidates"]["top_included"] = True
            artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

            audit = app.audit_project("demo")
            codes = {finding["code"] for finding in audit["findings"]}
            audit_text = json.dumps(audit, ensure_ascii=False)

            self.assertFalse(audit["ok"])
            self.assertIn("corpus_profile_source_path_stored", codes)
            self.assertIn("corpus_profile_candidate_names_stored", codes)
            self.assertNotIn("秘密", audit_text)

    def test_cli_save_list_read_corpus_profile_excludes_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects_root = Path(temp) / "projects"
            source_dir = Path(temp) / "source"
            source_dir.mkdir()
            source = source_dir / "sample.txt"
            body = "\n".join(
                [
                    "第一章 CliAlphaTitle",
                    "明河说道：“保密台词。”",
                    "第二章 CliBetaTitle",
                    "普通叙述段落。",
                ]
            )
            source.write_text(body, encoding="utf-8")

            create_code, _, create_err = run_cli(
                ["--projects-root", str(projects_root), "create-project", "demo"]
            )
            save_code, save_out, save_err = run_cli(
                [
                    "--projects-root",
                    str(projects_root),
                    "save-corpus-profile",
                    "demo",
                    str(source),
                    "--max-name-candidates",
                    "5",
                ]
            )
            profile_id = json.loads(save_out)["result"]["profile_id"]
            list_code, list_out, list_err = run_cli(
                ["--projects-root", str(projects_root), "list-corpus-profiles", "demo"]
            )
            read_code, read_out, read_err = run_cli(
                ["--projects-root", str(projects_root), "read-corpus-profile", "demo", profile_id]
            )
            combined = save_out + list_out + read_out

            self.assertEqual(create_code, 0, create_err)
            self.assertEqual(save_code, 0, save_err)
            self.assertEqual(list_code, 0, list_err)
            self.assertEqual(read_code, 0, read_err)
            self.assertNotIn("CliAlphaTitle", combined)
            self.assertNotIn("保密台词", combined)
            self.assertNotIn("明河", combined)
            self.assertNotIn(str(source), combined)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
