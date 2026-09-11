"""V1 data integrity checks with temporary projects and local provider results."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile
from hashlib import sha256

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.config import CURRENT_CONFIG_SCHEMA_VERSION
from novel_agent_workbench.drafts import DraftGenerationRequest, DraftGenerationService
from novel_agent_workbench.providers import ModelRoleConfig, ProviderError, ProviderResponse
from novel_agent_workbench.storage import ProjectStore
from novel_agent_workbench.task_control import JobControl, job_scope


def files_under(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class V1IntegrityTests(unittest.TestCase):
    def test_call_log_failure_keeps_generated_content_and_original_provider_error(self):
        with tempfile.TemporaryDirectory() as temp:
            app = WorkbenchApplicationService.open(temp)
            app.create_project("book")
            store = ProjectStore.open(temp, "book")
            drafts = DraftGenerationService(store)
            log = store.data_dir / "provider_call_log.json"
            log.write_text("{damaged log", encoding="utf-8")
            original = log.read_bytes()
            client = SimpleNamespace(
                role_config=ModelRoleConfig.from_mapping("writer", {"provider": "mock", "model": "mock"}),
                generate=Mock(return_value=ProviderResponse("Complete chapter.", {}, "mock", "mock", "stop")))
            control = JobControl()
            with job_scope(control), patch("novel_agent_workbench.providers.create_provider_client", return_value=client):
                result = drafts.generate_draft(DraftGenerationRequest("chapter_1", "Write.", max_tokens=64))
            self.assertEqual(drafts.read_draft(result.draft_id)["content"], "Complete chapter.")
            self.assertEqual(log.read_bytes(), original)
            self.assertTrue(control.warnings)
            with patch("novel_agent_workbench.providers.append_provider_call_log", side_effect=PermissionError("log busy")), \
                 patch("novel_agent_workbench.providers.create_provider_client", return_value=client):
                second = drafts.generate_draft(DraftGenerationRequest("chapter_2", "Write.", max_tokens=64))
                self.assertEqual(drafts.read_draft(second.draft_id)["content"], "Complete chapter.")
                failure = ProviderError("upstream failed", error_type="network_error")
                client.generate.side_effect = failure
                with self.assertRaises(ProviderError) as raised:
                    drafts.generate_draft(DraftGenerationRequest("chapter_3", "Write.", max_tokens=64))
                self.assertIs(raised.exception, failure)
            self.assertEqual(len(drafts.list_drafts()), 2)

    @unittest.skipUnless(os.name == "nt", "Windows desktop ownership uses a named mutex")
    def test_library_ownership_rejects_second_process_and_releases_on_exit(self):
        from novel_agent_workbench.library_lock import LibraryLease, LibraryInUseError
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "library"
            child = (
                "import os,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
                "from novel_agent_workbench.library_lock import LibraryLease,LibraryInUseError;"
                "\ntry: lease=LibraryLease.acquire(Path(sys.argv[2]))"
                "\nexcept LibraryInUseError: sys.exit(23)"
                "\nelse: os._exit(0)"
            )
            args = [sys.executable, "-c", child, str(ROOT / "src"), str(root)]
            with LibraryLease.acquire(root):
                with self.assertRaises(LibraryInUseError):
                    LibraryLease.acquire(root / ".")
                self.assertEqual(subprocess.run(args, capture_output=True, timeout=20).returncode, 23)
                with LibraryLease.acquire(Path(temp) / "another_library"):
                    pass
            # The child exits without cleanup; the OS must still release ownership.
            self.assertEqual(subprocess.run(args, capture_output=True, timeout=20).returncode, 0)
            with LibraryLease.acquire(root):
                pass
            # The classic window must also allow switching before any draft is open.
            from novel_agent_workbench.desktop_app import WorkbenchDesktopApp
            destination = Path(temp) / "another_library"
            destination.mkdir()
            desktop = WorkbenchDesktopApp(projects_root=root, repo_root=ROOT, library_lease=LibraryLease.acquire(root))
            try:
                desktop.update()
                with patch("novel_agent_workbench.desktop_app.filedialog.askdirectory", return_value=str(destination)):
                    with LibraryLease.acquire(destination), patch("novel_agent_workbench.desktop_app.messagebox.showerror") as warning:
                        desktop.choose_data_root()
                        self.assertEqual(desktop.projects_root, root)
                        self.assertIn("另一个窗口", warning.call_args.args[1])
                    desktop.choose_data_root()
                self.assertEqual(desktop.projects_root, destination)
                with LibraryLease.acquire(root):
                    pass
                with self.assertRaises(LibraryInUseError):
                    LibraryLease.acquire(destination)
            finally:
                desktop.destroy()
                desktop._library_lease.close()
            with LibraryLease.acquire(destination):
                pass

    def test_settings_reads_and_portability_preserve_data_and_reject_future_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = WorkbenchApplicationService.open(root / "source")
            app.create_project("global_book")
            app.create_project("custom_book")
            app.update_global_generation_settings({"sampling": {"temperature": 0.8}, "context": {"max_context_tokens": 123456}})
            app.update_generation_settings("custom_book", {"sampling": {"temperature": 0.6}})
            app.update_global_generation_settings({"sampling": {"temperature": 0.9}})
            before = files_under(root / "source")
            for book, expected in (("global_book", 0.9), ("custom_book", 0.6)):
                self.assertEqual(app.generation_settings(book)["sampling"]["temperature"], expected)
                runtime = app._runtime_store(book).read_config()
                self.assertEqual(runtime["generation_settings"]["sampling"]["temperature"], expected)
                self.assertEqual(runtime["context_policy"]["max_context_tokens"], 123456)
                app.project_overview(book)
            self.assertEqual(files_under(root / "source"), before)
            app.clear_project_generation_settings("custom_book")
            self.assertNotIn("generation_settings", ProjectStore.open(root / "source", "custom_book").read_config())
            self.assertEqual(app.generation_settings("custom_book")["sampling"]["temperature"], 0.9)
            app.update_generation_settings("custom_book", {"sampling": {"temperature": 0.6}})
            target = WorkbenchApplicationService.open(root / "target")
            target.update_global_generation_settings({"sampling": {"temperature": 0.7}})
            for book, expected in (("global_book", 0.7), ("custom_book", 0.6)):
                package = root / f"{book}.nawpkg"
                app.export_project_package(book, package)
                target.import_project_package(package, mode="keep_id")
                self.assertEqual(target.generation_settings(book)["sampling"]["temperature"], expected)

            package = root / "global_book.nawpkg"
            with zipfile.ZipFile(package) as archive:
                members = {name: archive.read(name) for name in archive.namelist()}
            manifest_name = next(name for name in members if "manifest" in name)
            manifest = json.loads(members[manifest_name])
            config = json.loads(members["data/config.json"])
            config["schema_version"] = CURRENT_CONFIG_SCHEMA_VERSION + 1
            members["data/config.json"] = json.dumps(config).encode()
            for entry in manifest["files"]:
                if entry["path"] == "data/config.json":
                    entry.update(size=len(members[entry["path"]]), sha256=sha256(members[entry["path"]]).hexdigest())
            members[manifest_name] = json.dumps(manifest).encode()
            future = root / "future.nawpkg"
            with zipfile.ZipFile(future, "w") as archive:
                for name, content in members.items():
                    archive.writestr(name, content)
            before = files_under(root / "target")
            for action in (lambda: target.inspect_project_package(future),
                           lambda: target.import_project_package(future, mode="new_id")):
                with self.assertRaisesRegex((ValueError, RuntimeError), "版本|格式"):
                    action()
                self.assertEqual(files_under(root / "target"), before)
            store = ProjectStore.open(root / "target", "global_book")
            store.config_path.write_bytes(members["data/config.json"])
            before = files_under(store.root)
            for action in (store.initialize, store.migrate_config,
                           lambda: store.write_json(store.data_dir / "drafts_index.json", {})):
                with self.assertRaisesRegex((ValueError, RuntimeError), "版本|格式"):
                    action()
                self.assertEqual(files_under(store.root), before)


if __name__ == "__main__":
    unittest.main()
