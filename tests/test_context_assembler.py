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
from novel_agent_workbench.storage import ProjectStore


class ContextAssemblerTest(unittest.TestCase):
    def test_context_assembly_dry_run_is_metadata_only_and_prioritized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-context-assembler-secret"})
            store.write_json(
                store.data_file_path("memory_bank.json"),
                {
                    "schema_version": 1,
                    "enabled": True,
                    "items": [
                        {
                            "id": "memory_private",
                            "category_id": "character_relationships",
                            "text": "PRIVATE MEMORY BANK TEXT",
                            "memory_weight": 1.0,
                        }
                    ],
                },
            )
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")

            result = app.context_assembly_dry_run("demo", max_context_tokens=4096)
            result_text = json.dumps(result, ensure_ascii=False)

            self.assertEqual(result["mode"], "metadata_only_dry_run")
            self.assertTrue(result["provider_api_boundary"]["requires_local_context_assembly"])
            self.assertFalse(result["provider_api_boundary"]["llm_api_accepts_priority_fields"])
            self.assertFalse(result["provider_api_boundary"]["provider_called"])
            self.assertGreater(len(result["candidates"]), 0)
            self.assertEqual(result["candidates"][0]["category_id"], "world_building")
            self.assertEqual(result["candidates"][0]["priority"], 1)
            self.assertNotIn("private assembler prompt", result_text)
            self.assertNotIn(str(confirmed["content"]), result_text)
            self.assertNotIn("PRIVATE MEMORY BANK TEXT", result_text)
            self.assertNotIn("sk-context-assembler-secret", result_text)

    def test_context_assembly_dry_run_respects_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp)

            result = app.context_assembly_dry_run("demo", max_context_tokens=1)

            self.assertEqual(result["token_budget"]["max_context_tokens"], 1)
            self.assertGreater(len(result["skipped"]), 0)
            self.assertTrue(any(item["skip_reason"] == "token_budget_exceeded" for item in result["skipped"]))

    def test_context_assembly_dry_run_reflects_world_book_overlap_weight(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp, world_book_enabled=True)

            result = app.context_assembly_dry_run("demo", max_context_tokens=4096)
            world_building = next(item for item in result["candidates"] if item["category_id"] == "world_building")

            self.assertEqual(world_building["memory_weight"], 0.35)
            self.assertEqual(world_building["reason"], "reduce_memory_weight_world_book_enabled")
            self.assertIn("world_book_enabled_world_building_memory_weight_may_be_reduced", result["warnings"])

    def test_context_assembly_dry_run_cli_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_context_plan_app(temp)

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "context-assembly-dry-run",
                    "demo",
                    "--max-context-tokens",
                    "4096",
                ]
            )

            self.assertEqual(code, 0, stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["result"]["provider_api_boundary"]["requires_local_context_assembly"])
            self.assertNotIn("private assembler prompt", stdout)
            self.assertNotIn("MOCK writer", stdout)

    def test_formal_context_task_queue_is_metadata_only_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-formal-task-secret"})
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]

            first = app.enqueue_formal_context_tasks("demo", plan_id)
            second = app.enqueue_formal_context_tasks("demo", plan_id)
            listed = app.list_formal_context_tasks("demo")
            state = app.project_state("demo")
            result_text = json.dumps(
                {"first": first, "second": second, "listed": listed, "state": state},
                ensure_ascii=False,
            )

            self.assertEqual(first["created_count"], 5)
            self.assertEqual(second["created_count"], 0)
            self.assertEqual(len(listed), 5)
            self.assertEqual(listed[0]["category_id"], "world_building")
            self.assertEqual(state["formal_context_task_count"], 5)
            self.assertNotIn("private assembler prompt", result_text)
            self.assertNotIn(str(confirmed["content"]), result_text)
            self.assertNotIn("sk-formal-task-secret", result_text)
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))

    def test_formal_context_task_mark_and_cli_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_context_plan_app(temp)
            app = WorkbenchApplicationService.open(Path(temp))
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            created = app.enqueue_formal_context_tasks("demo", plan_id)
            task_id = created["items"][0]["task_id"]

            marked = app.mark_formal_context_task("demo", task_id, status="acknowledged", reason_code="manual_done")
            pending = app.list_formal_context_tasks("demo", status="pending")
            acknowledged = app.list_formal_context_tasks("demo", status="acknowledged")

            self.assertEqual(marked["status"], "acknowledged")
            self.assertEqual(marked["reason_code"], "manual_done")
            self.assertEqual(len(pending), 4)
            self.assertEqual(acknowledged[0]["task_id"], task_id)

            code, stdout, stderr = run_cli(
                ["--projects-root", temp, "list-formal-context-tasks", "demo", "--status", "acknowledged"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["result"][0]["task_id"], task_id)
            self.assertNotIn("private assembler prompt", stdout)
            self.assertNotIn("MOCK writer", stdout)

    def test_memory_apply_preview_is_metadata_only_and_does_not_write_memory_bank(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-memory-preview-secret"})
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            app.enqueue_formal_context_tasks("demo", plan_id)
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")

            result = app.create_memory_apply_preview("demo")
            previews = app.list_memory_apply_previews("demo")
            preview = app.read_memory_apply_preview("demo", result["preview_id"])
            state = app.project_state("demo")
            result_text = json.dumps(
                {"result": result, "previews": previews, "preview": preview, "state": state},
                ensure_ascii=False,
            )

            self.assertEqual(result["status"], "preview_ready")
            self.assertEqual(result["task_count"], 5)
            self.assertEqual(preview["summary"]["would_write_memory_bank"], False)
            self.assertEqual(len(preview["items"]), 5)
            self.assertEqual(preview["items"][0]["proposed_action"], "manual_memory_bank_candidate")
            self.assertEqual(state["memory_apply_preview_count"], 1)
            self.assertNotIn("private assembler prompt", result_text)
            self.assertNotIn(str(confirmed["content"]), result_text)
            self.assertNotIn("sk-memory-preview-secret", result_text)
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))

    def test_memory_apply_preview_flags_world_book_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp, world_book_enabled=True)
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            app.enqueue_formal_context_tasks("demo", plan_id)

            result = app.create_memory_apply_preview("demo")
            preview = app.read_memory_apply_preview("demo", result["preview_id"])
            world_building = preview["items"][0]

            self.assertTrue(preview["world_book_enabled"])
            self.assertEqual(world_building["category_id"], "world_building")
            self.assertEqual(world_building["memory_weight"], 0.35)
            self.assertEqual(world_building["duplicate_risk"], "world_book_overlap_review_required")

    def test_memory_apply_preview_cli_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_context_plan_app(temp)
            app = WorkbenchApplicationService.open(Path(temp))
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            app.enqueue_formal_context_tasks("demo", plan_id)

            create_code, create_stdout, create_stderr = run_cli(
                ["--projects-root", temp, "create-memory-apply-preview", "demo"]
            )
            preview_id = json.loads(create_stdout)["result"]["preview_id"]
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-memory-apply-previews", "demo"])
            read_code, read_stdout, read_stderr = run_cli(
                ["--projects-root", temp, "read-memory-apply-preview", "demo", preview_id]
            )
            combined = create_stdout + list_stdout + read_stdout

            self.assertEqual(create_code, 0, create_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(read_code, 0, read_stderr)
            self.assertEqual(json.loads(read_stdout)["result"]["task_count"], 5)
            self.assertNotIn("private assembler prompt", combined)
            self.assertNotIn("MOCK writer", combined)


def configured_context_plan_app(temp: str, *, world_book_enabled: bool = False) -> WorkbenchApplicationService:
    app = WorkbenchApplicationService.open(Path(temp))
    app.create_project("demo")
    app.configure_mock_writer("demo")
    draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private assembler prompt")
    app.commit_draft("demo", draft["draft_id"])
    store = ProjectStore.open(Path(temp), "demo")
    if world_book_enabled:
        config = store.read_config()
        config["context_policy"]["world_book_enabled"] = True
        store.write_config(config)
    update = app.enqueue_context_updates("demo")["items"][0]
    preview = app.create_context_preview("demo", update["update_id"])
    app.create_formal_context_plan("demo", preview["preview_id"])
    return app


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
