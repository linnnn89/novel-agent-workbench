from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench.cli import main


class CliTest(unittest.TestCase):
    def test_smoke_command_can_generate_and_commit_without_prompt_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "smoke",
                    "demo",
                    "--title",
                    "Demo Novel",
                    "--chapter-id",
                    "chapter_001",
                    "--chapter-title",
                    "Opening",
                    "--prompt",
                    "private cli prompt",
                    "--commit",
                ]
            )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertEqual(payload["result"]["project"]["project_id"], "demo")
            self.assertEqual(payload["result"]["state"]["committed_chapter_count"], 1)
            self.assertNotIn("private cli prompt", stdout)
            self.assertEqual(stderr, "")

    def test_generate_command_reports_error_without_creating_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "no configured writer",
                ]
            )
            state_code, state_stdout, _ = run_cli(["--projects-root", temp, "state", "demo"])
            error_payload = json.loads(stderr)
            state_payload = json.loads(state_stdout)

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(error_payload["error_type"], "ProviderError")
            self.assertEqual(state_code, 0)
            self.assertEqual(state_payload["result"]["draft_count"], 0)

    def test_split_commands_create_generate_commit_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli(["--projects-root", temp, "create-project", "demo"])[0], 0)
            self.assertEqual(run_cli(["--projects-root", temp, "configure-mock-writer", "demo"])[0], 0)
            code, stdout, _ = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "draft by split commands",
                ]
            )
            draft_id = json.loads(stdout)["result"]["draft_id"]
            commit_code, commit_stdout, _ = run_cli(["--projects-root", temp, "commit-draft", "demo", draft_id])
            list_code, list_stdout, _ = run_cli(["--projects-root", temp, "list-confirmed", "demo"])

            self.assertEqual(code, 0)
            self.assertEqual(commit_code, 0)
            self.assertEqual(json.loads(commit_stdout)["result"]["chapter_id"], "chapter_001")
            self.assertEqual(list_code, 0)
            self.assertEqual(len(json.loads(list_stdout)["result"]), 1)

    def test_audit_project_checks_smoke_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            smoke_code, _, smoke_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "smoke",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "private audit cli prompt",
                    "--commit",
                ]
            )
            audit_code, audit_stdout, audit_stderr = run_cli(["--projects-root", temp, "audit-project", "demo"])
            payload = json.loads(audit_stdout)

            self.assertEqual(smoke_code, 0, smoke_stderr)
            self.assertEqual(audit_code, 0, audit_stderr)
            self.assertTrue(payload["result"]["ok"], audit_stdout)
            self.assertNotIn("private audit cli prompt", audit_stdout)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
