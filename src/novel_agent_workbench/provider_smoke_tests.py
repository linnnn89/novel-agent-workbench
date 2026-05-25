from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .final_assembly_gates import validate_reason_code
from .providers import (
    ProviderError,
    ProviderRequest,
    get_model_role_config,
    provider_real_test,
    safe_url_host,
)
from .storage import ProjectStore, safe_filename, utc_stamp


PROVIDER_SMOKE_TESTS_DIRNAME = "provider_smoke_tests"
PROVIDER_SMOKE_TESTS_INDEX_FILENAME = "provider_smoke_tests_index.json"
PROVIDER_SMOKE_TEST_PROMPT = "Return exactly OK."
PROVIDER_SMOKE_TEST_PURPOSE = "provider_live_connectivity_smoke_test"
PROVIDER_SMOKE_TEST_PASSED_STATUS = "passed"
PROVIDER_SMOKE_TEST_FAILED_STATUS = "failed"


class ProviderSmokeTestError(RuntimeError):
    """Raised when a provider smoke-test artifact cannot be read or written."""


@dataclass(frozen=True, slots=True)
class ProviderSmokeTestResult:
    smoke_test_id: str
    role: str
    provider: str
    model: str
    status: str
    ok: bool
    path: str
    created_at: str
    network_attempted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderSmokeTestService:
    """Persistent metadata-only harness for live Provider connectivity checks."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store

    @property
    def smoke_tests_dir(self) -> Path:
        return self.store.data_dir / PROVIDER_SMOKE_TESTS_DIRNAME

    @property
    def index_path(self) -> Path:
        return self.store.data_dir / PROVIDER_SMOKE_TESTS_INDEX_FILENAME

    def run_smoke_test(
        self,
        *,
        role: str = "writer",
        prompt: str = PROVIDER_SMOKE_TEST_PROMPT,
        system_prompt: str = "",
        temperature: float | None = 0,
        max_tokens: int | None = 16,
        reason_code: str = "",
    ) -> ProviderSmokeTestResult:
        self.store.initialize()
        safe_reason = validate_reason_code(reason_code)
        request = ProviderRequest(
            role=role,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata={"provider_smoke_test": True, "purpose": PROVIDER_SMOKE_TEST_PURPOSE},
        )
        role_config = get_model_role_config(self.store, role)
        created_at = utc_stamp()
        smoke_test_id = f"{created_at}_{uuid4().hex[:12]}"

        try:
            real_result = provider_real_test(self.store, request)
            result = real_result.to_dict()
        except ProviderError as exc:
            result = {
                "ok": False,
                "role": role,
                "provider": role_config.provider,
                "model": role_config.model,
                "mode": "real_test",
                "message": exc.message,
                "network_attempted": False,
                "status_code": None,
                "error_type": exc.error_type,
                "base_url_host": safe_url_host(role_config.base_url),
                "finish_reason": "",
                "usage": {},
                "response_text_chars": 0,
            }
        artifact = smoke_test_artifact(
            smoke_test_id=smoke_test_id,
            created_at=created_at,
            request=request,
            role_config=role_config,
            reason_code=safe_reason,
            result=result,
        )

        path = self.smoke_tests_dir / f"{safe_filename(role)}__{safe_filename(smoke_test_id)}.json"
        self.store.write_json(path, artifact)
        self._append_index_entry(smoke_test_index_entry(artifact, path.relative_to(self.store.root).as_posix()))
        return ProviderSmokeTestResult(
            smoke_test_id=smoke_test_id,
            role=role,
            provider=str(artifact.get("provider") or ""),
            model=str(artifact.get("model") or ""),
            status=str(artifact.get("status") or ""),
            ok=bool(artifact.get("ok")),
            path=str(path),
            created_at=created_at,
            network_attempted=bool(artifact.get("network_attempted")),
        )

    def list_smoke_tests(self, *, status: str = "") -> list[dict[str, Any]]:
        index = self.store.read_json(self.index_path, default={"schema_version": 1, "provider_smoke_tests": []})
        if not isinstance(index, dict):
            return []
        items = index.get("provider_smoke_tests")
        if not isinstance(items, list):
            return []
        smoke_tests = [item for item in items if isinstance(item, dict)]
        if status:
            smoke_tests = [item for item in smoke_tests if item.get("status") == status]
        return smoke_tests

    def read_smoke_test(self, smoke_test_id: str) -> dict[str, Any]:
        entry = self._smoke_test_index_entry(smoke_test_id)
        path = entry.get("path")
        if not isinstance(path, str):
            raise ProviderSmokeTestError(f"Provider smoke test index entry has no path: {smoke_test_id}")
        artifact = self.store.read_json(path, default=None)
        if not isinstance(artifact, dict):
            raise ProviderSmokeTestError(f"Provider smoke test artifact is missing or invalid: {smoke_test_id}")
        return artifact

    def _append_index_entry(self, entry: dict[str, Any]) -> None:
        items = self.list_smoke_tests()
        items.append(entry)
        self.store.write_json(self.index_path, {"schema_version": 1, "provider_smoke_tests": items})

    def _smoke_test_index_entry(self, smoke_test_id: str) -> dict[str, Any]:
        for item in self.list_smoke_tests():
            if item.get("smoke_test_id") == smoke_test_id:
                return item
        raise ProviderSmokeTestError(f"Provider smoke test not found: {smoke_test_id}")


def smoke_test_artifact(
    *,
    smoke_test_id: str,
    created_at: str,
    request: ProviderRequest,
    role_config: Any,
    reason_code: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    ok = bool(result.get("ok"))
    network_attempted = bool(result.get("network_attempted"))
    status = PROVIDER_SMOKE_TEST_PASSED_STATUS if ok else PROVIDER_SMOKE_TEST_FAILED_STATUS
    return {
        "schema_version": 1,
        "smoke_test_id": smoke_test_id,
        "purpose": PROVIDER_SMOKE_TEST_PURPOSE,
        "created_at": created_at,
        "status": status,
        "ok": ok,
        "role": request.role,
        "provider": role_config.provider,
        "model": role_config.model,
        "base_url_host": safe_url_host(role_config.base_url),
        "config_snapshot": provider_config_snapshot(role_config),
        "network_attempted": network_attempted,
        "operator_trigger": {
            "user_triggered": True,
            "reason_code": reason_code,
            "triggered_at": created_at,
        },
        "request_summary": {
            "prompt_chars": len(request.prompt),
            "system_prompt_chars": len(request.system_prompt or ""),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "metadata_keys": sorted(str(key) for key in request.metadata),
        },
        "result": {
            "message": str(result.get("message") or ""),
            "status_code": result.get("status_code"),
            "error_type": str(result.get("error_type") or ""),
            "finish_reason": str(result.get("finish_reason") or ""),
            "usage": result.get("usage") if isinstance(result.get("usage"), dict) else {},
            "response_text_chars": int(result.get("response_text_chars") or 0),
        },
        "classification": {
            "sample_only": True,
            "non_committable": True,
            "writes_draft": False,
            "auto_commit": False,
        },
        "safety": provider_smoke_test_safety(
            network_attempted=network_attempted,
        ),
    }


def smoke_test_index_entry(artifact: dict[str, Any], path: str) -> dict[str, Any]:
    return {
        "smoke_test_id": artifact.get("smoke_test_id"),
        "purpose": artifact.get("purpose"),
        "created_at": artifact.get("created_at"),
        "status": artifact.get("status"),
        "ok": artifact.get("ok"),
        "role": artifact.get("role"),
        "provider": artifact.get("provider"),
        "model": artifact.get("model"),
        "base_url_host": artifact.get("base_url_host"),
        "network_attempted": artifact.get("network_attempted"),
        "path": path,
    }


def provider_config_snapshot(role_config: Any) -> dict[str, Any]:
    secret_name = ""
    try:
        secret_name = role_config.secret_name()
    except Exception:
        secret_name = ""
    return {
        "role": role_config.role,
        "provider": role_config.provider,
        "model": role_config.model,
        "base_url_host": safe_url_host(role_config.base_url),
        "api_key_ref": role_config.api_key_ref,
        "secret_name": secret_name,
        "has_api_key_ref": bool(role_config.api_key_ref),
    }


def provider_smoke_test_safety(*, network_attempted: bool) -> dict[str, bool]:
    return {
        "provider_called": network_attempted,
        "real_llm_called": network_attempted,
        "user_triggered": True,
        "prompt_text_stored": False,
        "system_prompt_text_stored": False,
        "response_text_stored": False,
        "secret_text_stored": False,
        "draft_created": False,
        "auto_commit": False,
        "confirmed_chapter_created": False,
        "memory_bank_touched": False,
        "rag_touched": False,
        "exports_touched": False,
        "ui_touched": False,
        "docx_touched": False,
    }
