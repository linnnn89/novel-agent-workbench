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

    def test_check_draft_style_creates_metadata_only_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            baseline = service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", title="Three", prompt="private style check prompt")
            )
            replace_draft_text(store, draft.draft_id, "风格检查草稿。\n\n这是一个特别长特别长特别长特别长的段落。")

            result = service.check_draft_against_baseline(draft.draft_id, baseline_id=baseline.baseline_id)
            artifact = service.read_style_check(result.check_id)
            artifact_text = Path(result.path).read_text(encoding="utf-8")

            self.assertEqual(result.draft_id, draft.draft_id)
            self.assertEqual(artifact["baseline"]["baseline_id"], baseline.baseline_id)
            self.assertEqual(artifact["scene_mode"], "general")
            self.assertGreaterEqual(len(artifact["checks"]), 1)
            self.assertIn(result.status, {"within_baseline", "style_hints", "needs_attention"})
            self.assertNotIn("风格检查草稿", artifact_text)
            self.assertNotIn("private style check prompt", artifact_text)
            self.assertFalse(artifact["safety"]["provider_called"])
            self.assertFalse(artifact["safety"]["auto_commit"])

    def test_scene_mode_calibrates_soft_and_hard_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            baseline = service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private scene mode prompt")
            )
            replace_draft_text(store, draft.draft_id, "设定说明章。\n这里没有对白，只有连续说明。\n世界规则和背景被缓慢铺开。")

            general = service.check_draft_against_baseline(
                draft.draft_id,
                baseline_id=baseline.baseline_id,
                scene_mode="general",
            )
            exposition = service.check_draft_against_baseline(
                draft.draft_id,
                baseline_id=baseline.baseline_id,
                scene_mode="exposition",
            )
            general_dialogue = check_by_metric(general.checks, "dialogue_line_ratio")
            exposition_dialogue = check_by_metric(exposition.checks, "dialogue_line_ratio")

            self.assertEqual(general.scene_mode, "general")
            self.assertEqual(exposition.scene_mode, "exposition")
            self.assertEqual(general_dialogue["severity"], "warning")
            self.assertEqual(exposition_dialogue["severity"], "hint")
            self.assertEqual(exposition_dialogue["status"], "soft_low")

    def test_style_check_can_be_disabled_by_project_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            config = store.read_config()
            config["context_policy"]["style_check_policy"]["enabled"] = False
            store.write_config(config)
            service = SelfStyleBaselineService(store)
            service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private disabled style prompt")
            )

            with self.assertRaises(SelfStyleBaselineError):
                service.check_draft_against_baseline(draft.draft_id)

            self.assertEqual(service.list_style_checks(), [])

    def test_style_check_hide_hints_override_suppresses_hint_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            baseline = service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private hide hints prompt")
            )
            replace_draft_text(store, draft.draft_id, "设定说明章。\n这里没有对白，只有连续说明。\n世界规则和背景被缓慢铺开。")

            result = service.check_draft_against_baseline(
                draft.draft_id,
                baseline_id=baseline.baseline_id,
                scene_mode="exposition",
                show_hints=False,
            )

            self.assertEqual(result.hint_count, 0)
            self.assertTrue(all(item["severity"] != "hint" for item in result.checks))

    def test_style_check_can_disable_calibration_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            baseline = service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private no calibration prompt")
            )
            replace_draft_text(store, draft.draft_id, "设定说明章。\n这里没有对白，只有连续说明。\n世界规则和背景被缓慢铺开。")

            result = service.check_draft_against_baseline(
                draft.draft_id,
                baseline_id=baseline.baseline_id,
                scene_mode="exposition",
                calibration_enabled=False,
            )
            dialogue = check_by_metric(result.checks, "dialogue_line_ratio")

            self.assertEqual(dialogue["severity"], "warning")
            self.assertFalse(service.read_style_check(result.check_id)["style_check_policy"]["calibration_enabled"])

    def test_check_draft_style_uses_latest_baseline_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            first = service.create_baseline()
            second = service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private latest baseline prompt")
            )

            result = service.check_draft_against_baseline(draft.draft_id)

            self.assertNotEqual(first.baseline_id, second.baseline_id)
            self.assertEqual(result.baseline_id, second.baseline_id)

    def test_check_draft_style_requires_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private no baseline prompt")
            )

            with self.assertRaises(SelfStyleBaselineError):
                SelfStyleBaselineService(store).check_draft_against_baseline(draft.draft_id)

            self.assertFalse((store.data_dir / "style_checks").exists())

    def test_check_draft_style_has_no_formal_context_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private side effect prompt")
            )
            memory_before = store.data_file_path("memory_bank.json").read_text(encoding="utf-8")
            export_before = store.data_file_path("export_settings.json").read_text(encoding="utf-8")
            confirmed_before = len(DraftGenerationService(store).list_confirmed_chapters())

            service.check_draft_against_baseline(draft.draft_id)

            self.assertEqual(memory_before, store.data_file_path("memory_bank.json").read_text(encoding="utf-8"))
            self.assertEqual(export_before, store.data_file_path("export_settings.json").read_text(encoding="utf-8"))
            self.assertEqual(confirmed_before, len(DraftGenerationService(store).list_confirmed_chapters()))
            self.assertFalse((store.root / "rag").exists())
            self.assertFalse((store.root / "exports").exists())

    def test_audit_rejects_style_check_with_text_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = configured_store_with_confirmed_chapters(temp)
            service = SelfStyleBaselineService(store)
            service.create_baseline()
            draft = DraftGenerationService(store).generate_draft(
                DraftGenerationRequest(chapter_id="chapter_003", prompt="private audit check prompt")
            )
            result = service.check_draft_against_baseline(draft.draft_id)
            artifact = service.read_style_check(result.check_id)
            artifact["prompt"] = "should not be stored"
            store.write_json(str(Path(result.path).relative_to(store.root)), artifact)

            audit = audit_project(store)
            codes = {item["code"] for item in audit["findings"]}

            self.assertIn("draft_style_check_text_stored", codes)

    def test_facade_and_cli_style_check_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured_store_with_confirmed_chapters(temp)
            app = WorkbenchApplicationService.open(Path(temp))
            app.create_self_style_baseline("demo")
            draft = app.generate_draft("demo", chapter_id="chapter_003", prompt="private facade style prompt")

            check = app.check_draft_style("demo", draft["draft_id"])
            exposition_check = app.check_draft_style("demo", draft["draft_id"], scene_mode="exposition")
            hidden_hint_check = app.check_draft_style("demo", draft["draft_id"], show_hints=False)
            checks = app.list_draft_style_checks("demo")
            read = app.read_draft_style_check("demo", check["check_id"])
            stdout = capture_stdout(
                [
                    "--projects-root",
                    temp,
                    "list-draft-style-checks",
                    "demo",
                ]
            )
            state = app.project_state("demo")
            combined = json.dumps(
                {"check": check, "checks": checks, "read": read, "stdout": stdout, "state": state},
                ensure_ascii=False,
            )

            self.assertEqual(checks[0]["check_id"], check["check_id"])
            self.assertEqual(exposition_check["scene_mode"], "exposition")
            self.assertEqual(hidden_hint_check["hint_count"], 0)
            self.assertEqual(read["check_id"], check["check_id"])
            self.assertEqual(state["draft_style_check_count"], 3)
            self.assertNotIn("private facade style prompt", combined)
            self.assertNotIn("MOCK writer", combined)


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


def replace_draft_text(store: ProjectStore, draft_id: str, text: str) -> None:
    service = DraftGenerationService(store)
    draft = service.read_draft(draft_id)
    draft["content"] = text
    for item in service.list_drafts():
        if item.get("draft_id") == draft_id:
            store.write_json(str(item["path"]), draft)
            return
    raise AssertionError(f"Missing draft: {draft_id}")


def check_by_metric(checks: list[dict[str, object]], metric_id: str) -> dict[str, object]:
    for item in checks:
        if item.get("metric_id") == metric_id:
            return item
    raise AssertionError(f"Missing check metric: {metric_id}")


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
