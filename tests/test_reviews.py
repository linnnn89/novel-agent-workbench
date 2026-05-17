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
    DraftGenerationRequest,
    DraftGenerationService,
    DraftReviewError,
    DraftReviewService,
    ProjectStore,
    WorkbenchApplicationService,
    audit_project,
    public_project_state,
    read_provider_call_log,
    set_model_role_config,
)
from novel_agent_workbench.chapters import ChapterWorkflowService
from novel_agent_workbench.cli import main


class DraftReviewServiceTest(unittest.TestCase):
    def test_review_draft_creates_metadata_only_review_and_marks_chapter_review_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            draft_service = DraftGenerationService(store)
            review_service = DraftReviewService(store)
            draft_result = draft_service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", title="Opening", prompt="private review prompt")
            )
            draft = draft_service.read_draft(draft_result.draft_id)

            review_result = review_service.review_draft(draft_result.draft_id)
            review = review_service.read_review(review_result.review_id)
            chapter = ChapterWorkflowService(store).get_chapter("chapter_001")
            review_text = json.dumps(review, ensure_ascii=False)

            self.assertEqual(review["status"], "review_ready")
            self.assertEqual(review["draft_id"], draft_result.draft_id)
            self.assertEqual(review["chapter_id"], "chapter_001")
            self.assertEqual(review["provider"]["role"], "scorer")
            self.assertEqual(review["provider"]["provider"], "mock")
            self.assertIn("overall", review["scores"])
            self.assertEqual(chapter["status"], "review_ready")
            self.assertEqual(chapter["latest_review_id"], review_result.review_id)
            self.assertEqual(chapter["latest_draft_id"], draft_result.draft_id)
            self.assertNotIn("private review prompt", review_text)
            self.assertNotIn(str(draft["content"]), review_text)

    def test_review_does_not_create_confirmed_memory_rag_or_export_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            draft_service = DraftGenerationService(store)
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            draft_result = draft_service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private review side effect prompt")
            )

            DraftReviewService(store).review_draft(draft_result.draft_id)

            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.data_dir / "confirmed_chapters.json").exists())
            self.assertFalse((store.data_dir / "confirmed_chapters").exists())
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.data_dir / "rag.json").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_review_and_provider_log_exclude_draft_content_prompt_and_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-review-secret"})
            draft_service = DraftGenerationService(store)
            draft_result = draft_service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private scorer prompt")
            )
            draft = draft_service.read_draft(draft_result.draft_id)

            review_result = DraftReviewService(store).review_draft(draft_result.draft_id)
            combined = json.dumps(
                {
                    "review": DraftReviewService(store).read_review(review_result.review_id),
                    "reviews_index": DraftReviewService(store).list_reviews(),
                    "provider_log": read_provider_call_log(store),
                },
                ensure_ascii=False,
            )

            self.assertNotIn("private scorer prompt", combined)
            self.assertNotIn(str(draft["content"]), combined)
            self.assertNotIn("sk-review-secret", combined)
            self.assertNotIn('"prompt"', combined)

    def test_review_missing_draft_and_duplicate_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            review_service = DraftReviewService(store)
            draft_result = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private duplicate prompt")
            )

            with self.assertRaises(Exception):
                review_service.review_draft("missing_draft")
            first = review_service.review_draft(draft_result.draft_id)
            with self.assertRaises(DraftReviewError):
                review_service.review_draft(draft_result.draft_id)

            self.assertEqual(len(review_service.list_reviews()), 1)
            self.assertEqual(review_service.list_reviews()[0]["review_id"], first.review_id)

    def test_review_blocked_chapter_is_rejected_without_new_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            draft_result = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private blocked prompt")
            )
            ChapterWorkflowService(store).record_error(
                "chapter_001",
                stage="manual_block",
                error_type="blocked_for_test",
                message="metadata only",
            )

            with self.assertRaises(DraftReviewError):
                DraftReviewService(store).review_draft(draft_result.draft_id)

            self.assertEqual(DraftReviewService(store).list_reviews(), [])

    def test_public_state_and_audit_do_not_expose_review_sensitive_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")
            app.configure_provider_role("demo", "scorer", provider="mock", model="mock-scorer")
            draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private state review prompt")
            review = app.review_draft("demo", draft["draft_id"])

            state = app.project_state("demo")
            audit = app.audit_project("demo")
            state_text = json.dumps(state, ensure_ascii=False)
            audit_text = json.dumps(audit, ensure_ascii=False)

            self.assertEqual(state["review_count"], 1)
            self.assertEqual(state["latest_review"]["review_id"], review["review_id"])
            self.assertTrue(audit["ok"], audit_text)
            self.assertNotIn("private state review prompt", state_text + audit_text)
            self.assertNotIn("MOCK writer", state_text + audit_text)

    def test_decide_review_accepts_without_commit_or_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            draft_service = DraftGenerationService(store)
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            draft_result = draft_service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private accept prompt")
            )
            review_service = DraftReviewService(store)
            review_result = review_service.review_draft(draft_result.draft_id)

            decision = review_service.decide_review(
                review_result.review_id,
                decision="accepted",
                reason_code="manual_pass",
            )
            review = review_service.read_review(review_result.review_id)
            chapter = ChapterWorkflowService(store).get_chapter("chapter_001")

            self.assertEqual(decision.decision, "accepted")
            self.assertEqual(review["decision"]["status"], "accepted")
            self.assertEqual(chapter["status"], "review_accepted")
            self.assertEqual(chapter["latest_review_decision"]["decision"], "accepted")
            self.assertEqual(draft_service.list_confirmed_chapters(), [])
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_decide_review_needs_revision_and_blocked_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            first = create_review(store, "chapter_001", "private needs revision prompt")
            second = create_review(store, "chapter_002", "private blocked decision prompt")
            service = DraftReviewService(store)

            service.decide_review(first.review_id, decision="needs_revision", reason_code="tone_fix")
            service.decide_review(second.review_id, decision="blocked", reason_code="manual_block")
            first_chapter = ChapterWorkflowService(store).get_chapter("chapter_001")
            second_chapter = ChapterWorkflowService(store).get_chapter("chapter_002")
            public_text = json.dumps(public_project_state(store), ensure_ascii=False)
            audit_text = json.dumps(audit_project(store), ensure_ascii=False)

            self.assertEqual(first_chapter["status"], "needs_revision")
            self.assertEqual(second_chapter["status"], "blocked")
            self.assertEqual(second_chapter["error_summary"]["stage"], "review_decision")
            self.assertNotIn("private needs revision prompt", public_text + audit_text)
            self.assertNotIn("private blocked decision prompt", public_text + audit_text)

    def test_decide_review_rejects_duplicate_invalid_decision_and_unsafe_reason_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            review = create_review(store, "chapter_001", "private decision prompt")
            service = DraftReviewService(store)

            service.decide_review(review.review_id, decision="accepted")
            with self.assertRaises(DraftReviewError):
                service.decide_review(review.review_id, decision="needs_revision")
            with self.assertRaises(DraftReviewError):
                service.decide_review("missing_review", decision="accepted")
            second = create_review(store, "chapter_002", "private invalid decision prompt")
            with self.assertRaises(DraftReviewError):
                service.decide_review(second.review_id, decision="maybe")
            with self.assertRaises(DraftReviewError):
                service.decide_review(second.review_id, decision="accepted", reason_code="unsafe reason")

    def test_decide_review_missing_draft_artifact_leaves_review_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private missing artifact prompt")
            )
            review = DraftReviewService(store).review_draft(draft.draft_id)
            draft_path = Path(draft.path)
            draft_path.rename(draft_path.with_suffix(".json.trash"))

            with self.assertRaises(Exception):
                DraftReviewService(store).decide_review(review.review_id, decision="accepted")
            review_artifact = DraftReviewService(store).read_review(review.review_id)
            review_index = DraftReviewService(store).list_reviews()[0]

            self.assertEqual(review_artifact["decision"]["status"], "pending")
            self.assertEqual(review_index["decision"]["status"], "pending")

    def test_review_cli_commands_are_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "configure-mock-writer", "demo"])
            run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "scorer",
                    "--provider",
                    "mock",
                    "--model",
                    "mock-scorer",
                ]
            )
            _, draft_stdout, _ = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "private cli review prompt",
                ]
            )
            draft_id = json.loads(draft_stdout)["result"]["draft_id"]
            review_code, review_stdout, review_stderr = run_cli(["--projects-root", temp, "review-draft", "demo", draft_id])
            review_id = json.loads(review_stdout)["result"]["review_id"]
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-reviews", "demo"])
            read_code, read_stdout, read_stderr = run_cli(["--projects-root", temp, "read-review", "demo", review_id])

            self.assertEqual(review_code, 0, review_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(read_code, 0, read_stderr)
            self.assertEqual(json.loads(list_stdout)["result"][0]["review_id"], review_id)
            self.assertEqual(json.loads(read_stdout)["result"]["status"], "review_ready")
            combined_stdout = review_stdout + list_stdout + read_stdout
            self.assertNotIn("private cli review prompt", combined_stdout)
            self.assertNotIn("MOCK writer", combined_stdout)

    def test_decide_review_cli_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "configure-mock-writer", "demo"])
            run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "scorer",
                    "--provider",
                    "mock",
                    "--model",
                    "mock-scorer",
                ]
            )
            _, draft_stdout, _ = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "private cli decision prompt",
                ]
            )
            draft_id = json.loads(draft_stdout)["result"]["draft_id"]
            _, review_stdout, _ = run_cli(["--projects-root", temp, "review-draft", "demo", draft_id])
            review_id = json.loads(review_stdout)["result"]["review_id"]

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "decide-review",
                    "demo",
                    review_id,
                    "--decision",
                    "needs_revision",
                    "--reason-code",
                    "manual_fix",
                ]
            )
            status_code, status_stdout, status_stderr = run_cli(
                ["--projects-root", temp, "chapter-status", "demo", "chapter_001"]
            )

            self.assertEqual(code, 0, stderr)
            self.assertEqual(status_code, 0, status_stderr)
            self.assertEqual(json.loads(stdout)["result"]["decision"], "needs_revision")
            self.assertEqual(json.loads(status_stdout)["result"]["status"], "needs_revision")
            self.assertNotIn("private cli decision prompt", stdout + status_stdout)
            self.assertNotIn("MOCK writer", stdout + status_stdout)


def configured_store(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    set_model_role_config(store, "scorer", {"provider": "mock", "model": "mock-scorer"})
    return store


def create_review(store: ProjectStore, chapter_id: str, prompt: str):
    draft = DraftGenerationService(store).generate_draft(DraftGenerationRequest(chapter_id=chapter_id, prompt=prompt))
    return DraftReviewService(store).review_draft(draft.draft_id)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
