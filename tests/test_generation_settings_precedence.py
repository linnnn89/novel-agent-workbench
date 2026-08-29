from __future__ import annotations

import tempfile
import unittest

from novel_agent_workbench.application_service import WorkbenchApplicationService


class ProjectGenerationSettingsPrecedenceTests(unittest.TestCase):
    def test_project_sampling_remains_active_with_global_model_roles(self) -> None:
        with tempfile.TemporaryDirectory() as projects_root:
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("story", title="Story")
            app.update_global_generation_settings({"sampling": {"max_tokens": 222}})
            app.update_generation_settings("story", {"sampling": {"max_tokens": 111}})
            app.configure_global_provider_role("writer", provider="mock", model="mock-writer")
            app.configure_global_provider_role("scorer", provider="mock", model="mock-scorer")

            draft = app.generate_draft(
                "story",
                chapter_id="chapter_001",
                title="Chapter 1",
                prompt="Write a short scene.",
            )
            review = app.ai_review_draft("story", draft["draft_id"])
            review_artifact = app.read_review("story", review["review_id"])

            self.assertEqual(111, review_artifact["request_summary"]["max_tokens"])

    def test_project_without_override_uses_latest_global_sampling(self) -> None:
        with tempfile.TemporaryDirectory() as projects_root:
            app = WorkbenchApplicationService.open(projects_root)
            app.create_project("story", title="Story")
            app.update_global_generation_settings({"sampling": {"max_tokens": 222}})
            app.configure_global_provider_role("writer", provider="mock", model="mock-writer")
            app.configure_global_provider_role("scorer", provider="mock", model="mock-scorer")

            draft = app.generate_draft(
                "story",
                chapter_id="chapter_001",
                title="Chapter 1",
                prompt="Write a short scene.",
            )
            review = app.ai_review_draft("story", draft["draft_id"])
            review_artifact = app.read_review("story", review["review_id"])

            self.assertEqual(222, review_artifact["request_summary"]["max_tokens"])

    def test_lm_studio_configuration_keeps_api_key_optional(self) -> None:
        with tempfile.TemporaryDirectory() as projects_root:
            app = WorkbenchApplicationService.open(projects_root)

            role = app.configure_global_provider_role(
                "writer",
                provider="openai_compatible",
                model="local-model",
                base_url="http://127.0.0.1:1234/v1",
            )

            self.assertEqual("", role["api_key_ref"])


if __name__ == "__main__":
    unittest.main()
