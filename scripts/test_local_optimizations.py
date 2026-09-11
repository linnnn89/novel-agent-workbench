"""Regression checks using temporary projects and a loopback model stub only."""
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.config import default_generation_settings, effective_generation_settings
from novel_agent_workbench.context_assembler import ContextAssemblerService, memory_bank_package_candidates
from novel_agent_workbench.drafts import DraftGenerationRequest, DraftGenerationService
from novel_agent_workbench.memory_bank import MemoryBankService
from novel_agent_workbench.reviews import DraftReviewService
from novel_agent_workbench.model_settings import supports_deepseek_thinking
from novel_agent_workbench.modern_desktop import WorkbenchBridge
from novel_agent_workbench.providers import (
    ProviderError, ProviderRequest, ProviderResponse, ModelRoleConfig, OpenAICompatibleProviderClient,
    deepseek_thinking_switch_payload, generate_with_provider, safe_usage,
    read_openai_compatible_stream_response, provider_call_log_entry,
)
from novel_agent_workbench.storage import ProjectStore
from novel_agent_workbench.task_control import JobControl, JobCancelled, job_scope
from novel_agent_workbench.task_control import current_job
from novel_agent_workbench.token_budget import InputBudgetExceeded, capacity_check, count_text_tokens, estimate_input_tokens


class LocalProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="novel-regression-")
        self.addCleanup(self.temp.cleanup)
        self.app = WorkbenchApplicationService.open(self.temp.name)
        self.app.create_project("test")
        self.store = ProjectStore.open(self.temp.name, "test")
        self.drafts = DraftGenerationService(self.store)
        self.original = self.drafts.save_provider_draft_version(
            chapter_id="chapter_1", content="旧城门在北边。\n\n", title="旧城",
            provider_role="writer", provider="mock", model="mock", finish_reason="stop")

    def memory(self, *, sources=None, weight=0.35):
        self.store.write_json(self.store.data_file_path("memory_bank.json"), {
            "items": [{"memory_id": "main", "text": "旧城门在北边。" * 80,
                       "status": "ready", "memory_weight": weight,
                       "source_chapter_ids": sources if sources is not None else ["chapter_1"]}]})

    def confirm(self):
        self.app.accept_draft_manually("test", self.original.draft_id)
        self.app.commit_draft("test", self.original.draft_id, replace_existing=True)

    def test_noop_save_produces_no_writes_or_backup_files(self):
        self.confirm()
        before = {str(p): p.read_bytes() for p in Path(self.temp.name).rglob("*") if p.is_file()}
        text = self.drafts.read_draft(self.original.draft_id)["content"]
        for _ in range(20):
            result = self.drafts.update_draft_content(self.original.draft_id, text=text)
            self.assertFalse(result["changed"])
        after = {str(p): p.read_bytes() for p in Path(self.temp.name).rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_confirmed_edit_reminds_without_mutating_memory(self):
        self.confirm()
        self.memory()
        path = self.store.data_file_path("memory_bank.json")
        before = path.read_bytes()
        result = self.drafts.update_draft_content(self.original.draft_id, text="城门移到了南边。")
        self.assertEqual(result["memory_reminder"]["chapter_id"], "chapter_1")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.drafts.update_draft_content(self.original.draft_id, text="城门移到了南边。")["changed"])

    def test_retry_repairs_partial_save_instead_of_skipping_it(self):
        self.confirm()
        original_write = ProjectStore.write_json
        def fail_index(store, path, value):
            if str(path).endswith("drafts_index.json"):
                raise OSError("simulated index write failure")
            return original_write(store, path, value)
        with patch.object(ProjectStore, "write_json", autospec=True, side_effect=fail_index):
            with self.assertRaises(OSError):
                self.drafts.update_draft_content(self.original.draft_id, text="保存到一半的新正文")
        self.assertEqual(self.drafts.read_draft(self.original.draft_id)["content"], "保存到一半的新正文")
        self.assertNotEqual(self.drafts.read_confirmed_chapter("chapter_1")["content"], "保存到一半的新正文")
        result = self.drafts.update_draft_content(self.original.draft_id, text="保存到一半的新正文")
        self.assertTrue(result["changed"])
        self.assertEqual(self.drafts.read_confirmed_chapter("chapter_1")["content"], "保存到一半的新正文")

    def test_unconfirmed_or_unrelated_edit_does_not_remind(self):
        self.memory()
        self.assertIsNone(self.drafts.update_draft_content(self.original.draft_id, text="普通草稿编辑")["memory_reminder"])
        self.confirm()
        self.memory(sources=["chapter_8"])
        self.assertIsNone(self.drafts.update_draft_content(self.original.draft_id, text="再次编辑")["memory_reminder"])

    def test_replacing_confirmed_version_also_reminds(self):
        self.confirm()
        self.memory()
        newer = self.drafts.save_provider_draft_version(chapter_id="chapter_1", content="城门现在在南边。",
                    provider_role="writer", provider="mock", model="mock", finish_reason="stop")
        self.app.accept_draft_manually("test", newer.draft_id)
        result = self.app.commit_draft("test", newer.draft_id, replace_existing=True)
        self.assertEqual(result["memory_reminder"]["chapter_id"], "chapter_1")

    def test_memory_weight_does_not_reduce_token_cost(self):
        self.memory(weight=0.35)
        light = memory_bank_package_candidates(self.store, include_text=True)[0]
        self.memory(weight=1.0)
        full = memory_bank_package_candidates(self.store, include_text=True)[0]
        self.assertEqual(light["estimated_tokens"], full["estimated_tokens"])
        self.assertGreaterEqual(full["estimated_tokens"], count_text_tokens(full["text"]))

    def test_zero_budget_keeps_enabled_materials_for_user_decision(self):
        self.memory()
        preview = ContextAssemblerService(self.store).package_preview(max_context_tokens=0)
        self.assertEqual([s["source_id"] for s in preview.sections], ["main"])
        self.assertGreater(preview.token_budget["over_budget_tokens"], 0)
        self.assertFalse(any(s["skip_reason"] == "token_budget_exceeded" for s in preview.skipped))

    def test_all_enabled_materials_reach_generation_review_and_refinement(self):
        self.drafts.update_draft_content(self.original.draft_id, text="前文章节必须保留的独有标记。")
        self.confirm()
        self.memory()
        outline = "总纲必须保留。" * 120 + "总纲末尾标记"
        self.app.create_planning_item("test", "required_outline", text=outline, active=True)
        self.app.create_planning_item("test", "disabled_outline", text="禁止发送的未启用资料", active=False)
        self.app.configure_mock_writer("test")
        memory_before = self.store.data_file_path("memory_bank.json").read_bytes()
        client = MagicMock()
        client.role_config = ModelRoleConfig.from_mapping("writer", {"provider": "mock", "model": "deepseek-v4"})
        client.generate.side_effect = lambda r: ProviderResponse(
            "请调整结尾的节奏。" if r.feature_id == "ai_review" else "他重新打开城门，走入雨后的街道。",
            {}, "mock", "deepseek-v4", "stop")
        with patch("novel_agent_workbench.providers.create_provider_client", return_value=client):
            with self.assertRaises(InputBudgetExceeded) as blocked:
                self.drafts.generate_context_draft(DraftGenerationRequest("chapter_2", "继续写作"), max_context_tokens=64)
            self.assertFalse(blocked.exception.report["can_send"])
            self.assertGreater(blocked.exception.report["estimated_input_tokens"], 64)
            client.generate.assert_not_called()
            result = self.drafts.generate_context_draft(DraftGenerationRequest("chapter_2", "继续写作"), max_context_tokens=100000)
            review = DraftReviewService(self.store).ai_review_draft(result.draft_id, max_context_tokens=100000)
            with patch.object(WorkbenchApplicationService, "_runtime_store", return_value=self.store):
                self.app.refine_draft_from_ai_review("test", result.draft_id, review_id=review.review_id,
                                                   max_context_tokens=100000)
        self.assertEqual(client.generate.call_count, 3)
        for sent in client.generate.call_args_list:
            prompt = sent.args[0].prompt
            self.assertIn(outline, prompt)
            self.assertIn("旧城门在北边。" * 80, prompt)
            self.assertIn("前文章节必须保留的独有标记。", prompt)
            self.assertNotIn("禁止发送的未启用资料", prompt)
        self.assertEqual(self.store.data_file_path("memory_bank.json").read_bytes(), memory_before)

    def test_preview_matches_full_request_and_model_limit_cannot_be_raised_away(self):
        self.memory()
        self.app.configure_mock_writer("test")
        request = DraftGenerationRequest("chapter_2", "本次完整写作要求", max_tokens=100)
        prepared, preview, report = self.drafts.prepare_context_draft_request(request, max_context_tokens=1)
        self.assertFalse(report["can_send"])
        self.assertIn("旧城门在北边。" * 80, prepared.prompt)
        client = MagicMock()
        client.role_config = ModelRoleConfig.from_mapping("writer", {"provider": "mock", "model": "mock-writer"})
        client.generate.return_value = ProviderResponse("新的小说正文。", {}, "mock", "mock-writer", "stop")
        with patch("novel_agent_workbench.providers.create_provider_client", return_value=client):
            self.drafts.generate_context_draft(request, max_context_tokens=report["estimated_input_tokens"])
        sent = client.generate.call_args.args[0]
        self.assertEqual(prepared.prompt, sent.prompt)
        self.assertEqual(prepared.system_prompt, sent.system_prompt)
        self.assertEqual(preview["input_capacity"]["estimated_input_tokens"], sent.metadata["estimated_input_tokens"])
        n = estimate_input_tokens(prepared.system_prompt, prepared.prompt, model="mock-writer")
        config = {"primary_model_ref": "p::m", "model_profiles": {"p::m": {"context_length": n + 99}}}
        with self.assertRaises(InputBudgetExceeded) as blocked:
            capacity_check(config, prepared.prompt, prepared.system_prompt,
                           input_limit=n * 10, max_tokens=100, model="mock-writer")
        self.assertTrue(blocked.exception.report["model_limit_exceeded"])
        self.assertFalse(blocked.exception.report["software_limit_exceeded"])

    def test_empty_generation_rejected_and_truncated_generation_marked(self):
        before = len(self.drafts.list_drafts())
        for text in ("  ", "<think>仅有思考</think>"):
            with patch("novel_agent_workbench.drafts.generate_with_provider",
                       return_value=ProviderResponse(text, {}, "mock", "mock", "stop")):
                with self.assertRaises(RuntimeError):
                    self.drafts.generate_draft(DraftGenerationRequest("chapter_2", "test"))
        self.assertEqual(len(self.drafts.list_drafts()), before)
        with patch("novel_agent_workbench.drafts.generate_with_provider",
                   return_value=ProviderResponse("他推开门，", {}, "mock", "mock", "length")):
            result = self.drafts.generate_draft(DraftGenerationRequest("chapter_2", "test"))
        self.assertTrue(result.output_incomplete)
        self.assertTrue(self.drafts.read_draft(result.draft_id)["output_incomplete"])

    def test_context_generation_reserves_requirements_and_retains_original(self):
        self.memory()
        with patch("novel_agent_workbench.drafts.generate_with_provider") as send:
            with self.assertRaises(RuntimeError):
                self.drafts.generate_context_draft(DraftGenerationRequest("chapter_2", "要求" * 100), max_context_tokens=50)
            send.assert_not_called()
        self.assertEqual(self.drafts.read_draft(self.original.draft_id)["content"].strip(), "旧城门在北边。")

    def test_provider_protocol_setting_survives_save_and_resolve(self):
        saved = self.app.upsert_provider_profile("test-provider", display_name="测试", base_url="http://127.0.0.1:1/v1",
                                                thinking_protocol="deepseek")
        self.app.upsert_provider_profile(saved["profile_id"], display_name="改名", base_url="http://127.0.0.1:1/v1")
        profile = next(p for p in self.app.model_settings_state()["providers"] if p["profile_id"] == saved["profile_id"])
        self.assertEqual(profile["thinking_protocol"], "deepseek")


