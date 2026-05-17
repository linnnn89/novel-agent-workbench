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
    DraftReviewService,
    ProjectStore,
    RevisionRequestError,
    RevisionRequestService,
    WorkbenchApplicationService,
    audit_project,
    public_project_state,
    read_provider_call_log,
    set_model_role_config,
)
from novel_agent_workbench.chapters import ChapterWorkflowService
from novel_agent_workbench.cli import main


class RevisionRequestServiceTest(unittest.TestCase):
    def test_create_revision_request_after_needs_revision_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            review_id, draft_id = create_review_decision(store, "chapter_001", decision="needs_revision")

            result = RevisionRequestService(store).create_revision_request(review_id)
            artifact = RevisionRequestService(store).read_revision_request(result.revision_request_id)
            chapter = ChapterWorkflowService(store).get_chapter("chapter_001")

            self.assertEqual(result.review_id, review_id)
            self.assertEqual(result.draft_id, draft_id)
            self.assertEqual(artifact["status"], "requested")
            self.assertEqual(artifact["source_decision"]["status"], "needs_revision")
            self.assertEqual(artifact["revision_policy"], "manual_revision_required")
            self.assertEqual(chapter["status"], "revision_requested")
            self.assertEqual(chapter["latest_revision_request_id"], result.revision_request_id)

    def test_revision_request_has_no_confirmed_memory_rag_export_or_provider_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            review_id, draft_id = create_review_decision(store, "chapter_001", decision="needs_revision")
            draft_before = DraftGenerationService(store).read_draft(draft_id)
            calls_before = len(read_provider_call_log(store).get("calls", []))

            RevisionRequestService(store).create_revision_request(review_id)
            draft_after = DraftGenerationService(store).read_draft(draft_id)
            calls_after = len(read_provider_call_log(store).get("calls", []))

            self.assertEqual(draft_before, draft_after)
            self.assertEqual(calls_before, calls_after)
            self.assertEqual(DraftGenerationService(store).list_confirmed_chapters(), [])
            self.assertFalse((store.data_dir / "confirmed_chapters.json").exists())
            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_revision_request_rejects_pending_accepted_blocked_missing_and_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            pending_review = create_review(store, "chapter_001")
            accepted_review, _ = create_review_decision(store, "chapter_002", decision="accepted")
            blocked_review, _ = create_review_decision(store, "chapter_003", decision="blocked")
            needs_revision_review, _ = create_review_decision(store, "chapter_004", decision="needs_revision")
            service = RevisionRequestService(store)

            with self.assertRaises(RevisionRequestError):
                service.create_revision_request(pending_review)
            with self.assertRaises(RevisionRequestError):
                service.create_revision_request(accepted_review)
            with self.assertRaises(RevisionRequestError):
                service.create_revision_request(blocked_review)
            with self.assertRaises(RevisionRequestError):
                service.create_revision_request("missing_review")

            service.create_revision_request(needs_revision_review)
            with self.assertRaises(RevisionRequestError):
                service.create_revision_request(needs_revision_review)

            self.assertEqual(len(service.list_revision_requests()), 1)

    def test_revision_request_public_state_audit_and_artifact_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-revision-secret"})
            review_id, draft_id = create_review_decision(
                store,
                "chapter_001",
                decision="needs_revision",
                prompt="private revision prompt",
            )
            draft = DraftGenerationService(store).read_draft(draft_id)

            result = RevisionRequestService(store).create_revision_request(review_id)
            artifact_text = json.dumps(
                RevisionRequestService(store).read_revision_request(result.revision_request_id),
                ensure_ascii=False,
            )
            state_text = json.dumps(public_project_state(store), ensure_ascii=False)
            audit_text = json.dumps(audit_project(store), ensure_ascii=False)

            self.assertTrue(audit_project(store)["ok"], audit_text)
            self.assertIn("revision_request_count", state_text)
            self.assertNotIn("private revision prompt", artifact_text + state_text + audit_text)
            self.assertNotIn(str(draft["content"]), artifact_text + state_text + audit_text)
            self.assertNotIn("sk-revision-secret", artifact_text + state_text + audit_text)
            self.assertNotIn("MOCK writer", artifact_text + state_text + audit_text)

    def test_revision_request_facade_contract_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")
            app.configure_provider_role("demo", "scorer", provider="mock", model="mock-scorer")
            draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private facade revision prompt")
            review = app.review_draft("demo", draft["draft_id"])
            app.decide_review("demo", review["review_id"], decision="needs_revision", reason_code="manual_fix")

            result = app.create_revision_request("demo", review["review_id"])
            listed = app.list_revision_requests("demo")
            read_back = app.read_revision_request("demo", result["revision_request_id"])
            state = app.project_state("demo")
            result_text = json.dumps(
                {"result": result, "listed": listed, "read": read_back, "state": state},
                ensure_ascii=False,
            )

            self.assertEqual(result["status"], "requested")
            self.assertEqual(len(listed), 1)
            self.assertEqual(read_back["revision_request_id"], result["revision_request_id"])
            self.assertEqual(state["revision_request_count"], 1)
            self.assertEqual(state["latest_chapter"]["status"], "revision_requested")
            self.assertEqual(state["committed_chapter_count"], 0)
            self.assertNotIn("private facade revision prompt", result_text)
            self.assertNotIn("MOCK writer", result_text)

    def test_revision_request_cli_commands_are_metadata_only(self) -> None:
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
                    "private cli revision prompt",
                ]
            )
            draft_id = json.loads(draft_stdout)["result"]["draft_id"]
            _, review_stdout, _ = run_cli(["--projects-root", temp, "review-draft", "demo", draft_id])
            review_id = json.loads(review_stdout)["result"]["review_id"]
            run_cli(
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

            create_code, create_stdout, create_stderr = run_cli(
                ["--projects-root", temp, "create-revision-request", "demo", review_id]
            )
            request_id = json.loads(create_stdout)["result"]["revision_request_id"]
            list_code, list_stdout, list_stderr = run_cli(["--projects-root", temp, "list-revision-requests", "demo"])
            read_code, read_stdout, read_stderr = run_cli(
                ["--projects-root", temp, "read-revision-request", "demo", request_id]
            )

            self.assertEqual(create_code, 0, create_stderr)
            self.assertEqual(list_code, 0, list_stderr)
            self.assertEqual(read_code, 0, read_stderr)
            self.assertEqual(json.loads(list_stdout)["result"][0]["revision_request_id"], request_id)
            self.assertEqual(json.loads(read_stdout)["result"]["status"], "requested")
            combined = create_stdout + list_stdout + read_stdout
            self.assertNotIn("private cli revision prompt", combined)
            self.assertNotIn("MOCK writer", combined)


def configured_store(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    set_model_role_config(store, "scorer", {"provider": "mock", "model": "mock-scorer"})
    return store


def create_review(store: ProjectStore, chapter_id: str, prompt: str = "private revision prompt") -> str:
    draft = DraftGenerationService(store).generate_draft(DraftGenerationRequest(chapter_id=chapter_id, prompt=prompt))
    return DraftReviewService(store).review_draft(draft.draft_id).review_id


def create_review_decision(
    store: ProjectStore,
    chapter_id: str,
    *,
    decision: str,
    prompt: str = "private revision prompt",
) -> tuple[str, str]:
    draft = DraftGenerationService(store).generate_draft(DraftGenerationRequest(chapter_id=chapter_id, prompt=prompt))
    review = DraftReviewService(store).review_draft(draft.draft_id)
    DraftReviewService(store).decide_review(review.review_id, decision=decision, reason_code="manual_fix")
    return review.review_id, draft.draft_id


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
