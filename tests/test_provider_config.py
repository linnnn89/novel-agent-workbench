from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    ProviderConfigError,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProjectStore,
    configure_provider_role,
    create_provider_client,
    fake_test_model_role,
    generate_with_provider,
    get_model_role_config,
    list_provider_adapters,
    provider_dry_run,
    provider_real_test,
    read_provider_call_log,
    resolve_project_secret,
    set_real_generation_enabled,
    set_project_secret,
    set_model_role_config,
)
from novel_agent_workbench.audit import audit_project
from novel_agent_workbench.drafts import DraftGenerationRequest, DraftGenerationService


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

    def test_fake_connection_passes_with_mock_project_secret_and_never_returns_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.update_secrets({"mock_api_key": "sk-test-secret"})
            role_config = set_model_role_config(
                store,
                "writer",
                {
                    "provider": "mock",
                    "model": "mock-writer",
                    "api_key_ref": "project_secret.mock_api_key",
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

    def test_provider_adapter_registry_keeps_real_adapters_disabled(self) -> None:
        adapters = {item["adapter_id"]: item for item in list_provider_adapters()}

        self.assertTrue(adapters["mock"]["enabled"])
        self.assertFalse(adapters["mock"]["network_allowed"])
        self.assertFalse(adapters["openai_compatible"]["enabled"])
        self.assertFalse(adapters["openai_compatible"]["network_allowed"])
        self.assertFalse(adapters["deepseek"]["enabled"])
        self.assertFalse(adapters["deepseek"]["network_allowed"])
        self.assertFalse(adapters["chutes_openai"]["enabled"])
        self.assertFalse(adapters["chutes_openai"]["network_allowed"])

    def test_resolve_project_secret_reads_only_secrets_local_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-env-secret"}):
                with self.assertRaises(ProviderError) as missing:
                    resolve_project_secret(store, "project_secret.DEEPSEEK_API_KEY")

            self.assertEqual(missing.exception.error_type, "missing_secret")
            store.update_secrets({"DEEPSEEK_API_KEY": "sk-local-secret"})

            self.assertEqual(resolve_project_secret(store, "project_secret.DEEPSEEK_API_KEY"), "sk-local-secret")

    def test_resolve_project_secret_reports_invalid_missing_and_empty_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            store.update_secrets({"empty_key": ""})

            cases = [
                ("sk-raw", "invalid_secret_ref"),
                ("project_secret.missing_key", "missing_secret"),
                ("project_secret.empty_key", "empty_secret"),
            ]
            for api_key_ref, error_type in cases:
                with self.assertRaises(ProviderError) as context:
                    resolve_project_secret(store, api_key_ref)
                self.assertEqual(context.exception.error_type, error_type)

    def test_configure_disabled_provider_role_writes_ref_not_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            secret_state = set_project_secret(store, "deepseek_key", "sk-local-secret")

            role_config = configure_provider_role(
                store,
                "writer",
                provider="deepseek",
                model="deepseek-chat",
                api_key_ref="project_secret.deepseek_key",
                base_url="https://api.deepseek.example/v1",
            )
            result = fake_test_model_role(store, "writer")
            config_text = store.config_path.read_text(encoding="utf-8")

            self.assertEqual(role_config.provider, "deepseek")
            self.assertEqual(role_config.api_key_ref, "project_secret.deepseek_key")
            self.assertEqual(secret_state["masked"], "sk-****cret")
            self.assertEqual(result.error_type, "adapter_disabled")
            self.assertNotIn("sk-local-secret", config_text)
            self.assertIn("sk-local-secret", store.secrets_path.read_text(encoding="utf-8"))

    def test_configure_provider_role_rejects_missing_ref_for_secret_required_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with self.assertRaises(ProviderConfigError):
                configure_provider_role(store, "writer", provider="deepseek", model="deepseek-chat")

    def test_configure_provider_role_rejects_raw_key_in_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with self.assertRaises(ProviderConfigError):
                configure_provider_role(
                    store,
                    "writer",
                    provider="mock",
                    model="mock-writer",
                    settings={"api_key": "sk-raw-secret"},
                )

    def test_disabled_provider_dry_run_returns_safe_openai_summary_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "deepseek_key", "sk-local-secret")
            configure_provider_role(
                store,
                "writer",
                provider="deepseek",
                model="deepseek-chat",
                api_key_ref="project_secret.deepseek_key",
                base_url="https://api.deepseek.example/v1",
            )

            with patch("socket.create_connection", side_effect=AssertionError("network attempted")):
                result = provider_dry_run(
                    store,
                    ProviderRequest(
                        role="writer",
                        prompt="private dry run prompt",
                        system_prompt="private dry run system",
                        temperature=0.3,
                        max_tokens=123,
                        metadata={"private_note": "hidden", "chapter": 1},
                    ),
                )
            result_text = json.dumps(result.to_dict(), ensure_ascii=False)

            self.assertFalse(result.ok)
            self.assertEqual(result.error_type, "adapter_disabled")
            self.assertEqual(result.request_summary["provider"], "deepseek")
            self.assertEqual(result.request_summary["model"], "deepseek-chat")
            self.assertEqual(result.request_summary["base_url_host"], "api.deepseek.example")
            self.assertEqual(result.request_summary["message_count"], 2)
            self.assertEqual(result.request_summary["prompt_chars"], len("private dry run prompt"))
            self.assertEqual(result.request_summary["system_prompt_chars"], len("private dry run system"))
            self.assertEqual(result.request_summary["metadata_keys"], ["chapter", "private_note"])
            self.assertNotIn("private dry run prompt", result_text)
            self.assertNotIn("private dry run system", result_text)
            self.assertNotIn("sk-local-secret", result_text)

    def test_openai_compatible_dry_run_adapter_id_is_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "openai_key", "sk-openai-secret")
            configure_provider_role(
                store,
                "writer",
                provider="openai_compatible",
                model="gpt-compatible-test",
                api_key_ref="project_secret.openai_key",
                base_url="https://gateway.example.test/v1",
            )

            result = provider_dry_run(store, ProviderRequest(role="writer", prompt="safe length only"))

            self.assertEqual(result.error_type, "adapter_disabled")
            self.assertEqual(result.request_summary["provider"], "openai_compatible")
            self.assertEqual(result.request_summary["base_url_host"], "gateway.example.test")

    def test_chutes_openai_dry_run_uses_chutes_host_and_model_without_secret_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "chutes_key", "cpk-test-secret")
            configure_provider_role(
                store,
                "writer",
                provider="chutes_openai",
                model="Qwen/Qwen3-32B-TEE",
                api_key_ref="project_secret.chutes_key",
                base_url="https://llm.chutes.ai/v1",
            )

            result = provider_dry_run(store, ProviderRequest(role="writer", prompt="private chutes prompt"))
            result_text = json.dumps(result.to_dict(), ensure_ascii=False)

            self.assertEqual(result.error_type, "adapter_disabled")
            self.assertEqual(result.request_summary["provider"], "chutes_openai")
            self.assertEqual(result.request_summary["model"], "Qwen/Qwen3-32B-TEE")
            self.assertEqual(result.request_summary["base_url_host"], "llm.chutes.ai")
            self.assertEqual(result.request_summary["prompt_chars"], len("private chutes prompt"))
            self.assertNotIn("private chutes prompt", result_text)
            self.assertNotIn("cpk-test-secret", result_text)

    def test_chutes_real_test_returns_safe_metadata_without_writing_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "chutes_key", "cpk-test-secret")
            configure_provider_role(
                store,
                "writer",
                provider="chutes_openai",
                model="Qwen/Qwen3-32B-TEE",
                api_key_ref="project_secret.chutes_key",
                base_url="https://llm.chutes.ai/v1",
            )
            response_body = {
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            }

            with patch(
                "novel_agent_workbench.providers.urllib.request.urlopen",
                return_value=FakeHttpResponse(200, response_body),
            ):
                result = provider_real_test(
                    store,
                    ProviderRequest(role="writer", prompt="private real test prompt", max_tokens=16, temperature=0),
                )
            result_text = json.dumps(result.to_dict(), ensure_ascii=False)

            self.assertTrue(result.ok)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.provider, "chutes_openai")
            self.assertEqual(result.base_url_host, "llm.chutes.ai")
            self.assertEqual(result.finish_reason, "stop")
            self.assertEqual(result.response_text_chars, 2)
            self.assertEqual(result.usage["total_tokens"], 5)
            self.assertFalse((store.data_dir / "provider_call_log.json").exists())
            self.assertFalse((store.data_dir / "drafts").exists())
            self.assertNotIn("private real test prompt", result_text)
            self.assertNotIn("cpk-test-secret", result_text)
            self.assertNotIn("OK", result_text)

    def test_chutes_real_test_rejects_non_chutes_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})

            with self.assertRaises(ProviderError) as context:
                provider_real_test(store, ProviderRequest(role="writer", prompt="no network"))

            self.assertEqual(context.exception.error_type, "unsupported_provider")

    def test_chutes_generate_requires_explicit_real_generation_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "chutes_key", "cpk-test-secret")
            configure_provider_role(
                store,
                "writer",
                provider="chutes_openai",
                model="Qwen/Qwen3-32B-TEE",
                api_key_ref="project_secret.chutes_key",
                base_url="https://llm.chutes.ai/v1",
            )
            service = DraftGenerationService(store)

            with patch("novel_agent_workbench.providers.urllib.request.urlopen") as urlopen:
                with self.assertRaises(ProviderError) as context:
                    service.generate_draft(
                        DraftGenerationRequest(chapter_id="chapter_001", prompt="private disabled chutes prompt")
                    )

            self.assertEqual(context.exception.error_type, "real_generation_disabled")
            urlopen.assert_not_called()
            self.assertFalse((store.data_dir / "drafts").exists())
            self.assertFalse((store.data_dir / "confirmed_chapters").exists())
            self.assertFalse((store.root / "exports").exists())
            self.assertFalse((store.data_dir / "rag").exists())

    def test_disable_real_generation_can_recover_incomplete_chutes_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update(
                {
                    "provider": "chutes_openai",
                    "model": "Qwen/Qwen3-32B-TEE",
                    "settings": {"real_generation_enabled": True},
                }
            )
            store.write_config(config)

            role_config = set_real_generation_enabled(store, "writer", provider="chutes_openai", enabled=False)

            self.assertFalse(role_config.settings["real_generation_enabled"])
            with self.assertRaises(ProviderConfigError):
                set_real_generation_enabled(store, "writer", provider="chutes_openai", enabled=True)

    def test_chutes_real_generation_writes_draft_only_with_mocked_http(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "chutes_key", "cpk-test-secret")
            configure_provider_role(
                store,
                "writer",
                provider="chutes_openai",
                model="Qwen/Qwen3-32B-TEE",
                api_key_ref="project_secret.chutes_key",
                base_url="https://llm.chutes.ai/v1",
            )
            set_real_generation_enabled(store, "writer", provider="chutes_openai", enabled=True)
            response_body = {
                "choices": [{"message": {"content": "REAL DRAFT CONTENT"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            }
            service = DraftGenerationService(store)

            with patch(
                "novel_agent_workbench.providers.urllib.request.urlopen",
                return_value=FakeHttpResponse(200, response_body),
            ):
                result = service.generate_draft(
                    DraftGenerationRequest(
                        chapter_id="chapter_001",
                        prompt="private real generation prompt",
                        system_prompt="private real generation system",
                        max_tokens=32,
                        temperature=0.2,
                    )
                )
            draft = service.read_draft(result.draft_id)
            log_text = json.dumps(read_provider_call_log(store), ensure_ascii=False)
            draft_text = json.dumps(draft, ensure_ascii=False)

            self.assertEqual(result.provider, "chutes_openai")
            self.assertEqual(draft["content"], "REAL DRAFT CONTENT")
            self.assertEqual(draft["provider"]["usage"]["total_tokens"], 10)
            self.assertIn("REAL DRAFT CONTENT", draft_text)
            self.assertNotIn("private real generation prompt", draft_text)
            self.assertNotIn("private real generation system", draft_text)
            self.assertNotIn("cpk-test-secret", draft_text)
            self.assertNotIn("choices", draft_text)
            self.assertNotIn("REAL DRAFT CONTENT", log_text)
            self.assertNotIn("private real generation prompt", log_text)
            self.assertNotIn("cpk-test-secret", log_text)
            self.assertFalse((store.data_dir / "confirmed_chapters").exists())
            self.assertFalse((store.root / "exports").exists())
            self.assertFalse((store.data_dir / "rag").exists())

    def test_chutes_real_generation_audit_gate_blocks_leaky_provider_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_project_secret(store, "chutes_key", "cpk-test-secret")
            configure_provider_role(
                store,
                "writer",
                provider="chutes_openai",
                model="Qwen/Qwen3-32B-TEE",
                api_key_ref="project_secret.chutes_key",
                base_url="https://llm.chutes.ai/v1",
            )
            set_real_generation_enabled(store, "writer", provider="chutes_openai", enabled=True)
            store.write_json(
                store.data_dir / "provider_call_log.json",
                {"schema_version": 1, "calls": [{"prompt": "private leaked prompt"}]},
            )
            service = DraftGenerationService(store)

            with patch("novel_agent_workbench.providers.urllib.request.urlopen") as urlopen:
                with self.assertRaises(ProviderError) as context:
                    service.generate_draft(
                        DraftGenerationRequest(chapter_id="chapter_001", prompt="private blocked prompt")
                    )

            self.assertEqual(context.exception.error_type, "audit_gate_failed")
            urlopen.assert_not_called()
            self.assertIn("possible_prompt_in_provider_log", {item["code"] for item in audit_project(store)["findings"]})

    def test_provider_dry_run_reports_secret_errors_without_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            config = store.read_config()
            config["model_roles"]["writer"].update(
                {"provider": "deepseek", "model": "deepseek-chat", "api_key_ref": "project_secret.missing_key"}
            )
            config["model_roles"]["scorer"].update(
                {"provider": "deepseek", "model": "deepseek-chat", "api_key_ref": "project_secret.empty_key"}
            )
            config["model_roles"]["reviser"].update(
                {"provider": "deepseek", "model": "deepseek-chat", "api_key_ref": "sk-raw"}
            )
            store.write_config(config)
            store.update_secrets({"empty_key": ""})

            cases = [("writer", "missing_secret"), ("scorer", "empty_secret"), ("reviser", "invalid_secret_ref")]
            for role, error_type in cases:
                result = provider_dry_run(store, ProviderRequest(role=role, prompt="safe length only"))
                self.assertEqual(result.error_type, error_type)
                self.assertEqual(result.request_summary, {})

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

            self.assertEqual(context.exception.error_type, "adapter_disabled")
            self.assertEqual(read_provider_call_log(store)["calls"][0]["status"], "error")

    def test_disabled_provider_no_network_and_no_draft_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            set_model_role_config(store, "writer", {"provider": "deepseek", "model": "deepseek-test"})
            service = DraftGenerationService(store)

            with patch("socket.create_connection", side_effect=AssertionError("network attempted")):
                with self.assertRaises(ProviderError) as context:
                    service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="no network"))

            self.assertEqual(context.exception.error_type, "adapter_disabled")
            self.assertFalse((store.data_dir / "drafts").exists())
            self.assertFalse((store.data_dir / "confirmed_chapters").exists())
            self.assertFalse((store.root / "exports").exists())
            self.assertFalse((store.data_dir / "rag").exists())

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

class FakeHttpResponse:
    def __init__(self, status: int, payload: dict[str, object]) -> None:
        self.status = status
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
