from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

from .config import default_model_role
from .model_settings import FEATURE_IDS, resolve_model_role_mapping
from .storage import ProjectStore, utc_stamp


MODEL_ROLES = {"writer", "scorer", "reviser"}
SECRET_REF_PREFIX = "project_secret."
MOCK_PROVIDER_ID = "mock"
CHUTES_PROVIDER_ID = "chutes_openai"
SILICONFLOW_PROVIDER_ID = "siliconflow"
DEEPSEEK_PROVIDER_ID = "deepseek"
OPENROUTER_PROVIDER_ID = "openrouter"
LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID = "local_openai_compatible"
PROVIDER_CALL_LOG_FILENAME = "provider_call_log.json"
DISABLED_ADAPTER_IDS = (
    "openai_compatible",
    LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID,
    DEEPSEEK_PROVIDER_ID,
    CHUTES_PROVIDER_ID,
    SILICONFLOW_PROVIDER_ID,
    OPENROUTER_PROVIDER_ID,
)
REAL_NETWORK_PROVIDER_IDS = {
    "openai_compatible",
    LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID,
    DEEPSEEK_PROVIDER_ID,
    CHUTES_PROVIDER_ID,
    SILICONFLOW_PROVIDER_ID,
    OPENROUTER_PROVIDER_ID,
}
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 300.0
MIN_PROVIDER_TIMEOUT_SECONDS = 1.0
MAX_PROVIDER_TIMEOUT_SECONDS = 900.0
TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS = (1.0, 3.0)
REAL_GENERATION_BLOCKING_AUDIT_CODES = {
    "possible_secret_in_config",
    "raw_provider_api_key_in_config",
    "possible_prompt_in_provider_log",
    "possible_secret_in_provider_log",
    "possible_content_in_commit_log",
    "possible_secret_in_commit_log",
    "secrets_in_checkpoint",
    "possible_secret_in_public_state",
    "possible_prompt_or_content_in_public_state",
}


class ProviderConfigError(ValueError):
    """Raised when a model role provider configuration is invalid."""


