from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import atomic_write_json_file
from .model_settings import SUBSCRIPTION_PROVIDER_IDS
from .task_control import open_request, check_cancelled, current_job


MODEL_CATALOG_CACHE_FILENAME = "model_catalog_cache.json"
MAX_CATALOG_MODELS = 2000
MAX_CATALOG_BYTES = 8 * 1024 * 1024
COMMANDCODE_GOAT_PLAN_URL = "https://commandcode.ai/docs/plans/goat"


class ModelCatalogError(RuntimeError):
    pass


def models_endpoint(base_url: str, *, adapter: str = "") -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        raise ModelCatalogError("API 地址不能为空。")
    if adapter == "opencode_go" and base.endswith("/openai/v1"):
        base = base[:-len("/openai/v1")] + "/v1"
    return f"{base}/models"


def normalize_catalog_payload(payload: object, *, provider_profile_id: str, adapter: str = "",
                              goat_plan: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    source = payload if isinstance(payload, dict) else {}
    raw_models = source.get("data")
    if not isinstance(raw_models, list):
        raise ModelCatalogError("模型目录响应缺少 data 数组。")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_models[:MAX_CATALOG_MODELS]:
        if not isinstance(item, dict):
            continue
        if adapter == "opencode_go":
            apis = item.get("api")
            if item.get("type") != "chat" or not isinstance(apis, dict) or "chat-completions" not in apis:
                continue
        if adapter == "commandcode_goat":
            endpoints = item.get("supported_endpoints")
            if not isinstance(endpoints, list) or not any(
                isinstance(endpoint, str) and endpoint.strip("/") == "chat/completions" for endpoint in endpoints
            ) or not commandcode_goat_includes(goat_plan or [], item):
                continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        architecture = item.get("architecture") if isinstance(item.get("architecture"), dict) else {}
        result.append(
            {
                "provider_profile_id": provider_profile_id,
                "model_id": model_id,
                "display_name": str(item.get("name") or model_id).strip(),
                "context_length": item.get("context_length") or item.get("max_model_len"),
                "supported_parameters": item.get("supported_parameters")
                if isinstance(item.get("supported_parameters"), list)
                else [],
                "architecture": architecture,
                "source": "remote",
            }
        )
        if adapter in SUBSCRIPTION_PROVIDER_IDS:
            limits = item.get("limit") if isinstance(item.get("limit"), dict) else {}
            capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
            result[-1].update({
                "context_length": result[-1]["context_length"] or limits.get("context"),
                "max_output_tokens": limits.get("output") or item.get("max_completion_tokens"),
                "chat_completions_supported": True,
                "supported_parameters": ["max_tokens", "stream"] + [
                    key for key in ("temperature", "top_p") if capabilities.get(key) is not False
                ],
            })
    if adapter in SUBSCRIPTION_PROVIDER_IDS and not result:
        raise ModelCatalogError("订阅目录中没有可用的 Chat Completions 模型，已保留原模型列表。")
    return result


def read_commandcode_goat_plan(html: str) -> list[dict[str, Any]]:
    # Decode Next.js flight strings as JSON data; never execute page scripts.
    chunks = re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    try:
        payload = "".join(json.loads(match.group(1)) for match in chunks)
        start = payload.find('[{"slug":')
        if start < 0:
            raise ValueError("missing model table")
        entries, _ = json.JSONDecoder().raw_decode(payload, start)
        if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
            raise ValueError("invalid model table")
        if not any(entry.get("minPlanName") == "GOAT" for entry in entries):
            raise ValueError("missing GOAT plan")
        return entries
    except (ValueError, RecursionError) as exc:
        raise ModelCatalogError("无法读取 Command Code GOAT 套餐目录，已保留原模型列表。") from exc


def commandcode_goat_includes(plan: list[dict[str, Any]], model: dict[str, Any]) -> bool:
    model_id = str(model.get("id") or "").strip()
    if not model_id:
        return False
    matches = [entry for entry in plan if entry.get("id") == model_id]
    if not matches:
        slug = lambda value: re.sub(r"[^a-z0-9]", "", str(value or "").lower())
        matches = [entry for entry in plan if slug(entry.get("slug")) == slug(model_id)]
    if not matches and model.get("name"):
        matches = [entry for entry in plan if entry.get("name") == model["name"]]
    return len(matches) == 1 and matches[0].get("minPlanName") in {"Go", "GOAT"}


def _read_catalog_response(request: urllib.request.Request, timeout: float) -> bytes:
    with open_request(request, timeout=timeout) as response:
        body = response.read(MAX_CATALOG_BYTES + 1)
    check_cancelled()
    if len(body) > MAX_CATALOG_BYTES:
        raise ModelCatalogError("模型目录响应过大，已保留原模型列表。")
    return body


def fetch_model_catalog(
    *,
    provider_profile_id: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float = 30.0,
    adapter: str = "",
) -> list[dict[str, Any]]:
    adapter = adapter or provider_profile_id
    timeout = min(60.0, max(1.0, float(timeout_seconds)))
    request = urllib.request.Request(
        models_endpoint(base_url, adapter=adapter),
        headers={
            "Accept": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
            "User-Agent": "NovelAgentWorkbench/1.0",
        },
        method="GET",
    )
    try:
        payload = json.loads(_read_catalog_response(request, timeout).decode("utf-8"))
        goat_plan = None
        if adapter == "commandcode_goat":
            # The documentation host must never receive the provider's API key.
            plan_request = urllib.request.Request(COMMANDCODE_GOAT_PLAN_URL,
                headers={"Accept": "text/html", "User-Agent": "NovelAgentWorkbench/1.0"})
            goat_plan = read_commandcode_goat_plan(_read_catalog_response(plan_request, timeout).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ModelCatalogError(f"模型目录请求失败：HTTP {int(exc.code)}。") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        check_cancelled()
        raise ModelCatalogError(f"模型目录请求失败：{exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelCatalogError("模型目录返回了无法解析的 JSON。") from exc
    models = normalize_catalog_payload(payload, provider_profile_id=provider_profile_id, adapter=adapter, goat_plan=goat_plan)
    check_cancelled()
    control = current_job()
    if control:
        control.begin_saving()
    return models


def read_catalog_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "providers": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": 1, "providers": {}}
    return value if isinstance(value, dict) else {"schema_version": 1, "providers": {}}


def write_catalog_cache(path: Path, profile_id: str, models: list[dict[str, Any]]) -> dict[str, Any]:
    cache = read_catalog_cache(path)
    providers = cache.get("providers") if isinstance(cache.get("providers"), dict) else {}
    providers[profile_id] = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "models": models[:MAX_CATALOG_MODELS],
    }
    cache = {"schema_version": 1, "providers": providers}
    atomic_write_json_file(path, cache)
    return providers[profile_id]
