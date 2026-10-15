"""Project deletion must not overlap desktop generation; no real model calls."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.drafts import DraftGenerationRequest, DraftGenerationService
from novel_agent_workbench.modern_desktop import WorkbenchBridge
from novel_agent_workbench.providers import ProviderResponse


class DeleteProjectBusyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.bridge = WorkbenchBridge(projects_root=root / "projects", repo_root=root)
        self.bridge.app.create_project("test")
        self.store = self.bridge.app._open_store("test")

    def test_generation_blocks_delete_then_idle_delete_succeeds(self):
        received, resume, done = threading.Event(), threading.Event(), threading.Event()
        payloads = []
        def provider(*args, **kwargs):
            received.set()
            if not resume.wait(5):
                raise RuntimeError("test provider timed out")
            return ProviderResponse("完成的正文。", {}, "mock", "mock", "stop")
        def push(event, payload):
            if event == "draft_done":
                payloads.append(payload)
                done.set()
        self.bridge._push = push
        with patch("novel_agent_workbench.drafts.generate_with_provider", side_effect=provider):
            self.bridge._run_job("test-generation", lambda: DraftGenerationService(self.store).generate_draft(
                DraftGenerationRequest("chapter_1", "写正文")).to_dict(), on_done="draft_done")
            try:
                self.assertTrue(received.wait(5))
                result = self.bridge.delete_project("test", "确认删除")
                self.assertFalse(result["ok"])
                self.assertTrue(self.store.root.exists())
                self.assertFalse(list(self.bridge.projects_root.glob("*.trash")))
            finally:
                resume.set()
                self.assertTrue(done.wait(5))
        self.assertTrue(payloads[0]["ok"])
        self.assertEqual(len(DraftGenerationService(self.store).list_drafts()), 1)
        result = self.bridge.delete_project("test", "确认删除")
        self.assertTrue(result["ok"])
        self.assertFalse(self.store.root.exists())
        self.assertTrue(Path(result["data"]["result"]["trashed_path"]).exists())

    def test_deletion_reservation_blocks_jobs_without_holding_state_lock(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        original = WorkbenchApplicationService.delete_project
        results = []
        def paused_delete(app, project_id):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test deletion timed out")
            return original(app, project_id)
        def delete():
            try:
                results.append(self.bridge.delete_project("test", "确认删除"))
            finally:
                finished.set()
        with patch.object(WorkbenchApplicationService, "delete_project", paused_delete):
            thread = threading.Thread(target=delete)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                acquired = self.bridge._busy_lock.acquire(blocking=False)
                if acquired:
                    self.bridge._busy_lock.release()
                self.assertTrue(acquired, "disk I/O must not hold the state lock")
                self.assertFalse(self.bridge._begin_job())
                self.assertFalse(self.bridge.save_draft("test", "d", "x")["ok"])
                self.assertFalse(self.bridge.cancel_job()["data"]["stopping"])
            finally:
                release.set()
                thread.join(5)
        self.assertTrue(finished.is_set())
        self.assertTrue(results[0]["ok"])

    def test_failed_delete_releases_job_lock(self):
        with patch.object(WorkbenchApplicationService, "delete_project", side_effect=OSError("disk error")):
            self.assertFalse(self.bridge.delete_project("test", "确认删除")["ok"])
        self.assertTrue(self.bridge._begin_job())
        self.bridge._end_job()
        self.assertTrue(self.store.root.exists())

    def test_save_failure_does_not_block_delete_and_late_save_cannot_recreate(self):
        with patch.object(WorkbenchApplicationService, "update_draft_content", side_effect=OSError("save broken")):
            self.assertFalse(self.bridge.save_draft("test", "draft", "text")["ok"])
        self.assertTrue(self.bridge.delete_project("test", "确认删除")["ok"])
        self.assertFalse(self.bridge.save_draft("test", "draft", "late text")["ok"])
        self.assertFalse(self.store.root.exists())

    def test_stalled_save_rejects_delete_immediately_without_blocking_control(self):
        entered, release = threading.Event(), threading.Event()
        results = []
        def paused_save(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test save timed out")
            raise OSError("save failed")
        with patch.object(WorkbenchApplicationService, "update_draft_content", side_effect=paused_save):
            thread = threading.Thread(target=lambda: results.append(self.bridge.save_draft("test", "draft", "text")))
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                acquired = self.bridge._busy_lock.acquire(blocking=False)
                if acquired:
                    self.bridge._busy_lock.release()
                self.assertTrue(acquired)
                rejected = self.bridge.delete_project("test", "确认删除")
                self.assertFalse(rejected["ok"])
                self.assertIn("尚未结束", rejected["error"])
                self.assertTrue(self.store.root.exists())
                self.assertFalse(self.bridge._begin_job())
                self.assertFalse(self.bridge.cancel_job()["data"]["stopping"])
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(results[0]["ok"])
        self.assertTrue(self.bridge.delete_project("test", "确认删除")["ok"])

    def test_refresh_failure_after_delete_is_committed_success(self):
        with patch("novel_agent_workbench.modern_desktop.build_workspace_tree", side_effect=OSError("refresh failed")):
            result = self.bridge.delete_project("test", "确认删除")
        self.assertTrue(result["ok"])
        self.assertIn("warning", result["data"])
        self.assertFalse(self.store.root.exists())
        self.assertTrue(self.bridge._begin_job())
        self.bridge._end_job()

    def test_operation_reservation_released_on_any_exception(self):
        with self.assertRaises(ValueError):
            with self.bridge._local_operation("test"):
                raise ValueError("failure")
        self.assertTrue(self.bridge._begin_job())
        self.bridge._end_job()

    def test_stale_library_save_rejected_before_disk_access(self):
        with patch.object(WorkbenchApplicationService, "update_draft_content") as write:
            result = self.bridge.save_draft("test", "d", "text", str(self.bridge.projects_root / "other"))
        self.assertFalse(result["ok"])
        write.assert_not_called()

    def test_inspections_can_coexist_but_block_mutation_and_job(self):
        with self.bridge._local_operation("inspect one", inspection=True):
            with self.bridge._local_operation("inspect two", inspection=True):
                self.assertEqual(self.bridge._active_inspections, 2)
                self.assertFalse(self.bridge._begin_job())
                self.assertFalse(self.bridge.delete_project("test", "确认删除")["ok"])
                acquired = self.bridge._busy_lock.acquire(blocking=False)
                self.assertTrue(acquired)
                if acquired:
                    self.bridge._busy_lock.release()
        self.assertEqual(self.bridge._active_inspections, 0)
        self.assertTrue(self.bridge.delete_project("test", "确认删除")["ok"])

    def test_inspection_failure_releases_lease(self):
        with self.assertRaises(ValueError):
            with self.bridge._local_operation("inspect", inspection=True):
                raise ValueError("bad data")
        self.assertEqual(self.bridge._active_inspections, 0)
        self.assertTrue(self.bridge._begin_job())
        self.bridge._end_job()

    def test_confirmation_still_required(self):
        self.assertFalse(self.bridge.delete_project("test", "")["ok"])
        self.assertTrue(self.store.root.exists())


if __name__ == "__main__":
    unittest.main()