class ProviderError(RuntimeError):
    """Raised when a provider client cannot complete a request."""

    def __init__(self, message: str, *, error_type: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


@dataclass(frozen=True, slots=True)
class ProviderAdapterInfo:
    adapter_id: str
    enabled: bool
    network_allowed: bool
    requires_secret: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("stream_callback", None)
        return data


@dataclass(frozen=True, slots=True)
class ModelRoleConfig:
    role: str
    provider: str
    model: str
    base_url: str
    api_key_ref: str
    settings: dict[str, Any]

    @classmethod
    def from_mapping(cls, role: str, value: object) -> "ModelRoleConfig":
        validate_role(role)
        source = value if isinstance(value, dict) else {}
        merged = default_model_role(role)
        for key, item in source.items():
            if key == "settings" and isinstance(item, dict):
                merged["settings"] = {**merged["settings"], **item}
            else:
                merged[key] = item
        return cls(
            role=role,
            provider=str(merged.get("provider") or "").strip(),
            model=str(merged.get("model") or "").strip(),
            base_url=str(merged.get("base_url") or "").strip(),
            api_key_ref=str(merged.get("api_key_ref") or "").strip(),
            settings=merged.get("settings") if isinstance(merged.get("settings"), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_configured(self) -> bool:
        return bool(self.provider and self.model)

    def secret_name(self) -> str:
        if not self.api_key_ref:
            return ""
        if not self.api_key_ref.startswith(SECRET_REF_PREFIX):
            raise ProviderConfigError("api_key_ref must use project_secret.<name>; raw keys are not allowed.")
        name = self.api_key_ref[len(SECRET_REF_PREFIX) :].strip()
        if not name or any(char in name for char in "/\\: "):
            raise ProviderConfigError(f"Invalid project secret reference: {self.api_key_ref!r}")
        return name


@dataclass(frozen=True, slots=True)
class ProviderConnectionResult:
    ok: bool
    role: str
    provider: str
    model: str
    mode: str
    message: str
    has_api_key: bool
    masked_key: str
    adapter_enabled: bool = False
    network_allowed: bool = False
    error_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderDryRunResult:
    ok: bool
    role: str
    provider: str
    model: str
    mode: str
    message: str
    adapter_enabled: bool
    network_allowed: bool
    error_type: str
    request_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderRealTestResult:
    ok: bool
    role: str
    provider: str
    model: str
    mode: str
    message: str
    network_attempted: bool
    status_code: int | None
    error_type: str
    base_url_host: str
    finish_reason: str
    usage: dict[str, int]
    response_text_chars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    role: str
    prompt: str
    system_prompt: str = ""
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    repetition_penalty: float | None = None
    stream: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    stream_callback: Callable[[str], None] | None = field(default=None, repr=False, compare=False)
    reasoning_callback: Callable[[str], None] | None = field(default=None, repr=False, compare=False)
    feature_id: str = ""

    def __post_init__(self) -> None:
        validate_role(self.role)
        if self.feature_id and self.feature_id not in FEATURE_IDS:
            raise ProviderError(f"Unknown model feature: {self.feature_id!r}.", error_type="invalid_request")
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ProviderError("Provider prompt cannot be empty.", error_type="invalid_request")
        if self.system_prompt is not None and not isinstance(self.system_prompt, str):
            raise ProviderError("system_prompt must be a string.", error_type="invalid_request")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ProviderError("max_tokens must be positive when provided.", error_type="invalid_request")
        if self.temperature is not None and self.temperature < 0:
            raise ProviderError("temperature must be non-negative when provided.", error_type="invalid_request")
        if self.top_p is not None and not 0 <= self.top_p <= 1:
            raise ProviderError("top_p must be between 0 and 1 when provided.", error_type="invalid_request")
        if self.top_k is not None and self.top_k <= 0:
            raise ProviderError("top_k must be positive when provided.", error_type="invalid_request")
        if self.min_p is not None and not 0 <= self.min_p <= 1:
            raise ProviderError("min_p must be between 0 and 1 when provided.", error_type="invalid_request")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("stream_callback", None)
        data.pop("reasoning_callback", None)
        return data


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    text: str
    usage: dict[str, int]
    model: str
    provider: str
    finish_reason: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderClient:
    """Base interface for provider clients."""

    role_config: ModelRoleConfig

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError


@dataclass(slots=True)
class DisabledProviderDryRunAdapter:
    role_config: ModelRoleConfig
    adapter_info: ProviderAdapterInfo

    def dry_run(self, request: ProviderRequest) -> ProviderDryRunResult:
        if request.role != self.role_config.role:
            raise ProviderError(
                f"Request role {request.role!r} does not match adapter role {self.role_config.role!r}.",
                error_type="invalid_request",
            )
        return ProviderDryRunResult(
            ok=False,
            role=request.role,
            provider=self.role_config.provider,
            model=self.role_config.model,
            mode="dry_run",
            message=f"Provider adapter {self.role_config.provider!r} is disabled; dry-run summary only.",
            adapter_enabled=False,
            network_allowed=False,
            error_type="adapter_disabled",
            request_summary=openai_compatible_request_summary(request, self.role_config),
        )


@dataclass(slots=True)
class MockProviderClient(ProviderClient):
    role_config: ModelRoleConfig

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if request.role != self.role_config.role:
            raise ProviderError(
                f"Request role {request.role!r} does not match client role {self.role_config.role!r}.",
                error_type="invalid_request",
            )
        simulate_error = str(request.metadata.get("simulate_error") or self.role_config.settings.get("simulate_error") or "")
        if simulate_error:
            raise simulated_provider_error(simulate_error)
        if not self.role_config.model:
            raise ProviderError("Mock provider requires a model id.", error_type="missing_model")
        prompt_tokens = count_placeholder_tokens(request.prompt)
        system_tokens = count_placeholder_tokens(request.system_prompt)
        completion_tokens = min(max(request.max_tokens or 64, 1), 64)
        role_text = {
            "writer": "MOCK writer draft placeholder.",
            "scorer": "MOCK scorer result: pass=false score=0.",
            "reviser": "MOCK reviser placeholder.",
        }[request.role]
        text = f"{role_text} prompt_chars={len(request.prompt)}"
        if request.stream_callback is not None:
            request.stream_callback(text)
        return ProviderResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens + system_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + system_tokens + completion_tokens,
            },
            model=self.role_config.model,
            provider=MOCK_PROVIDER_ID,
            finish_reason="stop",
            raw_metadata={"mode": "mock", "metadata_keys": sorted(str(key) for key in request.metadata)},
        )


@dataclass(slots=True)
class OpenAICompatibleProviderClient(ProviderClient):
    role_config: ModelRoleConfig
    api_key: str
    timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        if request.role != self.role_config.role:
            raise ProviderError(
                f"Request role {request.role!r} does not match client role {self.role_config.role!r}.",
                error_type="invalid_request",
            )
        if not self.role_config.model:
            raise ProviderError("Provider requires a model id.", error_type="missing_model")
        if not self.role_config.base_url:
            raise ProviderError("Provider requires base_url.", error_type="missing_base_url")
        retry_delays = TRANSIENT_PROVIDER_RETRY_DELAYS_SECONDS
        for attempt_index in range(len(retry_delays) + 1):
            try:
                status_code, data = send_openai_compatible_chat_completion(
                    role_config=self.role_config,
                    request=request,
                    api_key=self.api_key,
                    timeout_seconds=self.timeout_seconds,
                )
                break
            except urllib.error.HTTPError as exc:
                raise ProviderError(f"HTTP error {int(exc.code)} from provider.", error_type="http_error") from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
                if attempt_index >= len(retry_delays):
                    attempts = attempt_index + 1
                    message = f"{network_error_message('provider generation', exc)} Attempts: {attempts}."
                    raise ProviderError(message, error_type="network_error") from exc
                time.sleep(retry_delays[attempt_index])
        if not 200 <= status_code < 300:
            raise ProviderError(f"HTTP error {status_code} from provider.", error_type="http_error")
        first_choice = first_response_choice(data)
        text = choice_text(first_choice)
        if not text:
            raise ProviderError("Provider response did not contain assistant content.", error_type="empty_response")
        usage = data.get("usage") if isinstance(data, dict) and isinstance(data.get("usage"), dict) else {}
        return ProviderResponse(
            text=text,
            usage=safe_usage(usage),
            model=self.role_config.model,
            provider=self.role_config.provider,
            finish_reason=str(first_choice.get("finish_reason") or "") if isinstance(first_choice, dict) else "",
            raw_metadata={
                "mode": "real_generation",
                "status_code": status_code,
                "base_url_host": safe_url_host(self.role_config.base_url),
                "response_text_chars": len(text),
            },
        )


ChutesOpenAIProviderClient = OpenAICompatibleProviderClient


PROVIDER_ADAPTER_REGISTRY: dict[str, ProviderAdapterInfo] = {
    MOCK_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=MOCK_PROVIDER_ID,
        enabled=True,
        network_allowed=False,
        requires_secret=False,
        description="Deterministic local test adapter. No network and no real LLM.",
    ),
    "openai_compatible": ProviderAdapterInfo(
        adapter_id="openai_compatible",
        enabled=True,
        network_allowed=True,
        requires_secret=True,
        description="OpenAI-compatible HTTP adapter. Network is used only when the user starts a connection test or generation.",
    ),
    LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID,
        enabled=True,
        network_allowed=True,
        requires_secret=False,
        description="Local OpenAI-compatible endpoint for LM Studio/Ollama-style services.",
    ),
    DEEPSEEK_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=DEEPSEEK_PROVIDER_ID,
        enabled=True,
        network_allowed=True,
        requires_secret=True,
        description="DeepSeek OpenAI-compatible adapter.",
    ),
    CHUTES_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=CHUTES_PROVIDER_ID,
        enabled=True,
        network_allowed=True,
        requires_secret=True,
        description="Chutes OpenAI-compatible adapter.",
    ),
    SILICONFLOW_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=SILICONFLOW_PROVIDER_ID,
        enabled=True,
        network_allowed=True,
        requires_secret=True,
        description="SiliconFlow OpenAI-compatible adapter.",
    ),
    OPENROUTER_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=OPENROUTER_PROVIDER_ID,
        enabled=True,
        network_allowed=True,
        requires_secret=True,
        description="OpenRouter OpenAI-compatible Chat Completions adapter.",
    ),
}


