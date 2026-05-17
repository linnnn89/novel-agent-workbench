"""Core package for the new novel agent workbench."""

from .providers import (
    ModelRoleConfig,
    ProviderConfigError,
    ProviderConnectionResult,
    fake_test_model_role,
    get_model_role_config,
    set_model_role_config,
)
from .storage import InvalidProjectIdError, ProjectLockError, ProjectRegistry, ProjectStore, StorageError

__all__ = [
    "InvalidProjectIdError",
    "ModelRoleConfig",
    "ProviderConfigError",
    "ProviderConnectionResult",
    "ProjectLockError",
    "ProjectRegistry",
    "ProjectStore",
    "StorageError",
    "fake_test_model_role",
    "get_model_role_config",
    "set_model_role_config",
]