class ModelBudgetTests(unittest.TestCase):
    def test_chinese_budget_and_fallback(self):
        text = "夜色笼罩着古老的城墙。他抬起头，望着远处的山峰。\n" * 400
        self.assertGreater(count_text_tokens(text), len(text) / 4)
        with patch("novel_agent_workbench.token_budget._tokenizer", return_value=None):
            self.assertGreaterEqual(count_text_tokens(text), len(text) - 400)
        self.assertEqual(count_text_tokens(""), 0)

    def test_default_widened_existing_setting_retained(self):
        self.assertEqual(default_generation_settings()["context"]["max_context_tokens"], 131072)
        config = {"generation_settings": {"context": {"max_context_tokens": 32768}}}
        self.assertEqual(effective_generation_settings(config)["context"]["max_context_tokens"], 32768)

    def test_capacity_includes_output_and_final_prompt(self):
        text = "完整中文原稿。" * 50
        n = estimate_input_tokens("系统规则", text)
        config = {"primary_model_ref": "p::m", "model_profiles": {"p::m": {"context_length": n + 99}}}
        with self.assertRaises(RuntimeError):
            capacity_check(config, text, "系统规则", max_tokens=100)
        self.assertEqual(capacity_check(config, text, "系统规则", max_tokens=99)["estimated_total_tokens"], n + 99)

    def test_all_features_checked_before_dispatch(self):
        store = MagicMock()
        store.read_config.return_value = {"generation_settings": {"context": {"max_context_tokens": 100}}}
        for feature in ("draft_generation", "ai_refinement", "ai_review", "memory_generation", "memory_compression"):
            client = MagicMock()
            client.role_config = ModelRoleConfig("writer", "deepseek", "deepseek-flash", "", "", {})
            with self.subTest(feature=feature), patch("novel_agent_workbench.providers.create_provider_client", return_value=client):
                with self.assertRaises(RuntimeError):
                    generate_with_provider(store, ProviderRequest("writer", "天下风云出我辈。" * 500, feature_id=feature))
                client.generate.assert_not_called()

    def test_future_aliases_and_protocol_overrides(self):
        for name in ("deepseek-flash", "deepseek-pro", "deepseek-ai/DeepSeek-V4-Flash", "deepseek/deepseek-v4-flash-0731",
                     "deepseek-v4.1-flash", "deepseek-v5-pro", "deepseek-v10-pro", "deepseek-chat"):
            self.assertTrue(supports_deepseek_thinking(name), name)
            role = ModelRoleConfig("writer", "deepseek", name, "", "", {})
            self.assertEqual(deepseek_thinking_switch_payload(role, "high")["reasoning_effort"], "high")
        for name in ("other-model", "deepseek-r1", "other-v4-flash-0731", "deepseek-v4-vision", "deepseek-r1-distill"):
            self.assertFalse(supports_deepseek_thinking(name), name)
        role = ModelRoleConfig("writer", "openai_compatible", "future-new-name", "", "", {"thinking_protocol": "deepseek"})
        self.assertEqual(deepseek_thinking_switch_payload(role, "none"), {"thinking": {"type": "disabled"}})
        role = ModelRoleConfig("writer", "deepseek", "deepseek-flash", "", "", {"thinking_protocol": "unsupported"})
        self.assertEqual(deepseek_thinking_switch_payload(role, "high"), {})

    def test_usage_preserves_cache_reasoning_cost_without_inventing_missing_values(self):
        usage = safe_usage({"prompt_tokens": 1000, "completion_tokens": 500,
                            "prompt_tokens_details": {"cached_tokens": 800},
                            "completion_tokens_details": {"reasoning_tokens": 300}, "cost": 0.0001})
        self.assertEqual(usage["prompt_cache_hit_tokens"], 800)
        self.assertEqual(usage["prompt_cache_miss_tokens"], 200)
        self.assertEqual(usage["completion_tokens_details"]["reasoning_tokens"], 300)
        self.assertEqual(usage["cost"], 0.0001)
        self.assertEqual(safe_usage({"cost": float("nan"), "prompt_tokens": True}), {})

    def test_cache_diagnostics_do_not_log_prompt_text(self):
        role = ModelRoleConfig("writer", "deepseek", "deepseek-flash", "", "", {})
        request = ProviderRequest("writer", "PRIVATE NOVEL", system_prompt="PRIVATE SYSTEM", feature_id="draft_generation")
        log = provider_call_log_entry(call_id="x", request=request, role_config=role, status="ok", error_type="", usage={})
        self.assertNotIn("PRIVATE", json.dumps(log))
        self.assertEqual(len(log["request_summary"]["system_prompt_sha256"]), 64)


