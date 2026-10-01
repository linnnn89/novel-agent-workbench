"""Stop/save regressions with temporary projects and a loopback streaming API."""
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge
from novel_agent_workbench.providers import ModelRoleConfig, OpenAICompatibleProviderClient
from novel_agent_workbench.task_control import JobCancelled, current_job


class StopDraftTests(unittest.TestCase):
    def test_stop_over_http_preserves_version_boundary_and_input_cache(self):
        for keep in (True, False):
            with self.subTest(keep=keep), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                api = WorkbenchBridge(projects_root=root / "projects", repo_root=root)
                api.app.create_project("test")
                store = api.app._open_store("test")
                drafts = DraftGenerationService(store)
                old = drafts.save_provider_draft_version(
                    chapter_id="chapter_001", title="原章", content="原稿不能丢失。",
                    provider_role="writer", provider="mock", model="mock")
                old_bytes = Path(old.path).read_bytes()
                cached = {"chapter_id": "chapter_001", "title": "本章", "prompt": "保留这次要求"}
                api.chapter_input("test", cached["chapter_id"], cached["title"],
                                  cached["prompt"], str(api.projects_root))
                received, disconnected, done = threading.Event(), threading.Event(), threading.Event()
                events = []
                expected = "已经接收的正文。尚未显示的尾段。"

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args): pass
                    def do_POST(self):
                        self.rfile.read(int(self.headers["Content-Length"]))
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.end_headers()
                        packet = {"choices": [{"delta": {"content": expected}}]}
                        self.wfile.write(("data: " + json.dumps(packet) + "\n\n").encode())
                        self.wfile.flush()
                        self.connection.settimeout(5)
                        if self.connection.recv(1) == b"": disconnected.set()

                server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                role = ModelRoleConfig("writer", "openai_compatible", "local-test-model",
                    f"http://127.0.0.1:{server.server_port}/v1", "", {"timeout_seconds": 10})
                client = OpenAICompatibleProviderClient(role, "")
                original_hooks = api._stream_hooks
                def hooks(*args, **kwargs):
                    content, reason, sent = original_hooks(*args, **kwargs)
                    def on_content(text):
                        content(text)
                        received.set()
                    return on_content, reason, sent
                def push(event, payload):
                    events.append((event, payload))
                    if event == "draft_done": done.set()
                api._push = push
                try:
                    with patch.object(WorkbenchApplicationService, "_runtime_store", return_value=store), \
                         patch("novel_agent_workbench.providers.create_provider_client", return_value=client), \
                         patch("novel_agent_workbench.modern_desktop.get_effective_model_role_config", return_value=role), \
                         patch("novel_agent_workbench.modern_desktop.time.monotonic", return_value=1), \
                         patch.object(api, "_stream_hooks", side_effect=hooks):
                        started = api.generate_draft("test", "chapter_001", "本章", cached["prompt"])
                        self.assertTrue(received.wait(3))
                        self.assertFalse(any(event == "draft_chunk" for event, _ in events))
                        self.assertTrue(api.cancel_job(started["data"]["job_id"], keep)["data"]["stopping"])
                        self.assertTrue(done.wait(3))
                        self.assertTrue(disconnected.wait(3), "HTTP request remained connected")
                    self.assertEqual(Path(old.path).read_bytes(), old_bytes)
                    self.assertEqual(store.read_json(store.data_dir / "pending_chapter_input.json"), cached)
                    self.assertEqual(api.suggest_chapter("test")["data"]["chapter_id"], "chapter_001")
                    self.assertEqual(api.chapter_input("test", "chapter_001", "", "默认", str(api.projects_root), True)["data"], cached)
                    completed = next(payload for event, payload in events if event == "draft_done")
                    self.assertTrue(completed["cancelled"])
                    self.assertEqual(completed["ok"], keep)
                    self.assertEqual(len(drafts.list_drafts()), 2 if keep else 1)
                    if keep:
                        saved = drafts.read_draft(completed["data"]["draft_id"])
                        self.assertEqual(saved["content"], expected)
                        self.assertEqual(saved["version"], 2)
                        self.assertEqual(saved["status"], "draft")
                        self.assertTrue(saved["output_incomplete"])
                        self.assertTrue(saved["generation_cancelled"])
                        self.assertEqual(saved["provider"]["finish_reason"], "cancelled")
                    self.assertFalse(api._busy)
                finally:
                    server.shutdown()
                    server.server_close()

    def test_empty_output_and_save_failure_leave_original_intact(self):
        for content, save_fails in (("", False), ("可恢复的片段", True)):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                api = WorkbenchBridge(projects_root=root / "projects", repo_root=root)
                api.app.create_project("test")
                received, done = threading.Event(), threading.Event()
                events = []
                def generate(app, project_id, **kwargs):
                    kwargs["stream_callback"](content)
                    received.set()
                    control = current_job()
                    control.event.wait(3)
                    # A late response callback must never enter the saved snapshot.
                    with self.assertRaises(JobCancelled): kwargs["stream_callback"]("迟到的正文")
                    control.check()
                def push(event, payload):
                    events.append((event, payload))
                    if event == "draft_done": done.set()
                api._push = push
                with patch.object(WorkbenchApplicationService, "generate_context_draft", generate), \
                     patch.object(api, "_save_cancelled_draft", side_effect=OSError("模拟磁盘失败")) as save:
                    started = api.generate_draft("test", "chapter_001", "测试", "要求")
                    self.assertTrue(received.wait(3))
                    api.cancel_job(started["data"]["job_id"], True)
                    self.assertTrue(done.wait(3))
                    completed = next(payload for event, payload in events if event == "draft_done")
                    self.assertFalse(completed["ok"])
                    if save_fails:
                        self.assertEqual(completed["partial_text"], content)
                        self.assertIn("模拟磁盘失败", completed["error"])
                    else:
                        save.assert_not_called()
                        self.assertIn("尚未收到", completed["error"])
                self.assertEqual(api.app.list_drafts("test"), [])
                self.assertFalse(api._busy)


if __name__ == "__main__": unittest.main()
