from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import WorkbenchApplicationService, audit_project
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


if __name__ == "__main__":
    unittest.main()
