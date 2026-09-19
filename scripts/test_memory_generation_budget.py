"""Memory Bank generation must budget for the thinking pass and report truncation.

Regression: a fixed max_tokens=8000 was billed for both thinking and the memory
text, so a long thinking pass cut the generated memory mid-sentence while the
result still looked complete.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_agent_workbench.memory_bank import (
    MEMORY_GENERATION_REASONING_HEADROOM_TOKENS,
    MemoryBankService,
    memory_generation_max_tokens,
)
from novel_agent_workbench.providers import ProviderResponse
from novel_agent_workbench.storage import ProjectRegistry


class MemoryGenerationBudgetTests(unittest.TestCase):
    def test_budget_leaves_room_for_thinking_above_the_target(self):
        for target in (1000, 5000, 20000):
            with self.subTest(target=target):
                budget = memory_generation_max_tokens(target)
                self.assertGreaterEqual(budget - target, MEMORY_GENERATION_REASONING_HEADROOM_TOKENS)

    def test_budget_grows_with_the_target(self):
        self.assertGreater(memory_generation_max_tokens(20000), memory_generation_max_tokens(5000))

    def test_invalid_target_falls_back_to_the_default_target(self):
        self.assertEqual(memory_generation_max_tokens(0), memory_generation_max_tokens(5000))


class MemoryGenerationTruncationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        registry = ProjectRegistry.open(Path(self.temp.name) / "projects")
        self.store = registry.create_project("memory_budget", title="记忆输出预算")
        self.service = MemoryBankService(self.store)
        self.chapters = [{"chapter_id": "chapter_001", "title": "第一章", "content": "第一章正文。"}]

    def generate(self, finish_reason: str) -> dict:
        response = ProviderResponse(
            text="一、测试记忆正文",
            usage={},
            model="mock-writer",
            provider="mock",
            finish_reason=finish_reason,
        )
        with patch("novel_agent_workbench.memory_bank.generate_with_provider", return_value=response):
            return self.service.generate_memory_text(
                current_memory="",
                chapters=self.chapters,
                target_token_budget=5000,
            ).to_dict()

    def test_output_limit_is_reported_as_incomplete(self):
        result = self.generate("length")
        self.assertTrue(result["output_incomplete"])
        self.assertEqual(result["finish_reason"], "length")
        self.assertEqual(result["text"], "一、测试记忆正文")

    def test_completed_output_is_reported_as_complete(self):
        result = self.generate("stop")
        self.assertFalse(result["output_incomplete"])

    def test_request_carries_the_reasoning_aware_budget(self):
        response = ProviderResponse(
            text="一、测试记忆正文", usage={}, model="mock-writer", provider="mock", finish_reason="stop",
        )
        with patch("novel_agent_workbench.memory_bank.generate_with_provider", return_value=response) as provider:
            self.service.generate_memory_text(
                current_memory="", chapters=self.chapters, target_token_budget=5000,
            )
        request = provider.call_args.args[1]
        self.assertEqual(request.max_tokens, memory_generation_max_tokens(5000))


if __name__ == "__main__":
    unittest.main()