def get_model_role_config(store: ProjectStore, role: str) -> ModelRoleConfig:
    validate_role(role)
    config = store.read_config()
    roles = config.get("model_roles") if isinstance(config.get("model_roles"), dict) else {}
    return ModelRoleConfig.from_mapping(role, roles.get(role))


def get_effective_model_role_config(
    store: ProjectStore,
    role: str,
    *,
    feature_id: str = "",
) -> ModelRoleConfig:
    validate_role(role)
    config = store.read_config()
    resolved = resolve_model_role_mapping(config, role=role, feature_id=feature_id)
    if resolved:
        return ModelRoleConfig.from_mapping(role, resolved)
    return get_model_role_config(store, role)


def provider_request_role_or_writer_fallback(
    store: ProjectStore,
    preferred_role: str,
    *,
    feature_id: str = "",
) -> str:
    validate_role(preferred_role)
    preferred = get_effective_model_role_config(store, preferred_role, feature_id=feature_id)
    if preferred.provider and preferred.model:
        return preferred_role
    writer = get_effective_model_role_config(store, "writer", feature_id=feature_id)
    if writer.provider and writer.model:
        return "writer"
    return preferred_role


def set_model_role_config(store: ProjectStore, role: str, updates: dict[str, Any]) -> ModelRoleConfig:
    validate_role(role)
    if "api_key" in updates:
        raise ProviderConfigError("Do not store raw api_key in model role config; write secrets separately.")
    current = store.read_config()
    roles = current.get("model_roles") if isinstance(current.get("model_roles"), dict) else {}
    role_config = ModelRoleConfig.from_mapping(role, {**default_model_role(role), **(roles.get(role) or {}), **updates})
    validate_model_role_config(role_config, store.read_secrets())
    current["model_roles"] = {**roles, role: role_config.to_dict()}
    store.write_config(current)
    return role_config


def configure_provider_role(
    store: ProjectStore,
    role: str,
    *,
    provider: str,
    model: str,
    api_key_ref: str = "",
    base_url: str = "",
    settings: dict[str, Any] | None = None,
) -> ModelRoleConfig:
    provider = str(provider or "").strip()
    model = str(model or "").strip()
    if not provider:
        raise ProviderConfigError("provider is required.")
    if not model:
        raise ProviderConfigError("model is required.")
    adapter = get_provider_adapter(provider)
    if adapter is None:
        raise ProviderConfigError(f"Provider adapter is not registered: {provider!r}")
    updates: dict[str, Any] = {"provider": provider, "model": model, "base_url": str(base_url or "").strip()}
    if api_key_ref:
        updates["api_key_ref"] = str(api_key_ref).strip()
    if settings:
        updates["settings"] = dict(settings)
    role_config = ModelRoleConfig.from_mapping(role, {**default_model_role(role), **updates})
    if adapter.requires_secret and not role_config.api_key_ref:
        raise ProviderConfigError(f"Provider {provider!r} requires api_key_ref.")
    validate_model_role_config(role_config, store.read_secrets(), require_secret_value=False)
    return set_model_role_config_without_secret_value_requirement(store, role, role_config)


def set_model_role_config_without_secret_value_requirement(
    store: ProjectStore, role: str, role_config: ModelRoleConfig
) -> ModelRoleConfig:
    current = store.read_config()
    roles = current.get("model_roles") if isinstance(current.get("model_roles"), dict) else {}
    current["model_roles"] = {**roles, role: role_config.to_dict()}
    store.write_config(current)
    return role_config


def set_project_secret(store: ProjectStore, name: str, value: str) -> dict[str, Any]:
    secret_name = validate_secret_name(name)
    if not isinstance(value, str) or not value:
        raise ProviderConfigError("secret value cannot be empty.")
    store.update_secrets({secret_name: value})
    return {"name": secret_name, "has_value": True, "masked": mask_secret(value)}