class TransportTests(unittest.TestCase):
    def test_reasoning_never_disables_timeout(self):
        response = io.BytesIO(b'data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\n\ndata: [DONE]\n')
        response._sock = MagicMock()
        read_openai_compatible_stream_response(response)
        response._sock.settimeout.assert_not_called()

    def test_heartbeats_cannot_keep_empty_response_alive_forever(self):
        with patch("novel_agent_workbench.providers.time.monotonic", side_effect=[0, 2]):
            with self.assertRaises(ProviderError) as error:
                read_openai_compatible_stream_response(io.BytesIO(b': ping\n'), idle_timeout_seconds=1)
        self.assertEqual(error.exception.error_type, "stream_timeout")

    def run_cancel(self, mode):
        reached = threading.Event()
        release = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if mode == "headers":
                    reached.set()
                    release.wait(5)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                if mode == "reasoning":
                    self.wfile.write(b'data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\n\n')
                else:
                    self.wfile.write(b': waiting\n\n')
                self.wfile.flush()
                reached.set()
                release.wait(5)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        control = JobControl()
        errors = []
        complete = threading.Event()
        role = ModelRoleConfig("writer", "openai_compatible", "model", f"http://127.0.0.1:{server.server_port}/v1", "", {"timeout_seconds": 30})
        def run():
            with job_scope(control):
                try:
                    OpenAICompatibleProviderClient(role, "").generate(ProviderRequest("writer", "test", stream=True))
                except Exception as error:
                    errors.append(error)
                finally:
                    complete.set()
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            self.assertTrue(reached.wait(3))
            self.assertTrue(control.cancel())
            self.assertTrue(complete.wait(2), f"Cancellation did not interrupt {mode}")
            self.assertIsInstance(errors[0], JobCancelled)
        finally:
            release.set()
            thread.join(3)
            server.shutdown()
            server.server_close()

    def test_cancel_before_headers(self): self.run_cancel("headers")
    def test_cancel_during_empty_stream(self): self.run_cancel("empty")
    def test_cancel_during_reasoning(self): self.run_cancel("reasoning")

    def test_late_stop_does_not_misreport_committed_result(self):
        control = JobControl()
        control.begin_saving()
        self.assertFalse(control.cancel())
        self.assertFalse(control.event.is_set())


