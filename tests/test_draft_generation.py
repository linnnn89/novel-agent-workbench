from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    DraftGenerationError,
    DraftGenerationRequest,
    DraftGenerationService,
    ProjectStore,
    ProviderError,
    public_project_state,
    set_model_role_config,
)


class DraftGenerationServiceTest(unittest.TestCase):
    def test_mock_writer_output_is_written_as_draft_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)

            result = service.generate_draft(
                DraftGenerationRequest(
                    chapter_id="chapter_001",
                    title="Opening",
                    prompt="draft the opening scene",
                    system_prompt="stay concise",
                )
            )
            draft = service.read_draft(result.draft_id)

            self.assertEqual(draft["status"], "draft")
            self.assertEqual(draft["chapter_id"], "chapter_001")
            self.assertEqual(draft["provider"]["role"], "writer")
            self.assertEqual(draft["provider"]["provider"], "mock")
            self.assertTrue(Path(result.path).exists())
            self.assertEqual(len(service.list_drafts()), 1)
            self.assertEqual(service.get_draft_status(result.draft_id), "draft")

    def test_draft_generation_does_not_touch_confirmed_memory_or_export_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")

            DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="draft but do not confirm")
            )

            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.data_dir / "chapters.json").exists())
            self.assertFalse((store.data_dir / "confirmed_chapters.json").exists())
            self.assertFalse((store.root / "chapters").exists())
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.data_dir / "rag.json").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_draft_artifact_and_index_do_not_store_prompt_text_or_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-test-secret"})
            prompt = "private prompt that must not be stored"

            result = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(
                    chapter_id="chapter_001",
                    prompt=prompt,
                    metadata={"scene_goal": "private value"},
                )
            )
            draft_text = Path(result.path).read_text(encoding="utf-8")
            index_text = (store.data_dir / "drafts_index.json").read_text(encoding="utf-8")

            self.assertIn("prompt_chars", draft_text)
            self.assertNotIn(prompt, draft_text)
            self.assertNotIn(prompt, index_text)
            self.assertNotIn("private value", draft_text)
            self.assertNotIn("sk-test-secret", draft_text)
            self.assertNotIn("sk-test-secret", index_text)

    def test_draft_generation_error_does_not_create_draft_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()
            service = DraftGenerationService(store)

            with self.assertRaises(ProviderError):
                service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="no provider"))

            self.assertEqual(service.list_drafts(), [])
            self.assertFalse((store.data_dir / "drafts").exists())
            self.assertFalse((store.data_dir / "drafts_index.json").exists())

    def test_invalid_draft_request_is_rejected_before_provider_call(self) -> None:
        with self.assertRaises(DraftGenerationError):
            DraftGenerationRequest(chapter_id="", prompt="draft")
        with self.assertRaises(DraftGenerationError):
            DraftGenerationRequest(chapter_id="chapter_001", prompt=" ")
        for chapter_id in ("../chapter", "chapter 001", "chapter:001", "章节001"):
            with self.assertRaises(DraftGenerationError):
                DraftGenerationRequest(chapter_id=chapter_id, prompt="draft")

    def test_checkpoint_includes_draft_without_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-test-secret"})
            DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="checkpoint private prompt")
            )

            checkpoint = store.create_checkpoint(label="draft_generation")

            with zipfile.ZipFile(Path(checkpoint["path"]), "r") as archive:
                names = set(archive.namelist())
                content = "\n".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in names
                    if name.endswith(".json")
                )

            self.assertTrue(any(name.startswith("data/drafts/") for name in names))
            self.assertIn("data/drafts_index.json", names)
            self.assertNotIn("data/secrets.local.json", names)
            self.assertNotIn("checkpoint private prompt", content)
            self.assertNotIn("sk-test-secret", content)

    def test_commit_draft_creates_confirmed_chapter_and_marks_draft_committed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            draft_result = service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", title="Opening", prompt="draft the opening")
            )

            commit = service.commit_draft(draft_result.draft_id)
            chapter = service.read_confirmed_chapter("chapter_001")
            draft = service.read_draft(draft_result.draft_id)

            self.assertEqual(commit.chapter_id, "chapter_001")
            self.assertTrue(Path(commit.path).exists())
            self.assertEqual(chapter["source_draft_id"], draft_result.draft_id)
            self.assertEqual(chapter["title"], "Opening")
            self.assertIn("MOCK writer", chapter["content"])
            self.assertEqual(draft["status"], "committed")
            self.assertEqual(draft["committed_chapter_id"], "chapter_001")
            self.assertEqual(service.list_confirmed_chapters()[0]["chapter_id"], "chapter_001")

    def test_generate_draft_does_not_auto_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)

            service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="draft only"))

            self.assertEqual(service.list_confirmed_chapters(), [])
            self.assertFalse((store.data_dir / "confirmed_chapters.json").exists())
            self.assertFalse((store.data_dir / "confirmed_chapters").exists())

    def test_duplicate_commit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            draft_result = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="draft"))

            service.commit_draft(draft_result.draft_id)
            with self.assertRaises(DraftGenerationError):
                service.commit_draft(draft_result.draft_id)

            self.assertEqual(len(service.list_confirmed_chapters()), 1)

    def test_second_draft_for_existing_confirmed_chapter_is_rejected_without_half_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            first = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="first"))
            second = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="second"))
            service.commit_draft(first.draft_id)

            with self.assertRaises(DraftGenerationError):
                service.commit_draft(second.draft_id)

            self.assertEqual(len(service.list_confirmed_chapters()), 1)
            self.assertEqual(service.get_draft_status(second.draft_id), "draft")

    def test_commit_draft_checkpoint_is_taken_before_confirmed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            draft_result = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="draft"))

            commit = service.commit_draft(draft_result.draft_id)

            self.assertEqual(commit.checkpoint["label"], "pre_commit")
            with zipfile.ZipFile(Path(commit.checkpoint["path"]), "r") as archive:
                names = set(archive.namelist())
            self.assertIn("data/drafts_index.json", names)
            self.assertNotIn("data/confirmed_chapters.json", names)
            self.assertFalse(any(name.startswith("data/confirmed_chapters/") for name in names))

    def test_commit_draft_does_not_update_memory_rag_or_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            service = DraftGenerationService(store)
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            draft_result = service.generate_draft(DraftGenerationRequest(chapter_id="chapter_001", prompt="draft"))

            service.commit_draft(draft_result.draft_id)

            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.data_dir / "rag.json").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_commit_log_excludes_content_prompt_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-test-secret"})
            service = DraftGenerationService(store)
            draft_result = service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private commit prompt")
            )

            service.commit_draft(draft_result.draft_id)
            log_text = json.dumps(service.read_commit_log(), ensure_ascii=False)

            self.assertIn("chapter_001", log_text)
            self.assertNotIn("private commit prompt", log_text)
            self.assertNotIn("MOCK writer", log_text)
            self.assertNotIn("sk-test-secret", log_text)

    def test_checkpoint_after_commit_keeps_commit_log_free_of_prompt_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-test-secret"})
            service = DraftGenerationService(store)
            draft_result = service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", prompt="private checkpoint commit prompt")
            )
            service.commit_draft(draft_result.draft_id)

            checkpoint = store.create_checkpoint(label="after_commit")

            with zipfile.ZipFile(Path(checkpoint["path"]), "r") as archive:
                names = set(archive.namelist())
                content = "\n".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in names
                    if name.endswith(".json")
                )

            self.assertIn("data/commit_log.json", names)
            self.assertIn("data/confirmed_chapters.json", names)
            self.assertNotIn("data/secrets.local.json", names)
            self.assertNotIn("private checkpoint commit prompt", content)
            self.assertNotIn("sk-test-secret", content)

    def test_public_project_state_excludes_prompt_content_and_plain_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store(temp)
            store.update_secrets({"mock_key": "sk-test-secret"})
            service = DraftGenerationService(store)
            draft_result = service.generate_draft(
                DraftGenerationRequest(chapter_id="chapter_001", title="Opening", prompt="private state prompt")
            )
            service.commit_draft(draft_result.draft_id)

            state = public_project_state(store)
            state_text = json.dumps(state, ensure_ascii=False)

            self.assertEqual(state["draft_count"], 1)
            self.assertEqual(state["committed_chapter_count"], 1)
            self.assertEqual(state["latest_draft"]["status"], "committed")
            self.assertEqual(state["latest_committed_chapter"]["chapter_id"], "chapter_001")
            self.assertNotIn("private state prompt", state_text)
            self.assertNotIn("MOCK writer", state_text)
            self.assertNotIn("sk-test-secret", state_text)


def configured_store(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    return store


if __name__ == "__main__":
    unittest.main()
