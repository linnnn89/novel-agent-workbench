"""Local text budgeting; never downloads a tokenizer or calls a model."""
from __future__ import annotations

from functools import lru_cache
from math import ceil
import threading
from typing import Any

from .config import effective_generation_settings
from .model_settings import effective_model_ref

DEFAULT_INPUT_BUDGET = 131072
_TOKENIZER_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _tokenizer():
    try:
        from deepseek_tokenizer import ds_token
        return ds_token
    except (ImportError, OSError, ValueError):
        return None


def count_text_tokens(text: str, *, model: str = "deepseek-v4") -> int:
    text = str(text or "")
    if not text:
        return 0
    tokenizer = _tokenizer() if "deepseek" in model.lower() else None
    if tokenizer is not None:
        # The vocabulary is V4's; aliases and future models remain estimates.
        with _TOKENIZER_LOCK:
            return len(tokenizer.encode(text, add_special_tokens=False))
    # Conservative fallback for Chinese prose, without the old chars/4 discount.
    ascii_chars = sum(ord(char) < 128 for char in text)
    return len(text) - ascii_chars + ceil(ascii_chars / 3)


def estimate_input_tokens(system_prompt: str, prompt: str, *, model: str = "deepseek-v4") -> int:
    return count_text_tokens(system_prompt, model=model) + count_text_tokens(prompt, model=model) + 32


def input_budget(config: dict[str, Any], *, requested: int | None = None,
                 feature_id: str = "", role: str = "writer", max_tokens: int | None = None) -> int:
    settings = effective_generation_settings(config)
    limit = int(requested if requested is not None else
                settings.get("context", {}).get("max_context_tokens") or DEFAULT_INPUT_BUDGET)
    profile = config.get("model_profiles", {}).get(effective_model_ref(config, feature_id, role), {})
    try:
        capacity = int(profile.get("context_length") or 0)
    except (TypeError, ValueError, OverflowError):
        capacity = 0
    output = int(max_tokens if max_tokens is not None else settings.get("sampling", {}).get("max_tokens") or 16)
    return min(limit, max(capacity - output, 0)) if capacity > 0 else limit


class InputBudgetExceeded(RuntimeError):
    """Complete input is retained; the caller must choose how to fit it."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = dict(report)
        estimated = report["estimated_input_tokens"]
        if report["model_limit_exceeded"]:
            message = (
                f"完整输入约 {estimated} tokens，加上预留输出 {report['output_token_budget']} tokens，"
                f"超过模型容量 {report['model_context_limit']} tokens。提高软件 input 预算不能突破模型容量；"
                "请减少前文章数、手工精简记忆，或调整输出预算。"
            )
        else:
            message = (
                f"完整输入约 {estimated} tokens，超过软件 input 预算 {report['configured_input_limit']} tokens。"
                "请选择提高 input 预算、减少前文章数，或手工精简记忆。"
            )
        super().__init__(message + "全部材料均已保留，未发送请求。")


def input_capacity_report(config: dict[str, Any], prompt: str, system_prompt: str, *,
                          feature_id: str = "", role: str = "writer", input_limit: int | None = None,
                          max_tokens: int | None = None, model: str = "deepseek-v4") -> dict[str, Any]:
    estimated = estimate_input_tokens(system_prompt, prompt, model=model)
    limit = input_budget(config, requested=input_limit, feature_id=feature_id, role=role, max_tokens=max_tokens)
    settings = effective_generation_settings(config)
    output = int(max_tokens if max_tokens is not None else settings.get("sampling", {}).get("max_tokens") or 16)
    configured_limit = int(input_limit if input_limit is not None else
                           settings.get("context", {}).get("max_context_tokens") or DEFAULT_INPUT_BUDGET)
    profile = config.get("model_profiles", {}).get(effective_model_ref(config, feature_id, role), {})
    try:
        model_capacity = int(profile.get("context_length") or 0)
    except (TypeError, ValueError, OverflowError):
        model_capacity = 0
    model_exceeded = model_capacity > 0 and estimated + output > model_capacity
    budget_exceeded = estimated > configured_limit
    return {"estimated_input_tokens": estimated, "output_token_budget": output,
            "model_context_limit": model_capacity or None,
            "estimated_total_tokens": estimated + output, "effective_input_limit": limit,
            "configured_input_limit": configured_limit,
            "over_budget_tokens": max(estimated - configured_limit, 0),
            "software_limit_exceeded": budget_exceeded,
            "model_limit_exceeded": model_exceeded,
            "can_send": not (budget_exceeded or model_exceeded),
            "suggested_input_limit": estimated,
            "materials_preserved": True,
            "feature_id": feature_id,
            "model": model,
            "token_estimator": tokenizer_description(model)}


def capacity_check(config: dict[str, Any], prompt: str, system_prompt: str, **kwargs: Any) -> dict[str, Any]:
    report = input_capacity_report(config, prompt, system_prompt, **kwargs)
    if not report["can_send"]:
        raise InputBudgetExceeded(report)
    return report


def tokenizer_description(model: str = "deepseek-v4") -> str:
    if "deepseek" in model.lower() and _tokenizer() is not None:
        return "DeepSeek V4 local tokenizer + message allowance; aliases/future models approximate"
    return "conservative CJK/ASCII estimate; approximate"