class BridgeTests(unittest.TestCase):
    def test_stopping_real_bridge_job_creates_no_draft(self):
        with tempfile.TemporaryDirectory(prefix="novel-bridge-test-") as root:
            bridge = WorkbenchBridge(projects_root=Path(root), repo_root=Path(__file__).resolve().parents[1])
            bridge.app.create_project("test")
            store = ProjectStore.open(root, "test")
            reached, done = threading.Event(), threading.Event()
            events = []
            def push(event, payload):
                events.append((event, payload))
                if event == "draft_done": done.set()
            bridge._push = push
            client = MagicMock()
            client.role_config = ModelRoleConfig("writer", "mock", "deepseek-flash", "", "", {})
            def generate(request):
                request.stream_callback("尚未完成的正文" * 400)
                reached.set()
                control = current_job()
                control.event.wait(5)
                control.check()
                return ProviderResponse("unexpected", {}, "deepseek-flash", "mock", "stop")
            client.generate.side_effect = generate
            with patch.object(WorkbenchApplicationService, "_runtime_store", return_value=store), \
                 patch("novel_agent_workbench.providers.create_provider_client", return_value=client):
                started = bridge.generate_draft("test", "chapter_1", "虚构章节", "写一章")
                self.assertTrue(reached.wait(3))
                self.assertTrue(bridge.cancel_job(started["data"]["job_id"])["data"]["stopping"])
                self.assertTrue(done.wait(2))
            self.assertFalse(bridge._busy)
            self.assertEqual(DraftGenerationService(store).list_drafts(), [])
            completed = next(payload for event, payload in events if event == "draft_done")
            self.assertTrue(completed["cancelled"])
            self.assertFalse(completed["ok"])

    def test_stream_batching_retains_order_and_tail(self):
        bridge = WorkbenchBridge.__new__(WorkbenchBridge)
        bridge._job_flushers = []
        seen = []
        bridge._push = lambda event, payload: seen.append((event, payload))
        with job_scope(JobControl()), patch("novel_agent_workbench.modern_desktop.time.monotonic", return_value=1):
            content, reasoning, sent = bridge._stream_hooks("draft_chunk", chapter_id="chapter_1")
            sent()
            for _ in range(1000): content("文")
            reasoning("尾部思考")
            for flush in bridge._job_flushers: flush()
        chunks = [payload["text"] for event, payload in seen if event == "draft_chunk"]
        self.assertEqual("".join(chunks), "文" * 1000)
        self.assertEqual(len(chunks), 1)
        self.assertIn(("think_chunk", {"text": "尾部思考", "chapter_id": "chapter_1"}), seen)

    def test_cancelled_buffers_are_not_delivered(self):
        bridge = WorkbenchBridge.__new__(WorkbenchBridge)
        bridge._job_flushers = []
        bridge._push = MagicMock()
        control = JobControl()
        with job_scope(control):
            content, _, _ = bridge._stream_hooks("draft_chunk")
            content("未提交的尾部")
            control.cancel()
            bridge._push.reset_mock()
            for flush in bridge._job_flushers: flush()
        bridge._push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