def fake_test_model_role(store: ProjectStore, role: str) -> ProviderConnectionResult:
    role_config = get_model_role_config(store, role)
    adapter = get_provider_adapter(role_config.provider) if role_config.provider else None
    try:
        validate_model_role_config(role_config, store.read_secrets(), require_secret_value=False)
    except ProviderConfigError as exc:
        return ProviderConnectionResult(
            ok=False,
            role=role,
            provider=role_config.provider,
            model=role_config.model,
            mode="fake",
            message=str(exc),
            has_api_key=False,
            masked_key="",
            adapter_enabled=bool(adapter.enabled) if adapter else False,
            network_allowed=False,
            error_type=provider_config_error_type(str(exc)),
        )
    if not role_config.is_configured():
        return ProviderConnectionResult(
            ok=False,
            role=role,
            provider=role_config.provider,
            model=role_config.model,
            mode="fake",
            message="Model role is not configured.",
            has_api_key=False,
            masked_key="",
            adapter_enabled=False,
            network_allowed=False,
            error_type="missing_provider",
        )
    if adapter is None:
        return ProviderConnectionResult(
            ok=False,
            role=role,
            provider=role_config.provider,
            model=role_config.model,
            mode="fake",
            message=f"Provider {role_config.provider!r} is not registered.",
            has_api_key=False,
            masked_key="",
            adapter_enabled=False,
            network_allowed=False,
            error_type="unsupported_provider",
        )
    secret_name = role_config.secret_name()
    secret_value = ""
    if secret_name:
        try:
            secret_value = resolve_project_secret(store, role_config.api_key_ref)
        except ProviderError as exc:
            return ProviderConnectionResult(
                ok=False,
                role=role,
                provider=role_config.provider,
                model=role_config.model,
                mode="fake",
                message=exc.message,
                has_api_key=False,
                masked_key="",
                adapter_enabled=adapter.enabled,
                network_allowed=adapter.network_allowed,
                error_type=exc.error_type,
            )
    elif adapter.requires_secret:
        return ProviderConnectionResult(
            ok=False,
            role=role,
            provider=role_config.provider,
            model=role_config.model,
            mode="fake",
            message=f"Provider {role_config.provider!r} requires api_key_ref.",
            has_api_key=False,
            masked_key="",
            adapter_enabled=adapter.enabled,
            network_allowed=adapter.network_allowed,
            error_type="missing_secret_ref",
        )
    if role_config.provider in REAL_NETWORK_PROVIDER_IDS:
        return ProviderConnectionResult(
            ok=True,
            role=role,
            provider=role_config.provider,
            model=role_config.model,
            mode="fake",
            message="Provider is configured; this status check did not make a network request.",
            has_api_key=bool(secret_value),
            masked_key=mask_secret(secret_value),
            adapter_enabled=True,
            network_allowed=True,
            error_type="",
        )
    if not adapter.enabled:
        return ProviderConnectionResult(
            ok=False,
            role=role,
            provider=role_config.provider,
            model=role_config.model,
            mode="fake",
            message=f"Provider adapter {role_config.provider!r} is disabled; no network request was made.",
            has_api_key=bool(secret_value),
            masked_key=mask_secret(secret_value),
            adapter_enabled=False,
            network_allowed=False,
            error_type="adapter_disabled",
        )
    return ProviderConnectionResult(
        ok=True,
        role=role,
        provider=role_config.provider,
        model=role_config.model,
        mode="fake",
        message="Fake connection test passed; no network request was made.",
        has_api_key=bool(secret_value),
        masked_key=mask_secret(secret_value),
        adapter_enabled=True,
        network_allowed=False,
        error_type="",
    )


def create_provider_client(store: ProjectStore, role: str, *, feature_id: str = "") -> ProviderClient:
    role_config = get_effective_model_role_config(store, role, feature_id=feature_id)
    if not role_config.provider:
        raise ProviderError("Model role has no provider configured.", error_type="missing_provider")
    adapter = get_provider_adapter(role_config.provider)
    if adapter is None:
        raise ProviderError(
            f"Provider {role_config.provider!r} is not registered.",
            error_type="unsupported_provider",
        )
    if role_config.provider in REAL_NETWORK_PROVIDER_IDS:
        secret_value = validate_real_generation_request(store, role_config)
        return OpenAICompatibleProviderClient(
            role_config=role_config,
            api_key=secret_value,
            timeout_seconds=provider_timeout_seconds(role_config),
        )
    if not adapter.enabled:
        raise ProviderError(
            f"Provider adapter {role_config.provider!r} is disabled; no network request was made.",
            error_type="adapter_disabled",
        )
    if role_config.provider != MOCK_PROVIDER_ID:
        raise ProviderError(f"Provider {role_config.provider!r} is not available.", error_type="unsupported_provider")
    validate_mock_role_config(store, role_config)
    return MockProviderClient(role_config=role_config)


def validate_real_generation_request(store: ProjectStore, role_config: ModelRoleConfig) -> str:
    if role_config.provider not in REAL_NETWORK_PROVIDER_IDS:
        raise ProviderError("Real generation requires an OpenAI-compatible provider.", error_type="unsupported_real_provider")
    if not role_config.model:
        raise ProviderError("Provider requires a model id.", error_type="missing_model")
    if not role_config.base_url:
        raise ProviderError("Provider requires base_url.", error_type="missing_base_url")
    adapter = get_provider_adapter(role_config.provider)
    if adapter and adapter.requires_secret:
        secret_value = resolve_project_secret(store, role_config.api_key_ref)
    else:
        secret_value = resolve_project_secret(store, role_config.api_key_ref) if role_config.api_key_ref else ""
    return secret_value


def real_generation_blocking_audit_codes(store: ProjectStore) -> list[str]:
    from .audit import audit_project

    result = audit_project(store)
    codes = sorted(
        {
            str(item.get("code"))
            for item in result.get("findings", [])
            if isinstance(item, dict) and str(item.get("code")) in REAL_GENERATION_BLOCKING_AUDIT_CODES
        }
    )
    return codes


def generate_with_provider(store: ProjectStore, request: ProviderRequest) -> ProviderResponse:
    call_id = str(uuid4())
    client: ProviderClient | None = None
    try:
        client = create_provider_client(store, request.role, feature_id=request.feature_id)
        response = client.generate(request)
        append_provider_call_log(
            store,
            provider_call_log_entry(
                call_id=call_id,
                request=request,
                role_config=client.role_config,
                status="ok",
                error_type="",
                usage=response.usage,
            ),
        )
        return response
    except ProviderError as exc:
        role_config = (
            client.role_config
            if client
            else get_effective_model_role_config(store, request.role, feature_id=request.feature_id)
        )
        append_provider_call_log(
            store,
            provider_call_log_entry(
                call_id=call_id,
                request=request,
                role_config=role_config,
                status="error",
                error_type=exc.error_type,
                usage={},
            ),
        )
        raise


