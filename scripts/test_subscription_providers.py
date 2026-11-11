"""Two integration contracts using temporary projects and a loopback HTTP server."""
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.model_catalog import ModelCatalogError, commandcode_goat_includes
from novel_agent_workbench.model_settings import default_model_settings_fields
from novel_agent_workbench.providers import ProviderError, ProviderRequest, generate_with_provider
from novel_agent_workbench.task_control import JobCancelled, JobControl, job_scope

GO_MODELS = {"data": [
    {"id": "go-free", "name": "Go Free", "type": "chat", "api": {"chat-completions": {}},
     "limit": {"context": 100000, "output": 10000}, "capabilities": {"temperature": False, "top_p": False}},
    {"id": "messages-only", "type": "chat", "api": {"messages": {}}},
    {"id": "embedding", "type": "embedding", "api": {"chat-completions": {}}},
]}
CMD_MODELS = {"data": [
    {"id": "vendor/goat-model", "name": "GOAT Model", "supported_endpoints": ["/chat/completions"], "context_length": 64000},
    {"id": "vendor/free-model", "name": "Free Model", "supported_endpoints": ["/chat/completions"]},
    {"id": "premium", "name": "Premium", "supported_endpoints": ["/chat/completions"]},
    {"id": "messages-only", "supported_endpoints": ["/messages"]},
    {"id": "responses-only", "supported_endpoints": ["/responses"]},
]}
PLAN = [
    {"slug": "goat-model", "id": "vendor/goat-model", "name": "GOAT Model", "minPlanName": "GOAT"},
    {"slug": "free-model", "id": "vendor/free-model", "name": "Free Model", "minPlanName": "Go"},
    {"slug": "premium", "id": "premium", "name": "Premium", "minPlanName": "Pro"},
]


@contextmanager
def local_provider():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append({"path": self.path, "headers": dict(self.headers)})
            if self.path == "/goat":
                flight = "models:" + json.dumps(state["plan"], separators=(",", ":"))
                body = ("<script>self.__next_f.push([1," + json.dumps(flight) + "])</script>").encode()
                if state.get("bad_plan"):
                    body = b"<html>page format changed</html>"
            else:
                body = json.dumps(state["go"] if self.path == "/go/v1/models" else state["cmd"]).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "headers": dict(self.headers), "body": payload})
            if state.get("post_error"):
                self.send_error(401)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream" if payload.get("stream") else "application/json")
            self.end_headers()
            if payload.get("stream"):
                for chunk in [
                    {"choices": [{"delta": {"reasoning_content": "测试思考"}}]},
                    {"choices": [{"delta": {"content": "本地测试正文。"}, "finish_reason": "stop"}]},
                    {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 8}},
                ]:
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self.wfile.write(json.dumps({"choices": [{"message": {"content": "本地测试正文。"}, "finish_reason": "stop"}]}).encode())

    state = {"go": deepcopy(GO_MODELS), "cmd": deepcopy(CMD_MODELS), "plan": deepcopy(PLAN)}
    requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with patch("novel_agent_workbench.model_catalog.COMMANDCODE_GOAT_PLAN_URL", base + "/goat"):
            yield base, state, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def configure(app, base, profile_id):
    app.upsert_provider_profile(profile_id, display_name=profile_id, adapter=profile_id,
        base_url=base + ("/go/openai/v1" if profile_id == "opencode_go" else "/cmd/v1"))
    app.set_provider_profile_secret(profile_id, "dummy-test-key")
    app.refresh_provider_models(profile_id)


