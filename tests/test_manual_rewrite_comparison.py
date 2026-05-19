from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from novel_agent_workbench import (  # noqa: E402
    DraftGenerationService,
    ManualRewriteComparisonError,
    ManualRewriteComparisonService,
    ManualRewriteTaskService,
    ProjectStore,
    RevisionRequestService,
    WorkbenchApplicationService,
    audit_project,
)
from novel_agent_workbench.cli import main  # noqa: E402
from test_manual_rewrite import configured_store_with_style_suggestion  # noqa: E402


class ManualRewriteComparisonServiceTest(unittest.TestCase):
    def test_create_comparison_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, task_id, submitted_draft_id = prepared_manual_rewrite_candidate(temp)
            service = ManualRewriteComparisonService(store)

            result = service.create_comparison(task_id)
            artifact = service.read_comparison(result.comparison_id)
            artifact_text = Path(result.path).read_text(encoding="utf-8")
            listed = service.list_comparisons()
            audit = audit_project(store)

            self.assertEqual(result.task_id, task_id)
            self.assertEqual(result.submitted_draft_id, submitted_draft_id)
            self.assertEqual(artifact["structure_metrics"]["delta"]["char_count"], result.char_count_delta)
            self.assertEqual(artifact["decision"]["status"], "pending")
            self.assertIn("char_count", artifact["structure_metrics"]["source_draft"])
            self.assertIn("paragraph_count", artifact["structure_metrics"]["submitted_draft"])
            self.assertEqual(listed[0]["comparison_id"], result.comparison_id)
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn("private manual rewrite prompt", artifact_text)
            self.assertNotIn("人工改写测试草稿", artifact_text)
            self.assertNotIn("人工提交的新正文", artifact_text)
            self.assertNotIn("MOCK writer", artifact_text)
            self.assertNotIn("content", artifact_text.lower())
            self.assertFalse(artifact["safety"]["provider_called"])
            self.assertFalse(artifact["safety"]["auto_commit"])
            self.assertFalse(artifact["safety"]["memory_bank_touched"])

    def test_create_comparison_requires_submitted_draft_and_rejects_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            task = ManualRewriteTaskService(store).create_task_from_style_suggestion(suggestion_id)
            service = ManualRewriteComparisonService(store)

            with self.assertRaises(ManualRewriteComparisonError):
                service.create_comparison(task.task_id)

        with tempfile.TemporaryDirectory() as temp:
            store, task_id, _submitted_draft_id = prepared_manual_rewrite_candidate(temp)
            service = ManualRewriteComparisonService(store)
            service.create_comparison(task_id)

            with self.assertRaises(ManualRewriteComparisonError):
                service.create_comparison(task_id)

    def test_decide_comparison_supports_manual_gate_decisions(self) -> None:
        for decision in ("selected_for_review", "rejected", "needs_more_manual_work"):
            with self.subTest(decision=decision):
                with tempfile.TemporaryDirectory() as temp:
                    store, task_id, _submitted_draft_id = prepared_manual_rewrite_candidate(temp)
                    service = ManualRewriteComparisonService(store)
                    comparison = service.create_comparison(task_id)

                    result = service.decide_comparison(
                        comparison.comparison_id,
                        decision=decision,
                        reason_code="manual_gate",
                    )
                    artifact = service.read_comparison(comparison.comparison_id)
                    listed = service.list_comparisons(status=decision)

                    self.assertEqual(result.decision, decision)
                    self.assertEqual(artifact["status"], decision)
                    self.assertEqual(artifact["decision"]["reason_code"], "manual_gate")
                    self.assertEqual(listed[0]["comparison_id"], comparison.comparison_id)
                    with self.assertRaises(ManualRewriteComparisonError):
                        service.decide_comparison(comparison.comparison_id, decision="rejected")

    def test_comparison_has_no_draft_confirmed_provider_memory_rag_export_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, task_id, _submitted_draft_id = prepared_manual_rewrite_candidate(temp)
            draft_service = DraftGenerationService(store)
            service = ManualRewriteComparisonService(store)
            draft_count_before = len(draft_service.list_drafts())
            confirmed_before = len(draft_service.list_confirmed_chapters())
            revision_before = len(RevisionRequestService(store).list_revision_requests())
            provider_log_before = store.read_json(store.data_dir / "provider_call_log.json", default={})
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")

            comparison = service.create_comparison(task_id)
            service.decide_comparison(comparison.comparison_id, decision="selected_for_review")

            self.assertEqual(draft_count_before, len(draft_service.list_drafts()))
            self.assertEqual(confirmed_before, len(draft_service.list_confirmed_chapters()))
            self.assertEqual(revision_before, len(RevisionRequestService(store).list_revision_requests()))
            self.assertEqual(provider_log_before, store.read_json(store.data_dir / "provider_call_log.json", default={}))
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_audit_rejects_comparison_with_text_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, task_id, _submitted_draft_id = prepared_manual_rewrite_candidate(temp)
            service = ManualRewriteComparisonService(store)
            comparison = service.create_comparison(task_id)
            artifact = service.read_comparison(comparison.comparison_id)
            artifact["prompt"] = "should not be stored"
            store.write_json(str(Path(comparison.path).relative_to(store.root)), artifact)

            audit = audit_project(store)
            codes = {item["code"] for item in audit["findings"]}

            self.assertIn("manual_rewrite_comparison_text_stored", codes)

    def test_facade_cli_and_public_state_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
            app = WorkbenchApplicationService.open(Path(temp))
            task = app.create_manual_rewrite_task("demo", suggestion_id)
            submitted = app.submit_manual_rewrite_draft(
                "demo",
                task["task_id"],
                text="CLI不可见的人工候选正文。",
            )

            comparison = app.compare_manual_rewrite_candidate("demo", task["task_id"])
            decision = app.decide_manual_rewrite_comparison(
                "demo",
                comparison["comparison_id"],
                decision="needs_more_manual_work",
                reason_code="more_work",
            )
            state = app.project_state("demo")
            stdout = capture_stdout(
                [
                    "--projects-root",
                    temp,
                    "read-manual-rewrite-comparison",
                    "demo",
                    comparison["comparison_id"],
                ]
            )
            listed_stdout = capture_stdout(
                [
                    "--projects-root",
                    temp,
                    "list-manual-rewrite-comparisons",
                    "demo",
                    "--status",
                    "needs_more_manual_work",
                ]
            )
            combined = json.dumps(
                {
                    "comparison": comparison,
                    "decision": decision,
                    "state": state,
                    "stdout": stdout,
                    "listed_stdout": listed_stdout,
                },
                ensure_ascii=False,
            )

            self.assertEqual(comparison["submitted_draft_id"], submitted["draft_id"])
            self.assertEqual(decision["decision"], "needs_more_manual_work")
            self.assertEqual(state["manual_rewrite_comparison_count"], 1)
            self.assertEqual(state["latest_manual_rewrite_comparison"]["comparison_id"], comparison["comparison_id"])
            self.assertEqual(len(DraftGenerationService(store).list_confirmed_chapters()), 2)
            self.assertNotIn("CLI不可见的人工候选正文", combined)
            self.assertNotIn("private manual rewrite prompt", combined)
            self.assertNotIn("人工改写测试草稿", combined)
            self.assertNotIn("MOCK writer", combined)
            self.assertNotIn("content", combined.lower())


def prepared_manual_rewrite_candidate(temp: str) -> tuple[ProjectStore, str, str]:
    store, suggestion_id = configured_store_with_style_suggestion(temp, decision="needs_manual_rewrite")
    task_service = ManualRewriteTaskService(store)
    task = task_service.create_task_from_style_suggestion(suggestion_id)
    submitted = task_service.submit_manual_rewrite_draft(
        task.task_id,
        text="人工提交的新正文。\n\n第二段保留人工候选结构。",
    )
    return store, task.task_id, submitted.draft_id


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
