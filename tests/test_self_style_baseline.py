from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novel_agent_workbench import (
    DraftGenerationRequest,
    DraftGenerationService,
    ProjectStore,
    SelfStyleBaselineError,
    SelfStyleBaselineService,
    WorkbenchApplicationService,
    audit_project,
    set_model_role_config,
)
from novel_agent_workbench.cli import main


class SelfStyleBaselineServiceTest(unittest.TestCase):
    def test_create_baseline_from_confirmed_chapters_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)

            result = service.create_baseline()
            artifact = service.read_baseline(result.baseline_id)

            self.assertEqual(result.chapter_count, 2)
            self.assertEqual(artifact["source"]["type"], "confirmed_chapters")
            self.assertEqual(artifact["metrics"]["chapter_count"], 2)
            self.assertEqual(artifact["metrics"]["nonspace_chars"]["count"], 2)
            self.assertIn("dialogue_line_ratio", artifact["metrics"])
            self.assertTrue(Path(result.path).exists())
            self.assertEqual(len(service.list_baselines()), 1)

    def test_baseline_does_not_store_chapter_text_prompt_or_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            store.update_secrets({"provider_key": "sk-self-style-secret"})
            service = SelfStyleBaselineService(store)

            result = service.create_baseline()
            artifact_text = Path(result.path).read_text(encoding="utf-8")
            index_text = (store.data_dir / "style_baselines_index.json").read_text(encoding="utf-8")
            combined = artifact_text + index_text

            self.assertNotIn("自有正文第一章", combined)
            self.assertNotIn("第二章继续", combined)
            self.assertNotIn("private baseline prompt", combined)
            self.assertNotIn("sk-self-style-secret", combined)
            self.assertFalse(json.loads(artifact_text)["safety"]["chapter_text_stored"])

    def test_baseline_requires_confirmed_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProjectStore.open(Path(temp), "demo")
            store.initialize()

            with self.assertRaises(SelfStyleBaselineError):
                SelfStyleBaselineService(store).create_baseline()

            self.assertFalse((store.data_dir / "style_baselines").exists())

    def test_public_state_and_audit_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            baseline = SelfStyleBaselineService(store).create_baseline()
            app = WorkbenchApplicationService.open(Path(temp))

            state = app.project_state("demo")
            audit = audit_project(store)
            output = json.dumps({"state": state, "audit": audit, "baseline": baseline.to_dict()}, ensure_ascii=False)

            self.assertEqual(state["self_style_baseline_count"], 1)
            self.assertEqual(state["latest_self_style_baseline"]["baseline_id"], baseline.baseline_id)
            self.assertTrue(audit["ok"], json.dumps(audit, ensure_ascii=False))
            self.assertNotIn("自有正文第一章", output)
            self.assertNotIn("第二章继续", output)

    def test_audit_rejects_style_baseline_with_text_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            result = service.create_baseline()
            artifact = service.read_baseline(result.baseline_id)
            artifact["text"] = "should not be stored"
            store.write_json(str(Path(result.path).relative_to(store.root)), artifact)

            audit = audit_project(store)
            codes = {item["code"] for item in audit["findings"]}

            self.assertIn("self_style_baseline_text_stored", codes)

    def test_facade_and_cli_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_store_with_confirmed_chapters(temp)
            app = WorkbenchApplicationService.open(Path(temp))

            result = app.create_self_style_baseline("demo")
            baselines = app.list_self_style_baselines("demo")
            read = app.read_self_style_baseline("demo", result["baseline_id"])
            stdout = capture_stdout(
                [
                    "--projects-root",
                    temp,
                    "list-self-style-baselines",
                    "demo",
                ]
            )

            combined = json.dumps({"result": result, "baselines": baselines, "read": read, "stdout": stdout}, ensure_ascii=False)
            self.assertEqual(result["chapter_count"], 2)
            self.assertEqual(baselines[0]["baseline_id"], result["baseline_id"])
            self.assertEqual(read["baseline_id"], result["baseline_id"])
            self.assertNotIn("自有正文第一章", combined)
            self.assertNotIn("private baseline prompt", combined)


def configured_store_with_confirmed_chapters(temp: str) -> ProjectStore:
    store = ProjectStore.open(Path(temp), "demo")
    store.initialize()
    set_model_role_config(store, "writer", {"provider": "mock", "model": "mock-writer"})
    service = DraftGenerationService(store)
    first = service.generate_draft(
        DraftGenerationRequest(chapter_id="chapter_001", title="One", prompt="private baseline prompt one")
    )
    second = service.generate_draft(
        DraftGenerationRequest(chapter_id="chapter_002", title="Two", prompt="private baseline prompt two")
    )
    service.commit_draft(first.draft_id)
    service.commit_draft(second.draft_id)
    replace_confirmed_text(
        store,
        "chapter_001",
        "自有正文第一章。\n“你好。”\n她停了一下，又笑了。\n\n新的段落很短！",
    )
    replace_confirmed_text(
        store,
        "chapter_002",
        "第二章继续。\n他们在街角聊天：今天要去哪里？\n答案并不复杂，只是日常。",
    )
    return store


def replace_confirmed_text(store: ProjectStore, chapter_id: str, text: str) -> None:
    service = DraftGenerationService(store)
    chapter = service.read_confirmed_chapter(chapter_id)
    chapter["content"] = text
    for item in service.list_confirmed_chapters():
        if item.get("chapter_id") == chapter_id:
            store.write_json(str(item["path"]), chapter)
            return
    raise AssertionError(f"Missing confirmed chapter: {chapter_id}")


def capture_stdout(argv: list[str]) -> str:
    from io import StringIO
    from unittest.mock import patch

    buffer = StringIO()
    with patch("sys.stdout", buffer):
        code = main(argv)
    if code != 0:
        raise AssertionError(f"CLI failed with exit code {code}: {buffer.getvalue()}")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
