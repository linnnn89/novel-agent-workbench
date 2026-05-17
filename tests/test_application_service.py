from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import ProviderError, WorkbenchApplicationService


class WorkbenchApplicationServiceTest(unittest.TestCase):
    def test_create_list_state_generate_read_and_commit_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            created = app.create_project("demo", title="Demo Novel")
            app.configure_mock_writer("demo")

            draft = app.generate_draft(
                "demo",
                chapter_id="chapter_001",
                title="Opening",
                prompt="private facade prompt",
                metadata={"private_note": "do not expose"},
            )
            drafts = app.list_drafts("demo")
            read_draft = app.read_draft("demo", draft["draft_id"])
            committed = app.commit_draft("demo", draft["draft_id"])
            confirmed = app.read_confirmed_chapter("demo", "chapter_001")
            state = app.project_state("demo")

            self.assertEqual(created["project_id"], "demo")
            self.assertEqual(app.list_projects()[0]["project_id"], "demo")
            self.assertEqual(len(drafts), 1)
            self.assertEqual(read_draft["status"], "draft")
            self.assertEqual(committed["chapter_id"], "chapter_001")
            self.assertEqual(confirmed["source_draft_id"], draft["draft_id"])
            self.assertEqual(
                set(state),
                {
                    "project_id",
                    "config",
                    "secrets",
                    "draft_count",
                    "committed_chapter_count",
                    "latest_draft",
                    "latest_committed_chapter",
                    "provider_roles",
                },
            )
            self.assertEqual(state["draft_count"], 1)
            self.assertEqual(state["committed_chapter_count"], 1)
            self.assertNotIn("private facade prompt", json.dumps(state, ensure_ascii=False))

    def test_generate_requires_configured_writer_and_does_not_create_draft_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")

            with self.assertRaises(ProviderError):
                app.generate_draft("demo", chapter_id="chapter_001", prompt="no writer")

            self.assertEqual(app.list_drafts("demo"), [])
            self.assertEqual(app.project_state("demo")["draft_count"], 0)

    def test_facade_state_does_not_expose_prompt_content_or_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")
            draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private state prompt")
            app.commit_draft("demo", draft["draft_id"])

            state_text = json.dumps(app.project_state("demo"), ensure_ascii=False)

            self.assertNotIn("private state prompt", state_text)
            self.assertNotIn("MOCK writer", state_text)
            self.assertNotIn("sk-", state_text)

    def test_facade_audit_project_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")

            audit = app.audit_project("demo")

            self.assertEqual(set(audit), {"ok", "project_id", "findings", "checked_paths"})
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))

    def test_provider_status_facade_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")

            result = app.provider_status("demo", "writer")
            adapters = app.list_provider_adapters()

            self.assertTrue(result["ok"])
            self.assertEqual(result["provider"], "mock")
            self.assertFalse(result["network_allowed"])
            self.assertIn("mock", {item["adapter_id"] for item in adapters})

    def test_facade_configures_disabled_provider_with_masked_secret_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")

            secret = app.set_project_secret("demo", "deepseek_key", "sk-facade-secret")
            role = app.configure_provider_role(
                "demo",
                "writer",
                provider="deepseek",
                model="deepseek-chat",
                api_key_ref="project_secret.deepseek_key",
            )
            status = app.provider_status("demo", "writer")
            result_text = json.dumps({"secret": secret, "role": role, "status": status}, ensure_ascii=False)

            self.assertEqual(secret["masked"], "sk-****cret")
            self.assertEqual(role["provider"], "deepseek")
            self.assertEqual(status["error_type"], "adapter_disabled")
            self.assertNotIn("sk-facade-secret", result_text)

    def test_facade_provider_dry_run_is_safe_summary_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.set_project_secret("demo", "deepseek_key", "sk-facade-secret")
            app.configure_provider_role(
                "demo",
                "writer",
                provider="deepseek",
                model="deepseek-chat",
                api_key_ref="project_secret.deepseek_key",
                base_url="https://api.deepseek.example/v1",
            )

            result = app.provider_dry_run(
                "demo",
                "writer",
                prompt="private facade dry run prompt",
                system_prompt="private facade dry run system",
                metadata={"secret_note": "hidden"},
            )
            result_text = json.dumps(result, ensure_ascii=False)

            self.assertEqual(result["error_type"], "adapter_disabled")
            self.assertEqual(result["request_summary"]["base_url_host"], "api.deepseek.example")
            self.assertEqual(result["request_summary"]["metadata_keys"], ["secret_note"])
            self.assertNotIn("private facade dry run prompt", result_text)
            self.assertNotIn("private facade dry run system", result_text)
            self.assertNotIn("sk-facade-secret", result_text)

    def test_facade_enable_disable_real_provider_exposes_flag_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.set_project_secret("demo", "chutes_key", "cpk-facade-secret")
            app.configure_provider_role(
                "demo",
                "writer",
                provider="chutes_openai",
                model="Qwen/Qwen3-32B-TEE",
                api_key_ref="project_secret.chutes_key",
                base_url="https://llm.chutes.ai/v1",
            )

            enabled = app.enable_real_provider("demo", "writer", provider="chutes_openai")
            state = app.project_state("demo")
            disabled = app.disable_real_provider("demo", "writer")
            result_text = json.dumps({"enabled": enabled, "state": state, "disabled": disabled}, ensure_ascii=False)

            self.assertTrue(enabled["settings"]["real_generation_enabled"])
            self.assertTrue(state["provider_roles"]["writer"]["real_generation_enabled"])
            self.assertFalse(disabled["settings"]["real_generation_enabled"])
            self.assertNotIn("cpk-facade-secret", result_text)


if __name__ == "__main__":
    unittest.main()