def validate_model_role_config(
    config: ModelRoleConfig, secrets: dict[str, Any], *, require_secret_value: bool = True
) -> None:
    validate_role(config.role)
    if config.provider and not is_safe_identifier(config.provider):
        raise ProviderConfigError(f"Invalid provider id: {config.provider!r}")
    if "api_key" in config.settings:
        raise ProviderConfigError("Do not store raw api_key in model role settings.")
    provider_timeout_seconds(config)
    if config.api_key_ref:
        secret_name = config.secret_name()
        if require_secret_value and (secret_name not in secrets or not str(secrets.get(secret_name) or "")):
            raise ProviderConfigError(f"Missing project secret: {secret_name}")


def validate_mock_role_config(store: ProjectStore, config: ModelRoleConfig) -> None:
    validate_role(config.role)
    if config.provider != MOCK_PROVIDER_ID:
        raise ProviderError("Only mock provider is supported by validate_mock_role_config.", error_type="unsupported_provider")
    if not config.model:
        raise ProviderError("Mock provider requires a model id.", error_type="missing_model")
    require_secret = bool(config.settings.get("require_api_key_ref"))
    if require_secret and not config.api_key_ref:
        raise ProviderError("Mock provider config requires api_key_ref.", error_type="missing_secret_ref")
    if config.api_key_ref:
        resolve_project_secret(store, config.api_key_ref)


def get_provider_adapter(provider_id: str) -> ProviderAdapterInfo | None:
    if not provider_id:
        return None
    return PROVIDER_ADAPTER_REGISTRY.get(provider_id)


def list_provider_adapters() -> list[dict[str, Any]]:
    return [PROVIDER_ADAPTER_REGISTRY[key].to_dict() for key in sorted(PROVIDER_ADAPTER_REGISTRY)]


def provider_status(store: ProjectStore, role: str) -> ProviderConnectionResult:
    return fake_test_model_role(store, role)


def provider_dry_run(store: ProjectStore, request: ProviderRequest) -> ProviderDryRunResult:
    role_config = get_model_role_config(store, request.role)
    adapter = get_provider_adapter(role_config.provider) if role_config.provider else None
    if not role_config.is_configured():
        return ProviderDryRunResult(
            ok=False,
            role=request.role,
            provider=role_config.provider,
            model=role_config.model,
            mode="dry_run",
            message="Model role is not configured.",
            adapter_enabled=False,
            network_allowed=False,
            error_type="missing_provider",
            request_summary={},
        )
    if adapter is None:
        return ProviderDryRunResult(
            ok=False,
            role=request.role,
            provider=role_config.provider,
            model=role_config.model,
            mode="dry_run",
            message=f"Provider {role_config.provider!r} is not registered.",
            adapter_enabled=False,
            network_allowed=False,
            error_type="unsupported_provider",
            request_summary={},
        )
    if adapter.requires_secret and not role_config.api_key_ref:
        return ProviderDryRunResult(
            ok=False,
            role=request.role,
            provider=role_config.provider,
            model=role_config.model,
            mode="dry_run",
            message=f"Provider {role_config.provider!r} requires api_key_ref.",
            adapter_enabled=adapter.enabled,
            network_allowed=adapter.network_allowed,
            error_type="missing_secret_ref",
            request_summary={},
        )
    if role_config.api_key_ref:
        try:
            resolve_project_secret(store, role_config.api_key_ref)
        except ProviderError as exc:
            return ProviderDryRunResult(
                ok=False,
                role=request.role,
                provider=role_config.provider,
                model=role_config.model,
                mode="dry_run",
                message=exc.message,
                adapter_enabled=adapter.enabled,
                network_allowed=adapter.network_allowed,
                error_type=exc.error_type,
                request_summary={},
            )
    if role_config.provider == MOCK_PROVIDER_ID:
        return ProviderDryRunResult(
            ok=True,
            role=request.role,
            provider=role_config.provider,
            model=role_config.model,
            mode="dry_run",
            message="Mock provider dry-run summary only; no network request was made.",
            adapter_enabled=True,
            network_allowed=False,
            error_type="",
            request_summary=openai_compatible_request_summary(request, role_config),
        )
    if role_config.provider in REAL_NETWORK_PROVIDER_IDS:
        return ProviderDryRunResult(
            ok=True,
            role=request.role,
            provider=role_config.provider,
            model=role_config.model,
            mode="dry_run",
            message="Provider request summary only; no network request was made.",
            adapter_enabled=True,
            network_allowed=True,
            error_type="",
            request_summary=openai_compatible_request_summary(request, role_config),
        )
    result = DisabledProviderDryRunAdapter(role_config=role_config, adapter_info=adapter).dry_run(request)
    return ProviderDryRunResult(
        ok=result.ok,
        role=result.role,
        provider=result.provider,
        model=result.model,
        mode=result.mode,
        message=result.message,
        adapter_enabled=result.adapter_enabled,
        network_allowed=result.network_allowed,
        error_type=result.error_type,
        request_summary=result.request_summary,
    )


