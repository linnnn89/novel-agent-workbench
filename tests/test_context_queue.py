from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    ContextUpdatePreviewError,
    ContextUpdateQueueError,
    FormalContextPlanError,
    WorkbenchApplicationService,
    audit_project,
)
from novel_agent_workbench.cli import main
from novel_agent_workbench.config import FORMAL_CONTEXT_PRIORITY_ORDER
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

    def test_context_preview_artifact_is_metadata_only_and_has_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-preview-secret"})
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")
            update = app.enqueue_context_updates("demo")["items"][0]

            result = app.create_context_preview("demo", update["update_id"])
            previews = app.list_context_previews("demo")
            preview = app.read_context_preview("demo", result["preview_id"])
            state = app.project_state("demo")
            audit = audit_project(store)
            safe_text = json.dumps(
                {"result": result, "previews": previews, "preview": preview, "state": state, "audit": audit},
                ensure_ascii=False,
            )

            self.assertEqual(result["status"], "preview_ready")
            self.assertEqual(preview["update_id"], update["update_id"])
            self.assertEqual(preview["recommendation"], "manual_review_required")
            self.assertEqual(
                preview["target_plan"]["formal_context"]["priority_order"],
                FORMAL_CONTEXT_PRIORITY_ORDER,
            )
            self.assertFalse(preview["safety"]["text_copied"])
            self.assertFalse(preview["safety"]["provider_called"])
            self.assertEqual(state["context_preview_count"], 1)
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn("private context queue prompt", safe_text)
            self.assertNotIn(str(confirmed["content"]), safe_text)
            self.assertNotIn("sk-preview-secret", safe_text)
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_context_preview_rejects_duplicate_skipped_and_missing_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            update = app.enqueue_context_updates("demo")["items"][0]
            app.create_context_preview("demo", update["update_id"])

            with self.assertRaises(ContextUpdatePreviewError):
                app.create_context_preview("demo", update["update_id"])
            with self.assertRaises(ContextUpdatePreviewError):
                app.create_context_preview("demo", "missing_update")

        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            update = app.enqueue_context_updates("demo")["items"][0]
            app.mark_context_update("demo", update["update_id"], status="skipped", reason_code="manual_skip")

            with self.assertRaises(ContextUpdatePreviewError):
                app.create_context_preview("demo", update["update_id"])

    def test_context_preview_cli_is_metadata_only(self) -> None:
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
                    "private cli context preview prompt",
                ]
            )
            draft_id = json.loads(draft_stdout)["result"]["draft_id"]
            run_cli(["--projects-root", temp, "commit-draft", "demo", draft_id])
            _, enqueue_stdout, _ = run_cli(["--projects-root", temp, "enqueue-context-updates", "demo"])
            update_id = json.loads(enqueue_stdout)["result"]["items"][0]["update_id"]

            create_code, create_stdout, create_stderr = run_cli(
                ["--projects-root", temp, "create-context-preview", "demo", update_id]
            )
            preview_id = json.loads(create_stdout)["result"]["preview_id"]
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-context-previews", "demo"])
            read_code, read_stdout, read_stderr = run_cli(
                ["--projects-root", temp, "read-context-preview", "demo", preview_id]
            )
            combined = create_stdout + list_stdout + read_stdout

            self.assertEqual(create_code, 0, create_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(read_code, 0, read_stderr)
            self.assertEqual(json.loads(list_stdout)["result"][0]["preview_id"], preview_id)
            self.assertEqual(json.loads(read_stdout)["result"]["status"], "preview_ready")
            self.assertNotIn("private cli context preview prompt", combined)
            self.assertNotIn("MOCK writer", combined)

    def test_formal_context_plan_artifact_is_metadata_only_and_has_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-formal-context-secret"})
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")
            update = app.enqueue_context_updates("demo")["items"][0]
            preview = app.create_context_preview("demo", update["update_id"])

            result = app.create_formal_context_plan("demo", preview["preview_id"])
            plans = app.list_formal_context_plans("demo")
            plan = app.read_formal_context_plan("demo", result["plan_id"])
            state = app.project_state("demo")
            audit = audit_project(store)
            safe_text = json.dumps(
                {"result": result, "plans": plans, "plan": plan, "state": state, "audit": audit},
                ensure_ascii=False,
            )

            self.assertEqual(result["status"], "plan_ready")
            self.assertEqual(plan["preview_id"], preview["preview_id"])
            self.assertEqual(plan["priority_order"], FORMAL_CONTEXT_PRIORITY_ORDER)
            self.assertEqual([item["category_id"] for item in plan["categories"]], FORMAL_CONTEXT_PRIORITY_ORDER)
            self.assertTrue(all(item["auto_extract"] is False for item in plan["categories"]))
            self.assertFalse(plan["safety"]["text_copied"])
            self.assertFalse(plan["safety"]["memory_bank_written"])
            self.assertEqual(state["formal_context_plan_count"], 1)
            self.assertEqual(state["latest_formal_context_plan"]["priority_order"], FORMAL_CONTEXT_PRIORITY_ORDER)
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn("private context queue prompt", safe_text)
            self.assertNotIn(str(confirmed["content"]), safe_text)
            self.assertNotIn("sk-formal-context-secret", safe_text)
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_formal_context_plan_rejects_duplicate_and_missing_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_committed_app(temp)
            update = app.enqueue_context_updates("demo")["items"][0]
            preview = app.create_context_preview("demo", update["update_id"])
            app.create_formal_context_plan("demo", preview["preview_id"])

            with self.assertRaises(FormalContextPlanError):
                app.create_formal_context_plan("demo", preview["preview_id"])
            with self.assertRaises(ContextUpdatePreviewError):
                app.create_formal_context_plan("demo", "missing_preview")

    def test_formal_context_plan_cli_is_metadata_only(self) -> None:
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
                    "private cli formal context prompt",
                ]
            )
            draft_id = json.loads(draft_stdout)["result"]["draft_id"]
            run_cli(["--projects-root", temp, "commit-draft", "demo", draft_id])
            _, enqueue_stdout, _ = run_cli(["--projects-root", temp, "enqueue-context-updates", "demo"])
            update_id = json.loads(enqueue_stdout)["result"]["items"][0]["update_id"]
            _, preview_stdout, _ = run_cli(["--projects-root", temp, "create-context-preview", "demo", update_id])
            preview_id = json.loads(preview_stdout)["result"]["preview_id"]

            create_code, create_stdout, create_stderr = run_cli(
                ["--projects-root", temp, "create-formal-context-plan", "demo", preview_id]
            )
            plan_id = json.loads(create_stdout)["result"]["plan_id"]
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-formal-context-plans", "demo"])
            read_code, read_stdout, read_stderr = run_cli(
                ["--projects-root", temp, "read-formal-context-plan", "demo", plan_id]
            )
            combined = create_stdout + list_stdout + read_stdout

            self.assertEqual(create_code, 0, create_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(read_code, 0, read_stderr)
            self.assertEqual(json.loads(list_stdout)["result"][0]["plan_id"], plan_id)
            self.assertEqual(json.loads(read_stdout)["result"]["priority_order"], FORMAL_CONTEXT_PRIORITY_ORDER)
            self.assertNotIn("private cli formal context prompt", combined)
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
