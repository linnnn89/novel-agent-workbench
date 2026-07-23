from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from novel_agent_workbench.application_service import WorkbenchApplicationService
from novel_agent_workbench.model_catalog import normalize_catalog_payload
from novel_agent_workbench.model_settings_ui import filter_model_labels
from novel_agent_workbench.model_settings import (
    BUILTIN_PROVIDER_PROFILES,
    make_model_ref,
    migrate_global_model_settings,
    resolve_model_role_mapping,
)


class ModelSettingsMigrationTests(unittest.TestCase):
    def test_builtin_profiles_include_required_three_providers(self) -> None:
        self.assertEqual(
            BUILTIN_PROVIDER_PROFILES["siliconflow"]["base_url"],
            "https://api.siliconflow.cn/v1",
        )
        self.assertEqual(BUILTIN_PROVIDER_PROFILES["chutes"]["adapter"], "chutes_openai")
        self.assertEqual(BUILTIN_PROVIDER_PROFILES["openrouter"]["adapter"], "openrouter")

    def test_v1_openrouter_role_migrates_without_changing_secret_reference(self) -> None:
        legacy = {
            "schema_version": 1,
            "model_roles": {
                "writer": {
                    "provider": "openrouter",
                    "model": "deepseek/deepseek-v4-flash",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_ref": "project_secret.existing_openrouter_key",
                    "settings": {"timeout_seconds": 300},
                }
            },
        }
        migrated, changed = migrate_global_model_settings(legacy)
        self.assertTrue(changed)
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(
            migrated["provider_profiles"]["openrouter"]["api_key_ref"],
            "project_secret.existing_openrouter_key",
        )
        self.assertEqual(
            migrated["primary_model_ref"],
            "openrouter::deepseek/deepseek-v4-flash",
        )
        self.assertEqual(migrated["model_roles"], legacy["model_roles"])

    def test_different_key_references_create_different_provider_profiles(self) -> None:
        legacy = {
            "schema_version": 1,
            "model_roles": {
                "writer": {
                    "provider": "openrouter",
                    "model": "provider/model-a",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_ref": "project_secret.key_a",
                },
                "scorer": {
                    "provider": "openrouter",
                    "model": "provider/model-b",
                    "base_url": "https://openrouter.ai/api/v1",
                    "api_key_ref": "project_secret.key_b",
                },
            },
        }
        migrated, _ = migrate_global_model_settings(legacy)
        refs = {
            profile["api_key_ref"]
            for profile in migrated["provider_profiles"].values()
            if profile["adapter"] == "openrouter"
        }
        self.assertIn("project_secret.key_a", refs)
        self.assertIn("project_secret.key_b", refs)
        self.assertEqual(migrated["feature_assignments"]["ai_review"]["mode"], "model")

    def test_feature_assignment_resolves_provider_model_and_timeout(self) -> None:
        model_ref = make_model_ref("chutes", "Qwen/Qwen3-32B-TEE")
        settings, _ = migrate_global_model_settings(
            {
                "schema_version": 2,
                "provider_profiles": BUILTIN_PROVIDER_PROFILES,
                "model_profiles": {
                    model_ref: {
                        "provider_profile_id": "chutes",
                        "model_id": "Qwen/Qwen3-32B-TEE",
                        "enabled": True,
                    }
                },
                "primary_model_ref": model_ref,
                "feature_assignments": {},
            }
        )
        resolved = resolve_model_role_mapping(settings, role="scorer", feature_id="ai_review")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["provider"], "chutes_openai")
        self.assertEqual(resolved["model"], "Qwen/Qwen3-32B-TEE")
        self.assertEqual(resolved["settings"]["timeout_seconds"], 300.0)


class ModelCatalogTests(unittest.TestCase):
    def test_catalog_normalization_deduplicates_and_keeps_metadata(self) -> None:
        result = normalize_catalog_payload(
            {
                "data": [
                    {"id": "org/model", "name": "Model", "context_length": 8192},
                    {"id": "org/model", "name": "Duplicate"},
                    {"object": "model"},
                ]
            },
            provider_profile_id="openrouter",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["model_id"], "org/model")
        self.assertEqual(result[0]["context_length"], 8192)


class ModelSettingsApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.app = WorkbenchApplicationService.open(self.root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_reading_v1_settings_creates_settings_only_backup(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "global_settings.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "model_roles": {
                        "writer": {
                            "provider": "openrouter",
                            "model": "org/model",
                            "base_url": "https://openrouter.ai/api/v1",
                            "api_key_ref": "project_secret.existing",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        state = self.app.model_settings_state()
        self.assertEqual(state["schema_version"], 2)
        backups = list((self.root / "migration_backups").glob("global_settings-v1-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertFalse(any(path.name.startswith("global_secrets") for path in backups))

    def test_custom_provider_manual_model_and_assignments_round_trip(self) -> None:
        provider = self.app.upsert_provider_profile(
            "",
            display_name="我的兼容服务",
            adapter="openai_compatible",
            base_url="https://example.invalid/v1",
            timeout_seconds=120,
        )
        profile_id = provider["profile_id"]
        self.app.set_provider_profile_secret(profile_id, "not-a-real-key")
        model = self.app.add_manual_model(profile_id, "author/model")
        assignments = {
            feature_id: {"mode": "inherit", "model_ref": ""}
            for feature_id in (
                "draft_generation",
                "ai_review",
                "ai_refinement",
                "memory_generation",
                "memory_compression",
            )
        }
        self.app.update_model_assignments(
            primary_model_ref=model["model_ref"],
            feature_assignments=assignments,
        )
        state = self.app.model_settings_state()
        stored = next(item for item in state["providers"] if item["profile_id"] == profile_id)
        self.assertTrue(stored["has_api_key"])
        self.assertNotIn("not-a-real-key", json.dumps(state, ensure_ascii=False))
        self.assertEqual(state["primary_model_ref"], model["model_ref"])

    def test_explicit_refresh_updates_models_and_cache(self) -> None:
        self.app.set_provider_profile_secret("openrouter", "not-a-real-key")
        fake_models = [
            {
                "provider_profile_id": "openrouter",
                "model_id": "org/model",
                "display_name": "Model",
                "source": "remote",
            }
        ]
        with patch(
            "novel_agent_workbench.application_service.fetch_model_catalog",
            return_value=fake_models,
        ):
            result = self.app.refresh_provider_models("openrouter")
        self.assertEqual(result["model_count"], 1)
        self.assertTrue((self.root / "model_catalog_cache.json").exists())
        state = self.app.model_settings_state()
        self.assertIn("openrouter::org/model", {item["model_ref"] for item in state["models"]})


class ModelSettingsUiSourceTests(unittest.TestCase):
    def test_model_label_search_is_case_insensitive_and_matches_all_terms(self) -> None:
        labels = [
            "OpenRouter · DeepSeek V4 Flash [deepseek/deepseek-v4-flash]",
            "硅基流动 · DeepSeek V3 [deepseek-ai/DeepSeek-V3]",
            "Chutes · GLM 5.2 [zai-org/GLM-5.2-TEE]",
        ]
        self.assertEqual(len(filter_model_labels(labels, "deep")), 2)
        self.assertEqual(
            filter_model_labels(labels, "DEEP flash"),
            [labels[0]],
        )
        self.assertEqual(filter_model_labels(labels, ""), labels)

    def test_dialog_has_three_pages_and_fixed_save_footer(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "novel_agent_workbench"
            / "model_settings_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"API 提供商"', source)
        self.assertIn('"模型目录"', source)
        self.assertIn('"功能分配"', source)
        self.assertIn('self.save_button.grid(row=0, column=1)', source)
        self.assertIn('self.window.resizable(True, True)', source)
        self.assertIn('state="normal"', source)
        self.assertIn('"<KeyRelease>"', source)
        self.assertIn('event.keysym in {"Return", "KP_Enter"}', source)
        self.assertIn("可继续输入", source)


if __name__ == "__main__":
    unittest.main()
