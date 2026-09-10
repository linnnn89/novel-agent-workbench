import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench import application_service as app_module
from novel_agent_workbench.providers import (
    ProviderError, ProviderResponse, ProviderRequest, ModelRoleConfig,
    OpenAICompatibleProviderClient, read_openai_compatible_stream_response,
)
from novel_agent_workbench.reviews import DraftReviewService
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.storage import ProjectStore


class StreamTests(unittest.TestCase):
    def test_no_retry_after_output(self):
        role = ModelRoleConfig("reviser", "openrouter", "model", "https://example.invalid/v1", "", {})
        client = OpenAICompatibleProviderClient(role, "")
        seen = []
        def interrupted(**kwargs):
            kwargs["request"].stream_callback("partial")
            raise OSError("broken connection")
        with patch("novel_agent_workbench.providers.send_openai_compatible_chat_completion", side_effect=interrupted) as http:
            with self.assertRaises(ProviderError):
                client.generate(ProviderRequest("reviser", "test", stream=True, stream_callback=seen.append))
        self.assertEqual(http.call_count, 1)
        self.assertEqual(seen, ["partial"])

    def test_incomplete_and_error_streams_raise(self):
        first = 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        for suffix in ("", 'data: {"error":{"message":"failed"}}\n\n', 'data: {"choices":[],"error":{"code":500}}\n\n'):
            with self.subTest(suffix=suffix), self.assertRaises(ProviderError):
                read_openai_compatible_stream_response(io.BytesIO((first + suffix).encode()))

    def test_completed_and_truncated_streams(self):
        for reason in ("stop", "length"):
            data = 'data: {"choices":[{"delta":{"content":"text"},"finish_reason":"' + reason + '"}]}\n\ndata: [DONE]\n'
            result = read_openai_compatible_stream_response(io.BytesIO(data.encode()))
            self.assertEqual(result["choices"][0]["finish_reason"], reason)
        # Some compatible services use DONE as their sole completion signal.
        result = read_openai_compatible_stream_response(io.BytesIO(b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n'))
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")


class ReviewTests(unittest.TestCase):
    def test_only_current_complete_review_is_reused(self):
        service = DraftReviewService(MagicMock())
        draft = {"draft_id": "d", "content": "new text"}
        review = {"review_type": "ai", "draft_id": "d", "review_id": "r", "comment": "revise", "source_content_sha256": "old"}
        with patch.object(DraftReviewService, "list_reviews", return_value=[{"draft_id": "d", "review_id": "r"}]), patch.object(DraftReviewService, "read_review", return_value=review), patch.object(DraftGenerationService, "read_draft", return_value=draft):
            self.assertIsNone(service.find_ai_review_for_draft("d"))
            import hashlib
            review["source_content_sha256"] = hashlib.sha256(b"new text").hexdigest()
            self.assertEqual(service.find_ai_review_for_draft("d"), review)
            review["provider"] = {"finish_reason": "length"}
            self.assertIsNone(service.find_ai_review_for_draft("d"))
            review.pop("source_content_sha256")
            review.pop("provider")
            self.assertIsNone(service.find_ai_review_for_draft("d"))


class RefinementIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = app_module.WorkbenchApplicationService.open(self.temp.name)
        self.app.create_project("test")
        self.store = ProjectStore.open(self.temp.name, "test")
        self.drafts = DraftGenerationService(self.store)
        self.original = self.drafts.save_provider_draft_version(
            chapter_id="chapter_1", title="test", content="Original chapter.",
            provider_role="writer", provider="mock", model="mock", finish_reason="stop",
        )
        response = ProviderResponse("Improve the ending.", {}, "mock", "mock", "stop")
        with patch("novel_agent_workbench.reviews.generate_with_provider", return_value=response):
            self.review = DraftReviewService(self.store).ai_review_draft(self.original.draft_id)

    def refine(self, response, **kwargs):
        with patch.object(app_module.WorkbenchApplicationService, "_runtime_store", return_value=self.store), patch.object(app_module, "generate_with_provider", return_value=response) as provider:
            result = self.app.refine_draft_from_ai_review("test", self.original.draft_id, max_tokens=100, **kwargs)
        return result, provider

    def test_truncation_saved_as_new_marked_candidate(self):
        response = ProviderResponse("New partial ending", {}, "mock", "mock", "length")
        result, provider = self.refine(response)
        self.assertTrue(result["output_incomplete"])
        saved = self.drafts.read_draft(result["draft_id"])
        self.assertTrue(saved["output_incomplete"])
        self.assertNotEqual(result["draft_id"], self.original.draft_id)
        self.assertEqual(self.drafts.read_draft(self.original.draft_id)["content"], "Original chapter.")
        request = provider.call_args.args[1]
        self.assertEqual(request.feature_id, "ai_refinement")
        self.assertIn("Original chapter.", request.prompt)
        self.assertIn("Improve the ending.", request.prompt)
        self.assertIn("estimated_input_tokens", saved["request_summary"])

    def test_edited_source_blocks_explicit_old_review(self):
        self.drafts.update_draft_content(self.original.draft_id, text="Edited source")
        with patch.object(app_module.WorkbenchApplicationService, "_runtime_store", return_value=self.store), patch.object(app_module, "generate_with_provider") as provider:
            with self.assertRaises(RuntimeError):
                self.app.refine_draft_from_ai_review("test", self.original.draft_id, review_id=self.review.review_id)
            provider.assert_not_called()
        self.assertIsNone(DraftReviewService(self.store).find_ai_review_for_draft(self.original.draft_id))
        with patch("novel_agent_workbench.reviews.generate_with_provider", return_value=ProviderResponse("New review", {}, "mock", "mock", "stop")):
            fresh = DraftReviewService(self.store).ai_review_draft(self.original.draft_id)
        self.assertNotEqual(fresh.review_id, self.review.review_id)
        self.assertIsNotNone(DraftReviewService(self.store).find_ai_review_for_draft(self.original.draft_id))

    def test_capacity_rejection_before_call(self):
        with patch.object(app_module.WorkbenchApplicationService, "_runtime_store", return_value=self.store), patch.object(app_module, "generate_with_provider") as provider:
            with self.assertRaises(RuntimeError):
                self.app.refine_draft_from_ai_review("test", self.original.draft_id, max_context_tokens=1)
            provider.assert_not_called()

    def test_failed_provider_does_not_save_candidate(self):
        before = len(self.drafts.list_drafts())
        with patch.object(app_module.WorkbenchApplicationService, "_runtime_store", return_value=self.store), patch.object(app_module, "generate_with_provider", side_effect=ProviderError("interrupted", error_type="incomplete_stream")):
            with self.assertRaises(ProviderError):
                self.app.refine_draft_from_ai_review("test", self.original.draft_id)
        self.assertEqual(len(self.drafts.list_drafts()), before)

    def test_reasoning_only_response_does_not_save_empty_candidate(self):
        before = len(self.drafts.list_drafts())
        with self.assertRaises(RuntimeError):
            self.refine(ProviderResponse("<think>reasoning only</think>", {}, "mock", "mock", "stop"))
        self.assertEqual(len(self.drafts.list_drafts()), before)

    def test_complete_response_and_default_output_budget(self):
        with patch.object(app_module.WorkbenchApplicationService, "_runtime_store", return_value=self.store), patch.object(app_module, "generate_with_provider", return_value=ProviderResponse("Complete revision", {}, "mock", "mock", "stop")) as provider:
            result = self.app.refine_draft_from_ai_review("test", self.original.draft_id)
        saved = self.drafts.read_draft(result["draft_id"])
        self.assertFalse(result["output_incomplete"])
        self.assertEqual(saved["request_summary"]["output_token_budget"], provider.call_args.args[1].max_tokens)


class ClassicEntryTests(unittest.TestCase):
    def test_save_failure_blocks_classic_refinement(self):
        from novel_agent_workbench.desktop_app import WorkbenchDesktopApp
        fake = MagicMock()
        fake.current_draft_project_id = "p"
        fake.current_draft_index = 0
        fake.current_draft_ids = ["d"]
        fake.save_current_draft_edit.return_value = False
        with patch("novel_agent_workbench.desktop_app.messagebox.showerror"):
            WorkbenchDesktopApp.refine_current_draft_from_ai_review(fake)
        fake.app.find_ai_review_for_draft.assert_not_called()


class CapacityTests(unittest.TestCase):
    def test_final_input_and_model_output_reservation(self):
        check = app_module.refinement_capacity_check
        config = {"primary_model_ref": "p::m", "model_profiles": {"p::m": {"context_length": 100}}}
        with self.assertRaises(RuntimeError):
            check(config, "x" * 400, "", input_limit=500, max_tokens=10, role="reviser")
        with self.assertRaises(RuntimeError):
            check({}, "x" * 400, "", input_limit=100, max_tokens=10, role="reviser")
        result = check(config, "short", "", input_limit=100, max_tokens=10, role="reviser")
        self.assertEqual(result["model_context_limit"], 100)



if __name__ == "__main__":
    unittest.main()
