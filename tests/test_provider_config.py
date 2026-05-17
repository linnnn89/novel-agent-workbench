from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    ProviderConfigError,
    ProjectStore,
    fake_test_model_role,
    get_model_role_config,
    set_model_role_config,
)


class ProviderConfigTest(unittest.TestCase):
    def test_default_role_config_is_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            writer = get_model_role_config(store, "writer")
            result = fake_test_model_role(store, "writer")

            self.assertFalse(writer.is_configured())
            self.assertFalse(result.ok)
            self.assertEqual(result.mode, "fake")

    def test_set_model_role_config_persists_without_secret_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            role_config = set_model_role_config(
                store,
                "writer",
                {
                    "provider": "openai_compatible",
                    "model": "test-model",
                    "base_url": "https://example.invalid/v1",
                    "settings": {"temperature": 0.4, "stream": False},
                },
            )

            self.assertTrue(role_config.is_configured())
            self.assertEqual(get_model_role_config(store, "writer").model, "test-model")
            self.assertNotIn("sk-", store.config_path.read_text(encoding="utf-8"))

    def test_raw_api_key_in_role_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with self.assertRaises(ProviderConfigError):
                set_model_role_config(store, "writer", {"api_key": "sk-raw"})

    def test_raw_api_key_ref_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with self.assertRaises(ProviderConfigError):
                set_model_role_config(
                    store,
                    "writer",
                    {"provider": "deepseek", "model": "deepseek-test", "api_key_ref": "sk-raw"},
                )

    def test_fake_connection_reports_missing_project_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update(
                {"provider": "deepseek", "model": "deepseek-test", "api_key_ref": "project_secret.deepseek_api_key"}
            )
            store.write_config(config)

            result = fake_test_model_role(store, "writer")

            self.assertFalse(result.ok)
            self.assertIn("Missing project secret", result.message)
            self.assertNotIn("deepseek_api_key", result.masked_key)

    def test_fake_connection_passes_with_project_secret_and_never_returns_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.update_secrets({"deepseek_api_key": "sk-test-secret"})
            role_config = set_model_role_config(
                store,
                "writer",
                {
                    "provider": "deepseek",
                    "model": "deepseek-test",
                    "api_key_ref": "project_secret.deepseek_api_key",
                },
            )

            result = fake_test_model_role(store, "writer")
            result_text = json.dumps(result.to_dict(), ensure_ascii=False)

            self.assertTrue(role_config.is_configured())
            self.assertTrue(result.ok)
            self.assertTrue(result.has_api_key)
            self.assertEqual(result.masked_key, "sk-****cret")
            self.assertNotIn("sk-test-secret", result_text)
            self.assertNotIn("sk-test-secret", store.config_path.read_text(encoding="utf-8"))

    def test_invalid_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with self.assertRaises(ProviderConfigError):
                get_model_role_config(store, "editor")


if __name__ == "__main__":
    unittest.main()
