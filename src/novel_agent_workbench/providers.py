from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import default_model_role
from .storage import ProjectStore


MODEL_ROLES = {"writer", "scorer", "reviser"}
SECRET_REF_PREFIX = "project_secret."


class ProviderConfigError(ValueError):
    """Raised when a model role provider configuration is invalid."""


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def fake_test_model_role(store: ProjectStore, role: str) -> ProviderConnectionResult:
    role_config = get_model_role_config(store, role)
    try:
        validate_model_role_config(role_config, store.read_secrets())
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
        )
    secret_name = role_config.secret_name()
    secret_value = str(store.read_secrets().get(secret_name) or "") if secret_name else ""
    return ProviderConnectionResult(
        ok=True,
        role=role,
        provider=role_config.provider,
        model=role_config.model,
        mode="fake",
        message="Fake connection test passed; no network request was made.",
        has_api_key=bool(secret_value),
        masked_key=mask_secret(secret_value),
    )


def validate_model_role_config(config: ModelRoleConfig, secrets: dict[str, Any]) -> None:
    validate_role(config.role)
    if config.provider and not is_safe_identifier(config.provider):
        raise ProviderConfigError(f"Invalid provider id: {config.provider!r}")
    if config.api_key_ref:
        secret_name = config.secret_name()
        if secret_name not in secrets or not str(secrets.get(secret_name) or ""):
            raise ProviderConfigError(f"Missing project secret: {secret_name}")


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
