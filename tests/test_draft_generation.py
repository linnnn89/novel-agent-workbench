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


def configured_store(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    return store


if __name__ == "__main__":
    unittest.main()
