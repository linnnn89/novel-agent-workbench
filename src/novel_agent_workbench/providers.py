from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .config import default_model_role
from .storage import ProjectStore, utc_stamp


MODEL_ROLES = {"writer", "scorer", "reviser"}
SECRET_REF_PREFIX = "project_secret."
MOCK_PROVIDER_ID = "mock"
CHUTES_PROVIDER_ID = "chutes_openai"
PROVIDER_CALL_LOG_FILENAME = "provider_call_log.json"
DISABLED_ADAPTER_IDS = ("openai_compatible", "deepseek", CHUTES_PROVIDER_ID)


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
        return asdict(self)


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
    max_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_role(self.role)
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ProviderError("Provider prompt cannot be empty.", error_type="invalid_request")
        if self.system_prompt is not None and not isinstance(self.system_prompt, str):
            raise ProviderError("system_prompt must be a string.", error_type="invalid_request")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ProviderError("max_tokens must be positive when provided.", error_type="invalid_request")
        if self.temperature is not None and self.temperature < 0:
            raise ProviderError("temperature must be non-negative when provided.", error_type="invalid_request")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        return ProviderResponse(
            text=f"{role_text} prompt_chars={len(request.prompt)}",
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
        enabled=False,
        network_allowed=False,
        requires_secret=True,
        description="Reserved OpenAI-compatible HTTP adapter. Disabled until MVP-2 real-provider gate is approved.",
    ),
    "deepseek": ProviderAdapterInfo(
        adapter_id="deepseek",
        enabled=False,
        network_allowed=False,
        requires_secret=True,
        description="Reserved DeepSeek adapter. Disabled until MVP-2 real-provider gate is approved.",
    ),
    CHUTES_PROVIDER_ID: ProviderAdapterInfo(
        adapter_id=CHUTES_PROVIDER_ID,
        enabled=False,
        network_allowed=False,
        requires_secret=True,
        description="Reserved Chutes OpenAI-compatible adapter. Disabled until explicit network approval.",
    ),
}


def get_model_role_config(store: ProjectStore, role: str) -> ModelRoleConfig:
    validate_role(role)
    config = store.read_config()
    roles = config.get("model_roles") if isinstance(config.get("model_roles"), dict) else {}
    return ModelRoleConfig.from_mapping(role, roles.get(role))


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


def create_provider_client(store: ProjectStore, role: str) -> ProviderClient:
    role_config = get_model_role_config(store, role)
    if not role_config.provider:
        raise ProviderError("Model role has no provider configured.", error_type="missing_provider")
    adapter = get_provider_adapter(role_config.provider)
    if adapter is None:
        raise ProviderError(
            f"Provider {role_config.provider!r} is not registered.",
            error_type="unsupported_provider",
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


def generate_with_provider(store: ProjectStore, request: ProviderRequest) -> ProviderResponse:
    call_id = str(uuid4())
    client: ProviderClient | None = None
    try:
        client = create_provider_client(store, request.role)
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
        role_config = client.role_config if client else get_model_role_config(store, request.role)
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
    return DisabledProviderDryRunAdapter(role_config=role_config, adapter_info=adapter).dry_run(request)


def provider_real_test(store: ProjectStore, request: ProviderRequest, *, timeout_seconds: float = 30.0) -> ProviderRealTestResult:
    role_config = get_model_role_config(store, request.role)
    if role_config.provider != CHUTES_PROVIDER_ID:
        raise ProviderError("Only chutes_openai supports explicit real test in this phase.", error_type="unsupported_provider")
    if not role_config.model:
        raise ProviderError("Provider real test requires a model id.", error_type="missing_model")
    if not role_config.base_url:
        raise ProviderError("Provider real test requires base_url.", error_type="missing_base_url")
    secret_value = resolve_project_secret(store, role_config.api_key_ref)
    endpoint = chat_completions_url(role_config.base_url)
    payload = {
        "model": role_config.model,
        "messages": openai_compatible_messages(request),
        "stream": False,
        "max_tokens": request.max_tokens or 16,
        "temperature": 0 if request.temperature is None else request.temperature,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {secret_value}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=timeout_seconds) as response:
            status_code = int(getattr(response, "status", 200))
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        return provider_real_test_error_result(
            request=request,
            role_config=role_config,
            status_code=int(exc.code),
            error_type="http_error",
            message=f"HTTP error {int(exc.code)} from provider.",
        )
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        return provider_real_test_error_result(
            request=request,
            role_config=role_config,
            status_code=None,
            error_type="network_error",
            message="Network error during provider real test.",
        )
    try:
        data = json.loads(response_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return provider_real_test_error_result(
            request=request,
            role_config=role_config,
            status_code=status_code,
            error_type="invalid_response",
            message="Provider response was not valid JSON.",
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
        "message_count": 2 if request.system_prompt else 1,
        "prompt_chars": len(request.prompt),
        "system_prompt_chars": len(request.system_prompt or ""),
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "metadata_keys": sorted(str(key) for key in request.metadata),
    }


def safe_url_host(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc.split("@")[-1]


def chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def openai_compatible_messages(request: ProviderRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages


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
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
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
