from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench.cli import main


class CliTest(unittest.TestCase):
    def test_smoke_command_can_generate_and_commit_without_prompt_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "smoke",
                    "demo",
                    "--title",
                    "Demo Novel",
                    "--chapter-id",
                    "chapter_001",
                    "--chapter-title",
                    "Opening",
                    "--prompt",
                    "private cli prompt",
                    "--commit",
                ]
            )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertEqual(payload["result"]["project"]["project_id"], "demo")
            self.assertEqual(payload["result"]["state"]["committed_chapter_count"], 1)
            self.assertNotIn("private cli prompt", stdout)
            self.assertEqual(stderr, "")

    def test_generate_command_reports_error_without_creating_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "no configured writer",
                ]
            )
            state_code, state_stdout, _ = run_cli(["--projects-root", temp, "state", "demo"])
            error_payload = json.loads(stderr)
            state_payload = json.loads(state_stdout)

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(error_payload["error_type"], "ProviderError")
            self.assertEqual(state_code, 0)
            self.assertEqual(state_payload["result"]["draft_count"], 0)

    def test_split_commands_create_generate_commit_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(run_cli(["--projects-root", temp, "create-project", "demo"])[0], 0)
            self.assertEqual(run_cli(["--projects-root", temp, "configure-mock-writer", "demo"])[0], 0)
            code, stdout, _ = run_cli(
                [
                    "--projects-root",
                    temp,
                    "generate-draft",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "draft by split commands",
                ]
            )
            draft_id = json.loads(stdout)["result"]["draft_id"]
            commit_code, commit_stdout, _ = run_cli(["--projects-root", temp, "commit-draft", "demo", draft_id])
            list_code, list_stdout, _ = run_cli(["--projects-root", temp, "list-confirmed", "demo"])

            self.assertEqual(code, 0)
            self.assertEqual(commit_code, 0)
            self.assertEqual(json.loads(commit_stdout)["result"]["chapter_id"], "chapter_001")
            self.assertEqual(list_code, 0)
            self.assertEqual(len(json.loads(list_stdout)["result"]), 1)

    def test_audit_project_checks_smoke_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            smoke_code, _, smoke_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "smoke",
                    "demo",
                    "--chapter-id",
                    "chapter_001",
                    "--prompt",
                    "private audit cli prompt",
                    "--commit",
                ]
            )
            audit_code, audit_stdout, audit_stderr = run_cli(["--projects-root", temp, "audit-project", "demo"])
            payload = json.loads(audit_stdout)

            self.assertEqual(smoke_code, 0, smoke_stderr)
            self.assertEqual(audit_code, 0, audit_stderr)
            self.assertTrue(payload["result"]["ok"], audit_stdout)
            self.assertNotIn("private audit cli prompt", audit_stdout)

    def test_provider_status_reports_mock_writer_without_secret_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "configure-mock-writer", "demo"])

            code, stdout, stderr = run_cli(["--projects-root", temp, "provider-status", "demo", "writer"])
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertTrue(payload["result"]["ok"])
            self.assertEqual(payload["result"]["provider"], "mock")
            self.assertFalse(payload["result"]["network_allowed"])

    def test_provider_status_reports_disabled_provider_no_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            config_path = Path(temp) / "demo" / "data" / "config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["model_roles"]["writer"].update({"provider": "deepseek", "model": "deepseek-chat"})
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            code, stdout, stderr = run_cli(["--projects-root", temp, "provider-status", "demo", "writer"])
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertFalse(payload["result"]["ok"])
            self.assertEqual(payload["result"]["error_type"], "missing_secret_ref")
            self.assertFalse(payload["result"]["network_allowed"])

    def test_provider_status_with_secret_ref_does_not_print_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            data_dir = Path(temp) / "demo" / "data"
            config_path = data_dir / "config.json"
            secrets_path = data_dir / "secrets.local.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["model_roles"]["writer"].update(
                {"provider": "deepseek", "model": "deepseek-chat", "api_key_ref": "project_secret.deepseek_key"}
            )
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            secrets_path.write_text(json.dumps({"deepseek_key": "sk-cli-secret"}, ensure_ascii=False), encoding="utf-8")

            code, stdout, stderr = run_cli(["--projects-root", temp, "provider-status", "demo", "writer"])
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertFalse(payload["result"]["ok"])
            self.assertEqual(payload["result"]["error_type"], "adapter_disabled")
            self.assertNotIn("sk-cli-secret", stdout)

    def test_configure_provider_role_and_set_secret_cli_do_not_print_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            secret_code, secret_stdout, secret_stderr = run_cli(
                ["--projects-root", temp, "set-project-secret", "demo", "deepseek_key", "--value", "sk-cli-secret"]
            )
            config_code, config_stdout, config_stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "writer",
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-chat",
                    "--api-key-ref",
                    "project_secret.deepseek_key",
                ]
            )
            status_code, status_stdout, status_stderr = run_cli(
                ["--projects-root", temp, "provider-status", "demo", "writer"]
            )
            config_path = Path(temp) / "demo" / "data" / "config.json"

            self.assertEqual(secret_code, 0, secret_stderr)
            self.assertEqual(config_code, 0, config_stderr)
            self.assertEqual(status_code, 0, status_stderr)
            self.assertNotIn("sk-cli-secret", secret_stdout)
            self.assertNotIn("sk-cli-secret", config_stdout)
            self.assertNotIn("sk-cli-secret", status_stdout)
            self.assertNotIn("sk-cli-secret", config_path.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(status_stdout)["result"]["error_type"], "adapter_disabled")

    def test_configure_provider_role_cli_rejects_missing_secret_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "writer",
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-chat",
                ]
            )
            payload = json.loads(stderr)

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertEqual(payload["error_type"], "ProviderConfigError")

    def test_provider_dry_run_cli_returns_safe_summary_without_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "set-project-secret", "demo", "deepseek_key", "--value", "sk-cli-secret"])
            run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "writer",
                    "--provider",
                    "deepseek",
                    "--model",
                    "deepseek-chat",
                    "--api-key-ref",
                    "project_secret.deepseek_key",
                    "--base-url",
                    "https://api.deepseek.example/v1",
                ]
            )

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "provider-dry-run",
                    "demo",
                    "writer",
                    "--prompt",
                    "private cli dry run prompt",
                    "--system-prompt",
                    "private cli dry run system",
                    "--temperature",
                    "0.25",
                    "--max-tokens",
                    "200",
                ]
            )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertEqual(payload["result"]["error_type"], "adapter_disabled")
            self.assertEqual(payload["result"]["request_summary"]["base_url_host"], "api.deepseek.example")
            self.assertEqual(payload["result"]["request_summary"]["prompt_chars"], len("private cli dry run prompt"))
            self.assertNotIn("private cli dry run prompt", stdout)
            self.assertNotIn("private cli dry run system", stdout)
            self.assertNotIn("sk-cli-secret", stdout)

    def test_provider_dry_run_cli_reports_missing_secret_without_prompt_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            config_path = Path(temp) / "demo" / "data" / "config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["model_roles"]["writer"].update(
                {"provider": "deepseek", "model": "deepseek-chat", "api_key_ref": "project_secret.missing_key"}
            )
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "provider-dry-run",
                    "demo",
                    "writer",
                    "--prompt",
                    "private missing secret prompt",
                ]
            )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertEqual(payload["result"]["error_type"], "missing_secret")
            self.assertEqual(payload["result"]["request_summary"], {})
            self.assertNotIn("private missing secret prompt", stdout)

    def test_chutes_provider_dry_run_cli_is_safe_and_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "set-project-secret", "demo", "chutes_key", "--value", "cpk-cli-secret"])
            run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "writer",
                    "--provider",
                    "chutes_openai",
                    "--model",
                    "Qwen/Qwen3-32B-TEE",
                    "--api-key-ref",
                    "project_secret.chutes_key",
                    "--base-url",
                    "https://llm.chutes.ai/v1",
                ]
            )

            code, stdout, stderr = run_cli(
                [
                    "--projects-root",
                    temp,
                    "provider-dry-run",
                    "demo",
                    "writer",
                    "--prompt",
                    "private chutes cli prompt",
                    "--temperature",
                    "0.7",
                    "--max-tokens",
                    "1024",
                ]
            )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertEqual(payload["result"]["error_type"], "adapter_disabled")
            self.assertEqual(payload["result"]["request_summary"]["provider"], "chutes_openai")
            self.assertEqual(payload["result"]["request_summary"]["model"], "Qwen/Qwen3-32B-TEE")
            self.assertEqual(payload["result"]["request_summary"]["base_url_host"], "llm.chutes.ai")
            self.assertNotIn("private chutes cli prompt", stdout)
            self.assertNotIn("cpk-cli-secret", stdout)

    def test_chutes_provider_real_test_cli_is_safe_with_mocked_http(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_cli(["--projects-root", temp, "create-project", "demo"])
            run_cli(["--projects-root", temp, "set-project-secret", "demo", "chutes_key", "--value", "cpk-cli-secret"])
            run_cli(
                [
                    "--projects-root",
                    temp,
                    "configure-provider-role",
                    "demo",
                    "writer",
                    "--provider",
                    "chutes_openai",
                    "--model",
                    "Qwen/Qwen3-32B-TEE",
                    "--api-key-ref",
                    "project_secret.chutes_key",
                    "--base-url",
                    "https://llm.chutes.ai/v1",
                ]
            )

            with patch(
                "novel_agent_workbench.providers.urllib.request.urlopen",
                return_value=FakeHttpResponse(
                    200,
                    {
                        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
                    },
                ),
            ):
                code, stdout, stderr = run_cli(
                    [
                        "--projects-root",
                        temp,
                        "provider-real-test",
                        "demo",
                        "writer",
                        "--prompt",
                        "private real cli prompt",
                    ]
                )
            payload = json.loads(stdout)

            self.assertEqual(code, 0, stderr)
            self.assertTrue(payload["result"]["ok"])
            self.assertEqual(payload["result"]["status_code"], 200)
            self.assertEqual(payload["result"]["response_text_chars"], 2)
            self.assertNotIn("private real cli prompt", stdout)
            self.assertNotIn("cpk-cli-secret", stdout)
            self.assertNotIn("OK", stdout)


def run_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


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
