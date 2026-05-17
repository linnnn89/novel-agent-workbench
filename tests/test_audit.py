from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import WorkbenchApplicationService, audit_project
from novel_agent_workbench.drafts import DraftGenerationRequest, DraftGenerationService
from novel_agent_workbench.providers import configure_provider_role, set_model_role_config, set_project_secret
from novel_agent_workbench.storage import ProjectStore


class ProjectAuditTest(unittest.TestCase):
    def test_clean_smoke_project_passes_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            app.configure_mock_writer("demo")
            draft = app.generate_draft("demo", chapter_id="chapter_001", prompt="private audit prompt")
            app.commit_draft("demo", draft["draft_id"])

            result = app.audit_project("demo")

            self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False))
            self.assertEqual(result["findings"], [])
            self.assertIn("public_project_state", result["checked_paths"])

    def test_audit_fails_on_plain_secret_in_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["api_key"] = "sk-test-secret"
            store.write_config(config)

            result = audit_project(store)

            self.assertFalse(result["ok"])
            self.assertIn("possible_secret_in_config", {item["code"] for item in result["findings"]})

    def test_audit_fails_on_raw_provider_api_key_in_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update(
                {"provider": "mock", "model": "mock-writer", "settings": {"api_key": "sk-test-secret"}}
            )
            store.write_config(config)

            result = audit_project(store)
            codes = {item["code"] for item in result["findings"]}

            self.assertFalse(result["ok"])
            self.assertIn("raw_provider_api_key_in_config", codes)

    def test_audit_flags_disabled_provider_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update({"provider": "deepseek", "model": "deepseek-chat"})
            store.write_config(config)

            result = audit_project(store)
            codes = {item["code"] for item in result["findings"]}

            self.assertFalse(result["ok"])
            self.assertIn("provider_adapter_disabled", codes)
            self.assertIn("provider_missing_secret_ref", codes)

    def test_audit_flags_missing_provider_secret_without_leaking_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update(
                {"provider": "deepseek", "model": "deepseek-chat", "api_key_ref": "project_secret.deepseek_key"}
            )
            store.write_config(config)

            result = audit_project(store)
            text = json.dumps(result, ensure_ascii=False)

            self.assertFalse(result["ok"])
            self.assertIn("provider_missing_secret", {item["code"] for item in result["findings"]})
            self.assertNotIn("sk-", text)

    def test_audit_after_provider_dry_run_has_disabled_finding_without_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_project("demo")
            store = ProjectStore.open(Path(temp), "demo")
            set_project_secret(store, "deepseek_key", "sk-audit-secret")
            configure_provider_role(
                store,
                "writer",
                provider="deepseek",
                model="deepseek-chat",
                api_key_ref="project_secret.deepseek_key",
                base_url="https://api.deepseek.example/v1",
            )
            app.provider_dry_run("demo", "writer", prompt="private audit dry run prompt")

            result = app.audit_project("demo")
            text = json.dumps(result, ensure_ascii=False)

            self.assertFalse(result["ok"])
            self.assertIn("provider_adapter_disabled", {item["code"] for item in result["findings"]})
            self.assertNotIn("private audit dry run prompt", text)
            self.assertNotIn("sk-audit-secret", text)

    def test_audit_fails_on_prompt_text_in_provider_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_json(
                store.data_dir / "provider_call_log.json",
                {"schema_version": 1, "calls": [{"prompt": "private leaked prompt"}]},
            )

            result = audit_project(store)

            self.assertFalse(result["ok"])
            self.assertIn("possible_prompt_in_provider_log", {item["code"] for item in result["findings"]})

    def test_audit_fails_on_content_in_commit_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.write_json(
                store.data_dir / "commit_log.json",
                {"schema_version": 1, "commits": [{"content": "MOCK writer leaked content"}]},
            )

            result = audit_project(store)

            self.assertFalse(result["ok"])
            self.assertIn("possible_content_in_commit_log", {item["code"] for item in result["findings"]})

    def test_audit_fails_on_orphan_confirmed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            draft = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="draft"))
            store.write_json(
                store.data_dir / "confirmed_chapters" / "chapter_001.json",
                {
                    "schema_version": 1,
                    "chapter_id": "chapter_001",
                    "content": "orphan content",
                    "source_draft_id": draft.draft_id,
                },
            )

            result = audit_project(store)

            self.assertFalse(result["ok"])
            self.assertIn("orphan_confirmed_artifact", {item["code"] for item in result["findings"]})

    def test_audit_fails_on_confirmed_index_when_source_draft_not_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            draft = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="draft"))
            artifact_path = store.data_dir / "confirmed_chapters" / "chapter_001.json"
            store.write_json(
                artifact_path,
                {
                    "schema_version": 1,
                    "chapter_id": "chapter_001",
                    "content": "half commit content",
                    "source_draft_id": draft.draft_id,
                },
            )
            store.write_json(
                store.data_dir / "confirmed_chapters.json",
                {
                    "schema_version": 1,
                    "chapters": [
                        {
                            "chapter_id": "chapter_001",
                            "source_draft_id": draft.draft_id,
                            "path": "data/confirmed_chapters/chapter_001.json",
                        }
                    ],
                },
            )

            result = audit_project(store)
            codes = {item["code"] for item in result["findings"]}

            self.assertFalse(result["ok"])
            self.assertIn("confirmed_source_draft_not_committed", codes)
            self.assertIn("confirmed_without_commit_log", codes)

    def test_audit_is_read_only_for_uninitialized_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")

            result = audit_project(store)

            self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False))
            self.assertFalse(store.root.exists())


def configured_store(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    return store


if __name__ == "__main__":
    unittest.main()
