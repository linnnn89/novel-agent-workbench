import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.model_settings import draft_reasoning_effort_from_settings, default_feature_assignment
from novel_agent_workbench.providers import generate_with_provider, ModelRoleConfig, ProviderRequest, v4_flash_0731_thinking_payload, send_openai_compatible_chat_completion

class ReasoningSwitchTests(unittest.TestCase):
    def test_default_and_saved_settings(self):
        self.assertEqual(default_feature_assignment("draft_generation")["reasoning_effort"], "none")
        for value in (None, "", "bad", "none", "low", "high", "max"):
            expected = value if value in ("none", "low", "high", "max") else "none"
            self.assertEqual(draft_reasoning_effort_from_settings({"feature_assignments": {"draft_generation": {"reasoning_effort": value}}}), expected)
        self.assertEqual(draft_reasoning_effort_from_settings({}), "none")

    def test_actual_http_body(self):
        for provider in ("openrouter", "deepseek"):
            role = ModelRoleConfig("writer", provider, "deepseek/deepseek-v4-flash-0731", "https://example.invalid/v1", "", {})
            for effort in ("none", "low", "high", "max"):
                with self.subTest(provider=provider, effort=effort):
                    extra = v4_flash_0731_thinking_payload(role, effort)
                    request = ProviderRequest("writer", "test", stream=False, extra_body=extra)
                    response = MagicMock()
                    response.__enter__.return_value = response
                    response.status = 200
                    response.read.return_value = b'{"choices":[{"message":{"content":"ok"}}]}'
                    with patch("urllib.request.urlopen", return_value=response) as http:
                        send_openai_compatible_chat_completion(role_config=role, request=request, api_key="", timeout_seconds=1)
                    body = json.loads(http.call_args.args[0].data)
                    if provider == "openrouter":
                        expected = {"enabled": False} if effort == "none" else {"enabled": True, "effort": effort}
                        self.assertEqual(body["reasoning"], expected)
                        self.assertNotIn("reasoning_effort", body)
                        self.assertNotIn("thinking", body)
                    else:
                        self.assertEqual(body["thinking"]["type"], "disabled" if effort == "none" else "enabled")
                        if effort == "none": self.assertNotIn("reasoning_effort", body)

    def test_generation_dispatch_to_http(self):
        role = ModelRoleConfig("reviser", "openrouter", "deepseek/deepseek-v4-flash-0731", "https://example.invalid/v1", "", {})
        for feature in ("draft_generation", "ai_refinement", "ai_review", "memory_generation"):
            for effort in ("none", "high"):
                with self.subTest(feature=feature, effort=effort):
                    store = MagicMock()
                    store.read_config.return_value = {"feature_assignments": {"draft_generation": {"reasoning_effort": effort}}}
                    client = MagicMock()
                    client.role_config = role
                    def send(request):
                        send_openai_compatible_chat_completion(role_config=role, request=request, api_key="", timeout_seconds=1)
                        return MagicMock()
                    client.generate.side_effect = send
                    response = MagicMock()
                    response.__enter__.return_value = response
                    response.status = 200
                    response.read.return_value = b'{"choices":[{"message":{"content":"ok"}}]}'
                    with patch("novel_agent_workbench.providers.create_provider_client", return_value=client), patch("novel_agent_workbench.providers.append_provider_call_log"), patch("novel_agent_workbench.providers.provider_call_log_entry", return_value={}), patch("urllib.request.urlopen", return_value=response) as http:
                        generate_with_provider(store, ProviderRequest("reviser", "test", feature_id=feature, stream=False))
                    body = json.loads(http.call_args.args[0].data)
                    if feature in ("draft_generation", "ai_refinement"):
                        expected = {"enabled": False} if effort == "none" else {"enabled": True, "effort": effort}
                        self.assertEqual(body.get("reasoning"), expected)
                    else:
                        self.assertNotIn("reasoning", body)

    def test_unrelated_model(self):
        role = ModelRoleConfig("writer", "openrouter", "other-model", "", "", {})
        self.assertEqual(v4_flash_0731_thinking_payload(role, "none"), {})

if __name__ == "__main__": unittest.main()
