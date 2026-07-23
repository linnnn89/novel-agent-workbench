from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import atomic_write_json_file


MODEL_CATALOG_CACHE_FILENAME = "model_catalog_cache.json"
MAX_CATALOG_MODELS = 2000


class ModelCatalogError(RuntimeError):
    pass


def models_endpoint(base_url: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        raise ModelCatalogError("API 地址不能为空。")
    return f"{base}/models"


def normalize_catalog_payload(payload: object, *, provider_profile_id: str) -> list[dict[str, Any]]:
    source = payload if isinstance(payload, dict) else {}
    raw_models = source.get("data")
    if not isinstance(raw_models, list):
        raise ModelCatalogError("模型目录响应缺少 data 数组。")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_models[:MAX_CATALOG_MODELS]:
        if not isinstance(item, dict):
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
    return result


def fetch_model_catalog(
    *,
    provider_profile_id: str,
    base_url: str,
    api_key: str,
    timeout_seconds: float = 30.0,
) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        models_endpoint(base_url),
        headers={
            "Accept": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
            "User-Agent": "NovelAgentWorkbench/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=min(60.0, max(1.0, float(timeout_seconds)))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ModelCatalogError(f"模型目录请求失败：HTTP {int(exc.code)}。") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise ModelCatalogError(f"模型目录请求失败：{exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelCatalogError("模型目录返回了无法解析的 JSON。") from exc
    return normalize_catalog_payload(payload, provider_profile_id=provider_profile_id)


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
