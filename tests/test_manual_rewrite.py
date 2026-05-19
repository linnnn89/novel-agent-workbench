from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    DraftGenerationRequest,
    DraftGenerationService,
    ManualRewriteTaskError,
    ManualRewriteTaskService,
    ProjectStore,
    RevisionRequestService,
    SelfStyleBaselineService,
    WorkbenchApplicationService,
    audit_project,
    set_model_role_config,
)
from novel_agent_workbench.cli import main


class ManualRewriteTaskServiceTest(unittest.TestCase):
    def test_create_task_requires_needs_manual_rewrite_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)

            result = service.create_task_from_style_suggestion(suggestion_id)
            artifact = service.read_task(result.task_id)
            text = Path(result.path).read_text(encoding="utf-8")

            self.assertEqual(result.status, "pending")
            self.assertEqual(result.suggestion_id, suggestion_id)
            self.assertEqual(artifact["source_decision"]["status"], "needs_manual_rewrite")
            self.assertEqual(artifact["workspace_policy"]["auto_generate_draft"], False)
            self.assertNotIn("private manual rewrite prompt", text)
            self.assertNotIn("人工改写测试草稿", text)
            self.assertFalse(artifact["safety"]["provider_called"])
            self.assertFalse(artifact["safety"]["auto_generate_draft"])
            self.assertFalse(artifact["safety"]["auto_commit"])

    def test_accepted_or_ignored_suggestion_cannot_create_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, accepted_id = configured_store_with_style_suggestion(temp, decision="accepted")
            service = ManualRewriteTaskService(store)

            with self.assertRaises(ManualRewriteTaskError):
                service.create_task_from_style_suggestion(accepted_id)

        with tempfile.TemporaryDirectory() as temp:
            store, ignored_id = configured_store_with_style_suggestion(temp, decision="ignored")
            service = ManualRewriteTaskService(store)

            with self.assertRaises(ManualRewriteTaskError):
                service.create_task_from_style_suggestion(ignored_id)

    def test_duplicate_task_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)

            service.create_task_from_style_suggestion(suggestion_id)

            with self.assertRaises(ManualRewriteTaskError):
                service.create_task_from_style_suggestion(suggestion_id)

    def test_mark_task_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)
            task = service.create_task_from_style_suggestion(suggestion_id)

            marked = service.mark_task(task.task_id, status="in_progress", reason_code="started")
            done = service.mark_task(task.task_id, status="done")
            artifact = service.read_task(task.task_id)

            self.assertEqual(marked.status, "in_progress")
            self.assertEqual(done.status, "done")
            self.assertEqual(artifact["status"], "done")
            self.assertEqual(service.list_tasks(status="done")[0]["task_id"], task.task_id)

    def test_submit_manual_rewrite_draft_creates_new_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)
            task = service.create_task_from_style_suggestion(suggestion_id)
            draft_service = DraftGenerationService(store)
            source_draft = draft_service.read_draft(task.draft_id)
            draft_count_before = len(draft_service.list_drafts())
            confirmed_before = len(draft_service.list_confirmed_chapters())
            revision_before = len(RevisionRequestService(store).list_revision_requests())
            provider_log_before = store.read_json(store.data_dir / "provider_call_log.json", default={})
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")

            result = service.submit_manual_rewrite_draft(task.task_id, text="人工提交的新正文。\n这是显式人工改写版本。")
            submitted = draft_service.read_draft(result.draft_id)
            source_after = draft_service.read_draft(task.draft_id)
            task_after = service.read_task(task.task_id)

            self.assertNotEqual(result.draft_id, task.draft_id)
            self.assertEqual(len(draft_service.list_drafts()), draft_count_before + 1)
            self.assertEqual(submitted["content"], "人工提交的新正文。\n这是显式人工改写版本。")
            self.assertEqual(submitted["manual_rewrite"]["manual_rewrite_task_id"], task.task_id)
            self.assertEqual(submitted["manual_rewrite"]["source_suggestion_id"], suggestion_id)
            self.assertEqual(submitted["manual_rewrite"]["source_check_id"], task.check_id)
            self.assertEqual(submitted["manual_rewrite"]["source_draft_id"], task.draft_id)
            self.assertEqual(source_after["content"], source_draft["content"])
            self.assertEqual(task_after["status"], "done")
            self.assertEqual(task_after["submitted_draft_id"], result.draft_id)
            self.assertEqual(confirmed_before, len(draft_service.list_confirmed_chapters()))
            self.assertEqual(revision_before, len(RevisionRequestService(store).list_revision_requests()))
            self.assertEqual(provider_log_before, store.read_json(store.data_dir / "provider_call_log.json", default={}))
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_submit_manual_rewrite_draft_rejects_empty_skipped_and_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)
            task = service.create_task_from_style_suggestion(suggestion_id)

            with self.assertRaises(ManualRewriteTaskError):
                service.submit_manual_rewrite_draft(task.task_id, text="   ")

            service.mark_task(task.task_id, status="skipped", reason_code="manual_skip")
            with self.assertRaises(ManualRewriteTaskError):
                service.submit_manual_rewrite_draft(task.task_id, text="人工文本")

        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)
            task = service.create_task_from_style_suggestion(suggestion_id)

            service.submit_manual_rewrite_draft(task.task_id, text="人工文本")

            with self.assertRaises(ManualRewriteTaskError):
                service.submit_manual_rewrite_draft(task.task_id, text="第二次人工文本")

    def test_task_has_no_draft_confirmed_memory_rag_export_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)
            draft_count_before = len(DraftGenerationService(store).list_drafts())
            confirmed_before = len(DraftGenerationService(store).list_confirmed_chapters())
            revision_before = len(RevisionRequestService(store).list_revision_requests())
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")

            task = service.create_task_from_style_suggestion(suggestion_id)
            service.mark_task(task.task_id, status="skipped", reason_code="manual_skip")

            self.assertEqual(draft_count_before, len(DraftGenerationService(store).list_drafts()))
            self.assertEqual(confirmed_before, len(DraftGenerationService(store).list_confirmed_chapters()))
            self.assertEqual(revision_before, len(RevisionRequestService(store).list_revision_requests()))
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_audit_rejects_manual_rewrite_task_with_text_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            service = ManualRewriteTaskService(store)
            task = service.create_task_from_style_suggestion(suggestion_id)
            artifact = service.read_task(task.task_id)
            artifact["prompt"] = "should not be stored"
            store.write_json(str(Path(task.path).relative_to(store.root)), artifact)

            audit = audit_project(store)
            codes = {item["code"] for item in audit["findings"]}

            self.assertIn("manual_rewrite_task_text_stored", codes)

    def test_facade_and_cli_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            app = WorkbenchApplicationService.open(Path(temp))
            suggestion_id = app.list_style_suggestions("demo")[0]["suggestion_id"]

            task = app.create_manual_rewrite_task("demo", suggestion_id)
            marked = app.mark_manual_rewrite_task("demo", task["task_id"], status="in_progress", reason_code="started")
            tasks = app.list_manual_rewrite_tasks("demo")
            read = app.read_manual_rewrite_task("demo", task["task_id"])
            state = app.project_state("demo")
            stdout = capture_stdout(
                [
                    "--projects-root",
                    temp,
                    "list-manual-rewrite-tasks",
                    "demo",
                ]
            )
            combined = json.dumps(
                {"task": task, "marked": marked, "tasks": tasks, "read": read, "state": state, "stdout": stdout},
                ensure_ascii=False,
            )

            self.assertEqual(task["suggestion_id"], suggestion_id)
            self.assertEqual(marked["status"], "in_progress")
            self.assertEqual(tasks[0]["task_id"], task["task_id"])
            self.assertEqual(read["task_id"], task["task_id"])
            self.assertEqual(state["manual_rewrite_task_count"], 1)
            self.assertEqual(state["latest_manual_rewrite_task"]["task_id"], task["task_id"])
            self.assertNotIn("private manual rewrite prompt", combined)
            self.assertNotIn("人工改写测试草稿", combined)
            self.assertNotIn("MOCK writer", combined)

    def test_submit_manual_rewrite_draft_facade_and_cli_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            app = WorkbenchApplicationService.open(Path(temp))
            suggestion_id = app.list_style_suggestions("demo")[0]["suggestion_id"]
            task = app.create_manual_rewrite_task("demo", suggestion_id)

            result = app.submit_manual_rewrite_draft(
                "demo",
                task["task_id"],
                text="CLI不可见的新正文。",
            )
            read = app.read_draft("demo", result["draft_id"])
            state = app.project_state("demo")
            second_store, second_suggestion_id = configured_store_with_style_suggestion(
                str(Path(temp) / "second"),
                decision="needs_manual_rewrite",
            )
            second_app = WorkbenchApplicationService.open(Path(temp) / "second")
            second_task = second_app.create_manual_rewrite_task("demo", second_suggestion_id)
            stdout = capture_stdout(
                [
                    "--projects-root",
                    str(Path(temp) / "second"),
                    "submit-manual-rewrite-draft",
                    "demo",
                    second_task["task_id"],
                    "--text",
                    "CLI提交的新正文。",
                ]
            )
            combined = json.dumps({"result": result, "state": state, "stdout": stdout}, ensure_ascii=False)

            self.assertEqual(read["content"], "CLI不可见的新正文。")
            self.assertEqual(state["latest_manual_rewrite_task"]["submitted_draft_id"], result["draft_id"])
            self.assertNotIn("CLI不可见的新正文", combined)
            self.assertNotIn("CLI提交的新正文", stdout)
            self.assertNotIn("private manual rewrite prompt", combined)
            self.assertNotIn("MOCK writer", combined)
            self.assertEqual(len(DraftGenerationService(second_store).list_confirmed_chapters()), 2)