def provider_real_test(store: ProjectStore, request: ProviderRequest, *, timeout_seconds: float = 30.0) -> ProviderRealTestResult:
    role_config = get_model_role_config(store, request.role)
    if role_config.provider not in REAL_NETWORK_PROVIDER_IDS:
        raise ProviderError("Provider real test requires an OpenAI-compatible provider.", error_type="unsupported_provider")
    if not role_config.model:
        raise ProviderError("Provider real test requires a model id.", error_type="missing_model")
    if not role_config.base_url:
        raise ProviderError("Provider real test requires base_url.", error_type="missing_base_url")
    adapter = get_provider_adapter(role_config.provider)
    if adapter and adapter.requires_secret:
        secret_value = resolve_project_secret(store, role_config.api_key_ref)
    else:
        secret_value = resolve_project_secret(store, role_config.api_key_ref) if role_config.api_key_ref else ""
    try:
        status_code, data = send_openai_compatible_chat_completion(
            role_config=role_config,
            request=request,
            api_key=secret_value,
            timeout_seconds=timeout_seconds,
        )
    except urllib.error.HTTPError as exc:
        return provider_real_test_error_result(
            request=request,
            role_config=role_config,
            status_code=int(exc.code),
            error_type="http_error",
            message=f"HTTP error {int(exc.code)} from provider.",
        )
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return provider_real_test_error_result(
            request=request,
            role_config=role_config,
            status_code=None,
            error_type="network_error",
            message=network_error_message("provider real test", exc),
        )
    except ProviderError as exc:
        return provider_real_test_error_result(
            request=request,
            role_config=role_config,
            status_code=None,
            error_type=exc.error_type,
            message=exc.message,
        )
    usage = data.get("usage") if isinstance(data, dict) and isinstance(data.get("usage"), dict) else {}
    first_choice = first_response_choice(data)
    text = choice_text(first_choice)
    return ProviderRealTestResult(
        ok=200 <= status_code < 300,
        role=request.role,
        provider=role_config.provider,
        model=role_config.model,
        mode="real_test",
        message="Provider real test completed; response text was not returned.",
        network_attempted=True,
        status_code=status_code,
        error_type="" if 200 <= status_code < 300 else "http_error",
        base_url_host=safe_url_host(role_config.base_url),
        finish_reason=str(first_choice.get("finish_reason") or "") if isinstance(first_choice, dict) else "",
        usage=safe_usage(usage),
        response_text_chars=len(text),
    )


def provider_real_test_error_result(
    *,
    request: ProviderRequest,
    role_config: ModelRoleConfig,
    status_code: int | None,
    error_type: str,
    message: str,
) -> ProviderRealTestResult:
    return ProviderRealTestResult(
        ok=False,
        role=request.role,
        provider=role_config.provider,
        model=role_config.model,
        mode="real_test",
        message=message,
        network_attempted=True,
        status_code=status_code,
        error_type=error_type,
        base_url_host=safe_url_host(role_config.base_url),
        finish_reason="",
        usage={},
        response_text_chars=0,
    )


def openai_compatible_request_summary(request: ProviderRequest, role_config: ModelRoleConfig) -> dict[str, Any]:
    return {
        "provider": role_config.provider,
        "model": role_config.model,
        "base_url_host": safe_url_host(role_config.base_url),
        "request_format": provider_request_format(role_config),
        "message_count": 2 if request.system_prompt else 1,
        "prompt_chars": len(request.prompt),
        "system_prompt_chars": len(request.system_prompt or ""),
        "temperature": request.temperature,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "min_p": request.min_p,
        "max_tokens": request.max_tokens,
        "presence_penalty": request.presence_penalty,
        "frequency_penalty": request.frequency_penalty,
        "repetition_penalty": request.repetition_penalty,
        "stream_requested": should_stream_response(request, role_config),
        "timeout_seconds": provider_timeout_seconds(role_config),
        "sent_parameter_keys": provider_sent_parameter_keys(request, role_config),
        "ignored_parameter_keys": provider_ignored_parameter_keys(request, role_config),
        "metadata_keys": sorted(str(key) for key in request.metadata),
    }


def safe_url_host(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc.split("@")[-1]


def network_error_message(context: str, exc: BaseException) -> str:
    detail = safe_network_error_detail(exc)
    if detail:
        return f"Network error during {context}: {detail}"
    return f"Network error during {context}."


def safe_network_error_detail(exc: BaseException) -> str:
    reason: object = exc
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
    text = str(reason or exc.__class__.__name__).strip()
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if not text:
        text = exc.__class__.__name__
    for prefix in ("http://", "https://"):
        while prefix in text:
            start = text.find(prefix)
            end = len(text)
            for separator in (" ", "'", '"', ")", "]", "}"):
                position = text.find(separator, start)
                if position != -1:
                    end = min(end, position)
            host = safe_url_host(text[start:end])
            replacement = f"{prefix}{host}" if host else "[provider_url]"
            text = f"{text[:start]}{replacement}{text[end:]}"
    return text[:240]


def provider_timeout_seconds(role_config: ModelRoleConfig) -> float:
    raw = role_config.settings.get("timeout_seconds")
    if raw is None or raw == "":
        return DEFAULT_PROVIDER_TIMEOUT_SECONDS
    if isinstance(raw, bool):
        raise ProviderConfigError("timeout_seconds must be a number.")
    try:
        parsed = float(raw)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigError("timeout_seconds must be a number.") from exc
    if not MIN_PROVIDER_TIMEOUT_SECONDS <= parsed <= MAX_PROVIDER_TIMEOUT_SECONDS:
        raise ProviderConfigError(
            f"timeout_seconds must be between {int(MIN_PROVIDER_TIMEOUT_SECONDS)} and {int(MAX_PROVIDER_TIMEOUT_SECONDS)}."
        )
    return parsed


def chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def send_openai_compatible_chat_completion(
    *,
    role_config: ModelRoleConfig,
    request: ProviderRequest,
    api_key: str,
    timeout_seconds: float,
) -> tuple[int, dict[str, Any]]:
    endpoint = chat_completions_url(role_config.base_url)
    stream_response = should_stream_response(request, role_config)
    supported_sampling_keys = provider_supported_sampling_keys(role_config)
    payload = {
        "model": role_config.model,
        "messages": openai_compatible_messages(request),
        "stream": stream_response,
        "max_tokens": request.max_tokens or 16,
    }
    if stream_response and role_config.provider == DEEPSEEK_PROVIDER_ID:
        payload["stream_options"] = {"include_usage": True}
    if request.temperature is not None and "temperature" in supported_sampling_keys:
        payload["temperature"] = request.temperature
    payload.update(openai_compatible_sampling_payload(request, role_config))
    payload.update(provider_format_payload(role_config))
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )
    if api_key:
        http_request.add_header("Authorization", f"Bearer {api_key}")
    if role_config.provider == OPENROUTER_PROVIDER_ID:
        http_request.add_header("X-OpenRouter-Title", "NovelAgentWorkbench")
    with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
        status_code = int(getattr(response, "status", 200))
        if stream_response:
            return status_code, read_openai_compatible_stream_response(
                response,
                stream_callback=request.stream_callback,
                reasoning_callback=request.reasoning_callback,
            )
        response_body = response.read()
    return status_code, parse_openai_compatible_json_response(response_body)


