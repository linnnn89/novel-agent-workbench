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
from novel_agent_workbench import audit_project
from novel_agent_workbench import MemoryBankError
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

    def test_commit_memory_apply_preview_writes_placeholder_entries_with_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-memory-commit-secret"})
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            app.enqueue_formal_context_tasks("demo", plan_id)
            preview = app.create_memory_apply_preview("demo")
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")

            result = app.commit_memory_apply_preview("demo", preview["preview_id"])
            memory_bank = store.read_json(store.data_file_path("memory_bank.json"))
            state = app.project_state("demo")
            audit = audit_project(store)
            result_text = json.dumps(
                {"result": result, "memory_bank": memory_bank, "state": state, "audit": audit},
                ensure_ascii=False,
            )

            self.assertEqual(result["status"], "committed")
            self.assertEqual(result["created_count"], 5)
            self.assertEqual(result["skipped_count"], 0)
            self.assertTrue(Path(result["checkpoint"]["path"]).exists())
            self.assertTrue(memory_bank["enabled"])
            self.assertEqual(len(memory_bank["items"]), 5)
            self.assertEqual(memory_bank["items"][0]["entry_type"], "formal_context_placeholder")
            self.assertEqual(memory_bank["items"][0]["status"], "manual_text_required")
            self.assertEqual(memory_bank["items"][0]["text"], "")
            self.assertEqual(state["memory_bank_item_count"], 5)
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn("private assembler prompt", result_text)
            self.assertNotIn(str(confirmed["content"]), result_text)
            self.assertNotIn("sk-memory-commit-secret", result_text)

    def test_commit_memory_apply_preview_is_duplicate_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_context_plan_app(temp)
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            app.enqueue_formal_context_tasks("demo", plan_id)
            preview = app.create_memory_apply_preview("demo")

            first = app.commit_memory_apply_preview("demo", preview["preview_id"])
            second = app.commit_memory_apply_preview("demo", preview["preview_id"])
            memory_bank = ProjectStore.open(Path(temp), "demo").read_json(
                ProjectStore.open(Path(temp), "demo").data_file_path("memory_bank.json")
            )

            self.assertEqual(first["created_count"], 5)
            self.assertEqual(second["status"], "no_new_items")
            self.assertEqual(second["created_count"], 0)
            self.assertEqual(second["skipped_count"], 5)
            self.assertEqual(len(memory_bank["items"]), 5)

    def test_commit_memory_apply_preview_cli_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_context_plan_app(temp)
            app = WorkbenchApplicationService.open(Path(temp))
            plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
            app.enqueue_formal_context_tasks("demo", plan_id)
            preview = app.create_memory_apply_preview("demo")

            code, stdout, stderr = run_cli(
                ["--projects-root", temp, "commit-memory-apply-preview", "demo", preview["preview_id"]]
            )

            self.assertEqual(code, 0, stderr)
            payload = json.loads(stdout)
            self.assertEqual(payload["result"]["created_count"], 5)
            self.assertNotIn("private assembler prompt", stdout)
            self.assertNotIn("MOCK writer", stdout)

    def test_manual_memory_text_fill_is_explicit_and_default_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            store.update_secrets({"mock_key": "sk-memory-fill-secret"})
            memory_id = app.list_memory_items("demo")[0]["memory_id"]
            manual_text = "本章新增王城禁书区规则，后续冲突围绕通行许可展开。"

            result = app.set_memory_text("demo", memory_id, manual_text)
            listed = app.list_memory_items("demo")
            read_default = app.read_memory_item("demo", memory_id)
            read_with_text = app.read_memory_item("demo", memory_id, include_text=True)
            state = app.project_state("demo")
            audit = audit_project(store)
            default_text = json.dumps(
                {"result": result, "listed": listed, "read_default": read_default, "state": state, "audit": audit},
                ensure_ascii=False,
            )

            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["text_chars"], len(manual_text))
            self.assertTrue(Path(result["checkpoint"]["path"]).exists())
            self.assertEqual(listed[0]["text_chars"], len(manual_text))
            self.assertNotIn("text", read_default)
            self.assertEqual(read_with_text["text"], manual_text)
            self.assertEqual(state["latest_memory_bank_item"]["text_status"], "manual")
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn(manual_text, default_text)
            self.assertNotIn("sk-memory-fill-secret", default_text)

    def test_manual_memory_text_rejects_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            memory_id = app.list_memory_items("demo")[0]["memory_id"]

            with self.assertRaises(MemoryBankError):
                app.set_memory_text("demo", memory_id, "cpk_fake_secret_value_123456789")

    def test_manual_memory_text_rejects_oversized_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            memory_id = app.list_memory_items("demo")[0]["memory_id"]

            with self.assertRaises(MemoryBankError):
                app.set_memory_text("demo", memory_id, "x" * 1201)

    def test_manual_memory_text_missing_item_does_not_create_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            store = ProjectStore.open(Path(temp), "demo")
            checkpoint_dir = store.backups_dir / "checkpoints"
            before = sorted(checkpoint_dir.glob("*.zip"))

            with self.assertRaises(MemoryBankError):
                app.set_memory_text("demo", "missing_memory_id", "Manual memory note.")

            after = sorted(checkpoint_dir.glob("*.zip"))
            self.assertEqual(before, after)

    def test_memory_item_disable_excludes_item_from_context_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            memory_id = app.list_memory_items("demo")[0]["memory_id"]
            manual_text = "Manual memory: sky iron is banned inside the city."
            app.set_memory_text("demo", memory_id, manual_text)

            disabled = app.set_memory_item_enabled("demo", memory_id, enabled=False, reason_code="duplicate_world_book")
            read_default = app.read_memory_item("demo", memory_id)
            state = app.project_state("demo")
            dry_run = app.context_assembly_dry_run("demo", max_context_tokens=4096)
            skipped = [
                item
                for item in dry_run["skipped"]
                if item.get("source_type") == "memory_bank" and item.get("source_id") == memory_id
            ]
            selected = [
                item
                for item in dry_run["selected"]
                if item.get("source_type") == "memory_bank" and item.get("source_id") == memory_id
            ]
            result_text = json.dumps({"disabled": disabled, "read": read_default, "state": state, "dry_run": dry_run})

            self.assertFalse(disabled["enabled"])
            self.assertEqual(disabled["lifecycle_status"], "disabled")
            self.assertTrue(Path(disabled["checkpoint"]["path"]).exists())
            self.assertFalse(read_default["enabled"])
            self.assertEqual(state["latest_memory_bank_item"]["lifecycle_status"], "disabled")
            self.assertEqual(skipped[0]["skip_reason"], "memory_item_disabled")
            self.assertEqual(selected, [])
            self.assertNotIn(manual_text, result_text)

    def test_memory_item_enable_disable_cli_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            memory_id = app.list_memory_items("demo")[0]["memory_id"]
            manual_text = "Manual memory: the canal gate opens only at dawn."
            app.set_memory_text("demo", memory_id, manual_text)

            disable_code, disable_stdout, disable_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "disable-memory-item",
                    "demo",
                    memory_id,
                    "--reason-code",
                    "manual_suppress",
                ]
            )
            enable_code, enable_stdout, enable_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "enable-memory-item",
                    "demo",
                    memory_id,
                    "--reason-code",
                    "manual_restore",
                ]
            )
            combined = disable_stdout + enable_stdout

            self.assertEqual(disable_code, 0, disable_stderr)
            self.assertEqual(enable_code, 0, enable_stderr)
            self.assertFalse(json.loads(disable_stdout)["result"]["enabled"])
            self.assertTrue(json.loads(enable_stdout)["result"]["enabled"])
            self.assertNotIn(manual_text, combined)

    def test_memory_item_lifecycle_rejects_unsafe_reason_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            memory_id = app.list_memory_items("demo")[0]["memory_id"]

            with self.assertRaises(MemoryBankError):
                app.set_memory_item_enabled("demo", memory_id, enabled=False, reason_code="bad reason")

    def test_manual_memory_text_cli_is_metadata_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = configured_memory_bank_app(temp)
            memory_id = app.list_memory_items("demo")[0]["memory_id"]
            manual_text = "人物关系更新：阿宁开始怀疑导师隐瞒旧案。"

            set_code, set_stdout, set_stderr = run_cli(
                ["--projects-root", temp, "set-memory-text", "demo", memory_id, "--text", manual_text]
            )
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-memory-items", "demo"])
            read_code, read_stdout, read_stderr = run_cli(["--projects-root", temp, "read-memory-item", "demo", memory_id])
            include_code, include_stdout, include_stderr = run_cli(
                ["--projects-root", temp, "read-memory-item", "demo", memory_id, "--include-text"]
            )
            default_combined = set_stdout + list_stdout + read_stdout

            self.assertEqual(set_code, 0, set_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(read_code, 0, read_stderr)
            self.assertEqual(include_code, 0, include_stderr)
            self.assertNotIn(manual_text, default_combined)
            self.assertEqual(json.loads(include_stdout)["result"]["text"], manual_text)


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


def configured_memory_bank_app(temp: str) -> WorkbenchApplicationService:
    app = configured_context_plan_app(temp)
    plan_id = app.list_formal_context_plans("demo")[0]["plan_id"]
    app.enqueue_formal_context_tasks("demo", plan_id)
    preview = app.create_memory_apply_preview("demo")
    app.commit_memory_apply_preview("demo", preview["preview_id"])
    return app


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
