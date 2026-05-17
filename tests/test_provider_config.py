from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    ProviderConfigError,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProjectStore,
    create_provider_client,
    fake_test_model_role,
    generate_with_provider,
    get_model_role_config,
    read_provider_call_log,
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

    def test_provider_request_and_response_are_serializable(self) -> None:
        request = ProviderRequest(role="writer", prompt="draft this", system_prompt="be terse", temperature=0.2)
        response = ProviderResponse(
            text="mock",
            usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            model="mock-small",
            provider="mock",
            finish_reason="stop",
        )

        self.assertEqual(request.to_dict()["role"], "writer")
        self.assertEqual(response.to_dict()["usage"]["total_tokens"], 3)

    def test_mock_provider_generates_for_all_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            for role in ("writer", "scorer", "reviser"):
                set_model_role_config(store, role, {"provider": "mock", "model": f"mock-{role}"})

            responses = [
                generate_with_provider(store, ProviderRequest(role=role, prompt=f"prompt for {role}"))
                for role in ("writer", "scorer", "reviser")
            ]

            self.assertEqual([item.provider for item in responses], ["mock", "mock", "mock"])
            self.assertEqual(len(read_provider_call_log(store)["calls"]), 3)

    def test_unsupported_provider_never_creates_network_client(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_model_role_config(store, "writer", {"provider": "deepseek", "model": "deepseek-test"})

            with self.assertRaises(ProviderError) as context:
                generate_with_provider(store, ProviderRequest(role="writer", prompt="do not call network"))

            self.assertEqual(context.exception.error_type, "unsupported_provider")
            self.assertEqual(read_provider_call_log(store)["calls"][0]["status"], "error")

    def test_mock_provider_reports_missing_model_and_secret_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update({"provider": "mock", "model": ""})
            config["model_roles"]["scorer"].update(
                {"provider": "mock", "model": "mock-scorer", "settings": {"require_api_key_ref": True}}
            )
            store.write_config(config)

            with self.assertRaises(ProviderError) as missing_model:
                create_provider_client(store, "writer")
            with self.assertRaises(ProviderError) as missing_secret_ref:
                generate_with_provider(store, ProviderRequest(role="scorer", prompt="score this"))

            self.assertEqual(missing_model.exception.error_type, "missing_model")
            self.assertEqual(missing_secret_ref.exception.error_type, "missing_secret_ref")

    def test_mock_provider_can_simulate_rate_limit_timeout_and_invalid_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})

            for error_type in ("rate_limit", "timeout", "invalid_request"):
                with self.assertRaises(ProviderError) as context:
                    generate_with_provider(
                        store,
                        ProviderRequest(
                            role="writer",
                            prompt="simulate",
                            metadata={"simulate_error": error_type},
                        ),
                    )
                self.assertEqual(context.exception.error_type, error_type)

    def test_provider_call_log_excludes_prompt_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.update_secrets({"mock_key": "sk-test-secret"})
            set_model_role_config(
                store,
                "writer",
                {
                    "provider": "mock",
                    "model": "mock-writer",
                    "api_key_ref": "project_secret.mock_key",
                },
            )

            generate_with_provider(store, ProviderRequest(role="writer", prompt="secret scene prompt"))
            log_text = json.dumps(read_provider_call_log(store), ensure_ascii=False)

            self.assertIn('"prompt_chars"', log_text)
            self.assertNotIn("secret scene prompt", log_text)
            self.assertNotIn("sk-test-secret", log_text)

    def test_checkpoint_excludes_provider_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.update_secrets({"mock_key": "sk-test-secret"})
            set_model_role_config(
                store,
                "writer",
                {
                    "provider": "mock",
                    "model": "mock-writer",
                    "api_key_ref": "project_secret.mock_key",
                },
            )
            generate_with_provider(store, ProviderRequest(role="writer", prompt="checkpoint prompt"))

            checkpoint = store.create_checkpoint(label="provider_log")

            with zipfile.ZipFile(Path(checkpoint["path"]), "r") as archive:
                names = set(archive.namelist())
                content = "\n".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in names
                    if name.endswith(".json")
                )

            self.assertIn("data/provider_call_log.json", names)
            self.assertNotIn("data/secrets.local.json", names)
            self.assertNotIn("sk-test-secret", content)
            self.assertNotIn("checkpoint prompt", content)


if __name__ == "__main__":
    unittest.main()