def configured_store_with_style_suggestion(temp: str, *, decision: str) -> tuple[ProjectStore, str]:
    store = configured_store_with_confirmed_chapters(temp)
    style_service = SelfStyleBaselineService(store)
    baseline = style_service.create_baseline()
    draft = DraftGenerationService(store).generate_draft(
        DraftGenerationRequest(chapter_id="chapter_003", prompt="private manual rewrite prompt")
    )
    replace_draft_text(store, draft.draft_id, "人工改写测试草稿。\n这里没有对白，只有连续说明。\n世界规则和背景被缓慢铺开。")
    check = style_service.check_draft_against_baseline(
        draft.draft_id,
        baseline_id=baseline.baseline_id,
        scene_mode="general",
    )
    suggestion = style_service.create_style_suggestion(check.check_id)
    style_service.decide_style_suggestion(
        suggestion.suggestion_id,
        decision=decision,
        reason_code="style_manual",
    )
    return store, suggestion.suggestion_id


def configured_store_with_confirmed_chapters(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    service = DraftGenerationService(store)
    first = service.generate_draft(
        DraftGenerationRequest(chapter_id="chapter_001", title="One", prompt="private baseline prompt one")
    )
    second = service.generate_draft(
        DraftGenerationRequest(chapter_id="chapter_002", title="Two", prompt="private baseline prompt two")
    )
    service.commit_draft(first.draft_id)
    service.commit_draft(second.draft_id)
    replace_confirmed_text(store, "chapter_001", "自有正文第一章。\n“你好。”\n她停了一下，又笑了。")
    replace_confirmed_text(store, "chapter_002", "第二章继续。\n他们在街角聊天：今天要去哪里？")
    return store


def replace_confirmed_text(store: ProjectStore, chapter_id: str, text: str) -> None:
    service = DraftGenerationService(store)
    chapter = service.read_confirmed_chapter(chapter_id)
    chapter["content"] = text
    for item in service.list_confirmed_chapters():
        if item.get("chapter_id") == chapter_id:
            store.write_json(str(item["path"]), chapter)
            return
    raise AssertionError(f"Missing confirmed chapter: {chapter_id}")


def replace_draft_text(store: ProjectStore, draft_id: str, text: str) -> None:
    service = DraftGenerationService(store)
    draft = service.read_draft(draft_id)
    draft["content"] = text
    for item in service.list_drafts():
        if item.get("draft_id") == draft_id:
            store.write_json(str(item["path"]), draft)
            return
    raise AssertionError(f"Missing draft: {draft_id}")


def capture_stdout(argv: list[str]) -> str:
    from io import StringIO
    from unittest.mock import patch

    buffer = StringIO()
    with patch("sys.stdout", buffer):
        code = main(argv)
    if code != 0:
        raise AssertionError(f"CLI failed with exit code {code}: {buffer.getvalue()}")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
