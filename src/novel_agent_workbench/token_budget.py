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
    limit = int(requested or settings.get("context", {}).get("max_context_tokens") or DEFAULT_INPUT_BUDGET)
    profile = config.get("model_profiles", {}).get(effective_model_ref(config, feature_id, role), {})
    try:
        capacity = int(profile.get("context_length") or 0)
    except (TypeError, ValueError, OverflowError):
        capacity = 0
    output = int(max_tokens if max_tokens is not None else settings.get("sampling", {}).get("max_tokens") or 16)
    return min(limit, max(capacity - output, 0)) if capacity > 0 else limit


def capacity_check(config: dict[str, Any], prompt: str, system_prompt: str, *,
                   feature_id: str = "", role: str = "writer", input_limit: int | None = None,
                   max_tokens: int | None = None, model: str = "deepseek-v4") -> dict[str, Any]:
    estimated = estimate_input_tokens(system_prompt, prompt, model=model)
    limit = input_budget(config, requested=input_limit, feature_id=feature_id, role=role, max_tokens=max_tokens)
    settings = effective_generation_settings(config)
    output = int(max_tokens if max_tokens is not None else settings.get("sampling", {}).get("max_tokens") or 16)
    if estimated > limit:
        raise RuntimeError(
            f"完整输入约 {estimated} tokens，可用输入上限为 {limit}（已预留输出空间）。"
            "请提高创作设置中的上下文上限、减少背景资料或调整输出预算；未截断原稿，未发送请求。"
        )
    profile = config.get("model_profiles", {}).get(effective_model_ref(config, feature_id, role), {})
    try:
        model_capacity = int(profile.get("context_length") or 0)
    except (TypeError, ValueError, OverflowError):
        model_capacity = 0
    return {"estimated_input_tokens": estimated, "output_token_budget": output,
            "model_context_limit": model_capacity or None,
            "estimated_total_tokens": estimated + output, "effective_input_limit": limit,
            "token_estimator": tokenizer_description(model)}


def tokenizer_description(model: str = "deepseek-v4") -> str:
    if "deepseek" in model.lower() and _tokenizer() is not None:
        return "DeepSeek V4 local tokenizer + message allowance; aliases/future models approximate"
    return "conservative CJK/ASCII estimate; approximate"
