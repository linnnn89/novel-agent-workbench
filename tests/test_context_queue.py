from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import ContextUpdateQueueError, WorkbenchApplicationService, audit_project
from novel_agent_workbench.cli import main
from novel_agent_workbench.storage import ProjectStore


class ContextUpdateQueueTest(unittest.TestCase):
    def test_enqueue_confirmed_chapter_is_metadata_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-context-secret"})
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")

            first = app.enqueue_context_updates("demo")
            second = app.enqueue_context_updates("demo")
            listed = app.list_context_updates("demo")
            audit = audit_project(store)
            safe_text = json.dumps({"first": first, "second": second, "listed": listed, "audit": audit}, ensure_ascii=False)

            self.assertEqual(first["created_count"], 1)
            self.assertEqual(second["created_count"], 0)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["status"], "pending")
            self.assertEqual(listed[0]["targets"]["memory_bank"], "manual_pending")
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn("private context queue prompt", safe_text)
            self.assertNotIn(str(confirmed["content"]), safe_text)
            self.assertNotIn("sk-context-secret", safe_text)
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_mark_context_update_status_and_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            created = app.enqueue_context_updates("demo")
            update_id = created["items"][0]["update_id"]

            marked = app.mark_context_update("demo", update_id, status="acknowledged", reason_code="manual_done")
            pending = app.list_context_updates("demo", status="pending")
            acknowledged = app.list_context_updates("demo", status="acknowledged")

            self.assertEqual(marked["status"], "acknowledged")
            self.assertEqual(marked["reason_code"], "manual_done")
            self.assertEqual(pending, [])
            self.assertEqual(acknowledged[0]["update_id"], update_id)

    def test_context_update_queue_rejects_invalid_status_and_missing_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            created = app.enqueue_context_updates("demo")
            update_id = created["items"][0]["update_id"]

            with self.assertRaises(ContextUpdateQueueError):
                app.mark_context_update("demo", update_id, status="done")
            with self.assertRaises(ContextUpdateQueueError):
                app.mark_context_update("demo", "missing_update", status="skipped")

    def test_enqueue_without_confirmed_chapters_creates_no_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")

            result = app.enqueue_context_updates("demo")

            self.assertEqual(result["created_count"], 0)
            self.assertEqual(result["total_count"], 0)
            self.assertEqual(app.list_context_updates("demo"), [])

    def test_context_update_cli_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "configure-mock-writer", "demo"])
            _, draft_stdout, _ = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "private cli context queue prompt",
                ]
            )
            draft_id = json.loads(draft_stdout)["result"]["draft_id"]
            run_cli(["--projects-root", temp, "commit-draft", "demo", draft_id])

            enqueue_code, enqueue_stdout, enqueue_stderr = run_cli(["--projects-root", temp, "enqueue-context-updates", "demo"])
            update_id = json.loads(enqueue_stdout)["result"]["items"][0]["update_id"]
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-context-updates", "demo"])
            mark_code, mark_stdout, mark_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "mark-context-update",
                    "demo",
                    update_id,
                    "--status",
                    "skipped",
                    "--reason-code",
                    "manual_skip",
                ]
            )
            combined = enqueue_stdout + list_stdout + mark_stdout

            self.assertEqual(enqueue_code, 0, enqueue_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(mark_code, 0, mark_stderr)
            self.assertEqual(json.loads(mark_stdout)["result"]["status"], "skipped")
            self.assertNotIn("private cli context queue prompt", combined)
            self.assertNotIn("MOCK writer", combined)


def configured_committed_app(temp: str) -> WorkbenchApplicationService:
    app = WorkbenchApplicationService.open(Path(temp))
    app.create_project("demo")
    app.configure_mock_writer("demo")
    draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private context queue prompt")
    app.commit_draft("demo", draft["draft_id"])
    return app


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
