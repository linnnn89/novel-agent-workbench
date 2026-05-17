from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import ProviderError, WorkbenchApplicationService, audit_project
from novel_agent_workbench.chapters import ChapterWorkflowService
from novel_agent_workbench.drafts import DraftGenerationRequest, DraftGenerationError, DraftGenerationService
from novel_agent_workbench.providers import set_model_role_config
from novel_agent_workbench.storage import ProjectStore
from novel_agent_workbench.cli import main


class ChapterWorkflowTest(unittest.TestCase):
    def test_generate_and_commit_update_chapter_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            workflow = ChapterWorkflowService(store)

            workflow.mark_planned("chapter_001", title="Opening")
            draft = service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", title="Opening", prompt="private workflow prompt")
            )
            ready = workflow.get_chapter("chapter_001")
            committed = service.commit_draft(draft.draft_id)
            chapter = workflow.get_chapter("chapter_001")

            self.assertEqual(ready["status"], "draft_ready")
            self.assertEqual(ready["latest_draft_id"], draft.draft_id)
            self.assertEqual(chapter["status"], "committed")
            self.assertEqual(chapter["confirmed_chapter_id"], committed.chapter_id)
            self.assertEqual(chapter["latest_draft_id"], draft.draft_id)

    def test_failed_generation_records_metadata_only_blocked_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            service = DraftGenerationService(store)
            workflow = ChapterWorkflowService(store)

            with self.assertRaises(ProviderError):
                service.generate_draft(
                    DraftGenerationRequest(chapter_id="chapter_001", title="Opening", prompt="private failed prompt")
                )
            chapter = workflow.get_chapter("chapter_001")
            text = json.dumps(chapter, ensure_ascii=False)

            self.assertEqual(chapter["status"], "blocked")
            self.assertEqual(chapter["error_summary"]["stage"], "generate_draft")
            self.assertNotIn("private failed prompt", text)
            self.assertFalse((store.data_dir / "drafts").exists())

    def test_duplicate_commit_keeps_committed_status_and_records_error_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            workflow = ChapterWorkflowService(store)
            draft = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="private draft"))
            service.commit_draft(draft.draft_id)

            with self.assertRaises(DraftGenerationError):
                service.commit_draft(draft.draft_id)
            chapter = workflow.get_chapter("chapter_001")

            self.assertEqual(chapter["status"], "committed")
            self.assertEqual(chapter["error_summary"]["stage"], "commit_draft")

    def test_public_state_and_audit_do_not_expose_prompt_content_or_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")
            draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private state workflow prompt")
            app.commit_draft("demo", draft["draft_id"])

            state_text = json.dumps(app.project_state("demo"), ensure_ascii=False)
            audit_text = json.dumps(app.audit_project("demo"), ensure_ascii=False)

            self.assertNotIn("private state workflow prompt", state_text)
            self.assertNotIn("MOCK writer", state_text)
            self.assertNotIn("private state workflow prompt", audit_text)
            self.assertNotIn("MOCK writer", audit_text)

    def test_chapter_cli_commands_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            create_code, _, create_stderr = run_cli(["--projects-root", temp, "create-project", "demo"])
            mark_code, mark_stdout, mark_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "mark-chapter-planned",
                    "demo",
                    "chapter_001",
                    "--title",
                    "Opening",
                ]
            )
            status_code, status_stdout, status_stderr = run_cli(
                ["--projects-root", temp, "chapter-status", "demo", "chapter_001"]
            )
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-chapters", "demo"])

            self.assertEqual(create_code, 0, create_stderr)
            self.assertEqual(mark_code, 0, mark_stderr)
            self.assertEqual(status_code, 0, status_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(json.loads(mark_stdout)["result"]["status"], "planned")
            self.assertEqual(json.loads(status_stdout)["result"]["chapter_id"], "chapter_001")
            self.assertEqual(len(json.loads(list_stdout)["result"]), 1)


def configured_store(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    return store


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