def should_stream_response(request: ProviderRequest, role_config: ModelRoleConfig) -> bool:
    if role_config.provider == CHUTES_PROVIDER_ID:
        return True
    return bool(request.stream)


def parse_openai_compatible_json_response(response_body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(response_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderError("Provider response was not valid JSON.", error_type="invalid_response") from exc
    if not isinstance(data, dict):
        raise ProviderError("Provider response was not a JSON object.", error_type="invalid_response")
    return data


def read_openai_compatible_stream_response(
    response: Any,
    *,
    stream_callback: Callable[[str], None] | None = None,
    reasoning_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if not hasattr(response, "readline"):
        return parse_openai_compatible_json_response(response.read())
    content_parts: list[str] = []
    finish_reason = ""
    usage: dict[str, Any] = {}
    while True:
        line = response.readline()
        if not line:
            break
        stripped = line.strip()
        if not stripped:
            continue
        if is_sse_control_line(stripped):
            continue
        if not stripped.startswith(b"data:"):
            remainder = response.read() if hasattr(response, "read") else b""
            return parse_openai_compatible_json_response(line + remainder)
        data_text = stripped[len(b"data:") :].strip()
        if data_text == b"[DONE]":
            break
        try:
            chunk = json.loads(data_text.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ProviderError("Provider stream chunk was not valid JSON.", error_type="invalid_response") from exc
        if not isinstance(chunk, dict):
            raise ProviderError("Provider stream chunk was not a JSON object.", error_type="invalid_response")
        if isinstance(chunk.get("usage"), dict):
            usage = chunk["usage"]
        choice = first_response_choice(chunk)
        if not choice:
            continue
        delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = delta.get("content") if isinstance(delta, dict) else ""
        if content is None:
            content = message.get("content") if isinstance(message, dict) else ""
        reasoning_content = delta.get("reasoning_content") if isinstance(delta, dict) else ""
        if reasoning_content is None:
            reasoning_content = message.get("reasoning_content") if isinstance(message, dict) else ""
        if reasoning_content and reasoning_callback is not None:
            reasoning_callback(str(reasoning_content))
        if content:
            text = str(content)
            content_parts.append(text)
            if stream_callback is not None:
                stream_callback(text)
        if choice.get("finish_reason"):
            finish_reason = str(choice.get("finish_reason") or "")
    return {
        "choices": [
            {
                "message": {"content": "".join(content_parts)},
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage,
    }


def is_sse_control_line(line: bytes) -> bool:
    lowered = line.lower()
    return (
        lowered.startswith(b":")
        or lowered.startswith(b"event:")
        or lowered.startswith(b"id:")
        or lowered.startswith(b"retry:")
    )


def openai_compatible_messages(request: ProviderRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages


def provider_request_format(role_config: ModelRoleConfig) -> str:
    if role_config.provider == DEEPSEEK_PROVIDER_ID:
        return "deepseek_chat_completions_non_thinking"
    if role_config.provider == OPENROUTER_PROVIDER_ID:
        return "openrouter_chat_completions"
    if role_config.provider == CHUTES_PROVIDER_ID:
        return "chutes_openai_chat_completions"
    if role_config.provider == LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID:
        return "local_openai_compatible_chat_completions"
    return "openai_compatible_chat_completions"


def provider_format_payload(role_config: ModelRoleConfig) -> dict[str, Any]:
    if role_config.provider == DEEPSEEK_PROVIDER_ID:
        return {"thinking": deepseek_thinking_payload(role_config)}
    return {}


def deepseek_thinking_payload(role_config: ModelRoleConfig) -> dict[str, Any]:
    raw = role_config.settings.get("thinking")
    if isinstance(raw, dict):
        value = str(raw.get("type") or "").strip().lower()
        if value == "enabled":
            payload = {"type": "enabled"}
            effort = str(raw.get("reasoning_effort") or "").strip().lower()
            if effort in {"high", "max"}:
                payload["reasoning_effort"] = effort
            return payload
        if value == "disabled":
            return {"type": "disabled"}
    if str(raw or "").strip().lower() == "enabled":
        return {"type": "enabled"}
    return {"type": "disabled"}


def provider_supported_sampling_keys(role_config: ModelRoleConfig) -> set[str]:
    provider = role_config.provider
    keys = {"temperature", "top_p", "max_tokens", "stream"}
    if provider == DEEPSEEK_PROVIDER_ID:
        if deepseek_thinking_payload(role_config).get("type") == "enabled":
            return {"max_tokens", "stream"}
        return keys
    if provider == OPENROUTER_PROVIDER_ID:
        return keys | {"presence_penalty", "frequency_penalty", "top_k", "min_p", "repetition_penalty"}
    if provider == LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID:
        return keys | {"presence_penalty", "frequency_penalty", "top_k", "min_p", "repetition_penalty"}
    return keys | {"presence_penalty", "frequency_penalty"}


def request_sampling_values(request: ProviderRequest) -> dict[str, Any]:
    return {
        "temperature": request.temperature,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "min_p": request.min_p,
        "max_tokens": request.max_tokens,
        "presence_penalty": request.presence_penalty,
        "frequency_penalty": request.frequency_penalty,
        "repetition_penalty": request.repetition_penalty,
        "stream": request.stream,
    }


def provider_sent_parameter_keys(request: ProviderRequest, role_config: ModelRoleConfig) -> list[str]:
    supported = provider_supported_sampling_keys(role_config)
    keys = [key for key, value in request_sampling_values(request).items() if value is not None and key in supported]
    if role_config.provider == DEEPSEEK_PROVIDER_ID:
        keys.append("thinking")
    return sorted(set(keys))


def provider_ignored_parameter_keys(request: ProviderRequest, role_config: ModelRoleConfig) -> list[str]:
    supported = provider_supported_sampling_keys(role_config)
    return sorted(key for key, value in request_sampling_values(request).items() if value is not None and key not in supported)


def openai_compatible_sampling_payload(request: ProviderRequest, role_config: ModelRoleConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    provider = role_config.provider
    supported = provider_supported_sampling_keys(role_config)
    if request.top_p is not None and "top_p" in supported:
        payload["top_p"] = request.top_p
    if request.presence_penalty is not None and "presence_penalty" in supported:
        payload["presence_penalty"] = request.presence_penalty
    if request.frequency_penalty is not None and "frequency_penalty" in supported:
        payload["frequency_penalty"] = request.frequency_penalty
    if provider in {LOCAL_OPENAI_COMPATIBLE_PROVIDER_ID, OPENROUTER_PROVIDER_ID}:
        if request.top_k is not None:
            payload["top_k"] = request.top_k
        if request.min_p is not None:
            payload["min_p"] = request.min_p
        if request.repetition_penalty is not None:
            payload["repetition_penalty"] = request.repetition_penalty
    return payload


def first_response_choice(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    first = choices[0]
    return first if isinstance(first, dict) else {}


def choice_text(choice: dict[str, Any]) -> str:
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = message.get("content") if isinstance(message, dict) else ""
    return str(content or "")


def safe_usage(value: dict[str, Any]) -> dict[str, int]:
    safe: dict[str, int] = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    ):
        item = value.get(key)
        if isinstance(item, int):
            safe[key] = item
    return safe


def resolve_project_secret(store: ProjectStore, api_key_ref: str) -> str:
    if not api_key_ref:
        raise ProviderError("Provider config is missing api_key_ref.", error_type="missing_secret_ref")
    if not api_key_ref.startswith(SECRET_REF_PREFIX):
        raise ProviderError("api_key_ref must use project_secret.<name>.", error_type="invalid_secret_ref")
    name = api_key_ref[len(SECRET_REF_PREFIX) :].strip()
    if not is_safe_secret_name(name):
        raise ProviderError("api_key_ref must use project_secret.<name>.", error_type="invalid_secret_ref")
    secrets = store.read_secrets()
    if name not in secrets:
        raise ProviderError(f"Missing project secret: {name}", error_type="missing_secret")
    value = str(secrets.get(name) or "")
    if not value:
        raise ProviderError(f"Project secret is empty: {name}", error_type="empty_secret")
    return value


def validate_secret_name(name: str) -> str:
    secret_name = str(name or "").strip()
    if not is_safe_secret_name(secret_name):
        raise ProviderConfigError("secret name must use letters, numbers, '_', '-', or '.'.")
    return secret_name


def is_safe_secret_name(name: str) -> bool:
    return bool(name) and all(char.isalnum() or char in {"_", "-", "."} for char in name)


def provider_config_error_type(message: str) -> str:
    if "api_key_ref" in message or "Invalid project secret reference" in message:
        return "invalid_secret_ref"
    if "Missing project secret" in message:
        return "missing_secret"
    if "provider" in message.lower():
        return "invalid_provider"
    return "invalid_config"


def simulated_provider_error(value: str) -> ProviderError:
    allowed = {
        "rate_limit": "Mock provider simulated rate limit.",
        "timeout": "Mock provider simulated timeout.",
        "invalid_request": "Mock provider simulated invalid request.",
        "missing_model": "Mock provider simulated missing model.",
        "missing_secret_ref": "Mock provider simulated missing secret ref.",
    }
    if value not in allowed:
        return ProviderError(f"Unknown mock provider simulated error: {value}", error_type="invalid_request")
    return ProviderError(allowed[value], error_type=value)


def append_provider_call_log(store: ProjectStore, entry: dict[str, Any]) -> None:
    path = store.data_dir / PROVIDER_CALL_LOG_FILENAME
    log = store.read_json(path, default={"schema_version": 1, "calls": []})
    if not isinstance(log, dict):
        log = {"schema_version": 1, "calls": []}
    calls = log.get("calls") if isinstance(log.get("calls"), list) else []
    calls.append(entry)
    store.write_json(path, {"schema_version": 1, "calls": calls})


def read_provider_call_log(store: ProjectStore) -> dict[str, Any]:
    return store.read_json(store.data_dir / PROVIDER_CALL_LOG_FILENAME, default={"schema_version": 1, "calls": []})


def provider_call_log_entry(
    *,
    call_id: str,
    request: ProviderRequest,
    role_config: ModelRoleConfig,
    status: str,
    error_type: str,
    usage: dict[str, int],
) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "timestamp": utc_stamp(),
        "role": request.role,
        "provider": role_config.provider,
        "model": role_config.model,
        "status": status,
        "error_type": error_type,
        "usage": dict(usage),
        "request_summary": {
            "prompt_chars": len(request.prompt),
            "system_prompt_chars": len(request.system_prompt or ""),
            "metadata_keys": sorted(str(key) for key in request.metadata),
        },
    }


def validate_role(role: str) -> None:
    if role not in MODEL_ROLES:
        raise ProviderConfigError(f"Unknown model role: {role!r}")


def is_safe_identifier(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in {"_", "-", "."} for char in value)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:3]}****{value[-4:]}"


def count_placeholder_tokens(value: str) -> int:
    return len(value.split()) if value.strip() else 0