class SubscriptionProviderTests(unittest.TestCase):
    def test_upgrade_catalog_filtering_and_failure_preserves_saved_data(self):
        with tempfile.TemporaryDirectory() as directory, local_provider() as (base, state, requests):
            app = WorkbenchApplicationService.open(Path(directory) / "projects")
            old = {"schema_version": 2, **default_model_settings_fields()}
            for profile_id in ("opencode_go", "commandcode_goat"):
                del old["provider_profiles"][profile_id]
            old["provider_profiles"]["openrouter"]["base_url"] = "https://saved.example/v1"
            old["primary_model_ref"] = "openrouter::saved-model"
            old["model_profiles"] = {"openrouter::saved-model": {"provider_profile_id": "openrouter", "model_id": "saved-model"}}
            app._write_global_settings(old)
            settings = app._read_global_settings()
            self.assertEqual(settings["primary_model_ref"], old["primary_model_ref"])
            self.assertEqual(settings["provider_profiles"]["openrouter"]["base_url"], "https://saved.example/v1")
            self.assertTrue({"opencode_go", "commandcode_goat"} <= settings["provider_profiles"].keys())
            for profile_id in ("opencode_go", "commandcode_goat"):
                configure(app, base, profile_id)
            models = app._read_global_settings()["model_profiles"]
            self.assertEqual({m["model_id"] for m in models.values() if m["provider_profile_id"] == "opencode_go"}, {"go-free"})
            self.assertEqual({m["model_id"] for m in models.values() if m["provider_profile_id"] == "commandcode_goat"},
                             {"vendor/goat-model", "vendor/free-model"})
            self.assertEqual(models["opencode_go::go-free"]["context_length"], 100000)
            self.assertEqual(models["opencode_go::go-free"]["supported_parameters"], ["max_tokens", "stream"])
            self.assertTrue(all(r["headers"].get("Authorization") is None for r in requests if r["path"] == "/goat"))
            self.assertTrue(any(r["path"] == "/go/v1/models" for r in requests))
            for failure in ("bad_plan", "empty_models"):
                with self.subTest(failure=failure):
                    before = [p.read_bytes() for p in (app._global_settings_path(), app._model_catalog_cache_path())]
                    state["bad_plan"] = failure == "bad_plan"
                    state["cmd"] = {"data": []} if failure == "empty_models" else deepcopy(CMD_MODELS)
                    with self.assertRaises(ModelCatalogError):
                        app.refresh_provider_models("commandcode_goat")
                    self.assertEqual(before, [p.read_bytes() for p in (app._global_settings_path(), app._model_catalog_cache_path())])
            state["bad_plan"] = False
            state["cmd"] = {"data": [CMD_MODELS["data"][0]]}
            app.refresh_provider_models("commandcode_goat")
            self.assertFalse(app._read_global_settings()["model_profiles"]["commandcode_goat::vendor/free-model"]["enabled"])
            ambiguous = [{"slug": "goat-model", "minPlanName": "GOAT"}, {"slug": "goat_model", "minPlanName": "Pro"}]
            self.assertFalse(commandcode_goat_includes(ambiguous, {"id": "goat-model"}))
            control = JobControl()
            control.cancel()
            count = len(requests)
            with job_scope(control), self.assertRaises(JobCancelled):
                app.refresh_provider_models("opencode_go")
            self.assertEqual(count, len(requests))

    def test_generation_streaming_headers_sampling_and_model_admission(self):
        with tempfile.TemporaryDirectory() as directory, local_provider() as (base, state, requests):
            app = WorkbenchApplicationService.open(Path(directory) / "projects")
            app.create_project("one")
            app.create_project("two")
            sessions = []
            for profile_id, model_id in (("opencode_go", "go-free"), ("commandcode_goat", "vendor/goat-model")):
                configure(app, base, profile_id)
                app.update_model_assignments(primary_model_ref=profile_id + "::" + model_id, feature_assignments={})
                for project in ("one", "one", "two"):
                    chunks, reasoning = [], []
                    response = generate_with_provider(app._runtime_store(project), ProviderRequest("writer", "隔离测试输入", stream=True,
                        temperature=.7, top_p=.9, presence_penalty=.2, feature_id="memory_generation",
                        stream_callback=chunks.append, reasoning_callback=reasoning.append))
                    self.assertEqual(response.text, "本地测试正文。")
                    self.assertEqual(chunks, ["本地测试正文。"])
                    self.assertEqual(reasoning, ["测试思考"])
                    self.assertEqual(response.usage["completion_tokens"], 8)
                    sent = requests[-1]
                    self.assertEqual(sent["headers"]["Authorization"], "Bearer dummy-test-key")
                    self.assertEqual(sent["headers"]["User-Agent"], "NovelAgentWorkbench/1.0")
                    self.assertEqual(sent["body"]["stream_options"], {"include_usage": True})
                    self.assertNotIn("presence_penalty", sent["body"])
                    if profile_id == "opencode_go":
                        self.assertNotIn("temperature", sent["body"])
                        self.assertNotIn("top_p", sent["body"])
                        sessions.append(sent["headers"]["X-Opencode-Session"])
                    else:
                        self.assertEqual(sent["body"]["temperature"], .7)
                        self.assertNotIn("X-Opencode-Session", sent["headers"])
                state["post_error"] = True
                with self.assertRaisesRegex(ProviderError, "HTTP error 401"):
                    generate_with_provider(app._runtime_store("one"), ProviderRequest("writer", "测试", stream=False))
                state["post_error"] = False
                manual = app.add_manual_model(profile_id, "unknown-manual")
                app.update_model_assignments(primary_model_ref=manual["model_ref"], feature_assignments={})
                before = len(requests)
                with self.assertRaisesRegex(ProviderError, "刷新"):
                    generate_with_provider(app._runtime_store("one"), ProviderRequest("writer", "测试"))
                self.assertEqual(before, len(requests))
            self.assertEqual(sessions[0], sessions[1])
            self.assertNotEqual(sessions[0], sessions[2])
            self.assertTrue(all(value.startswith("naw-") and len(value) == 68 for value in sessions))


if __name__ == "__main__":
    unittest.main()
