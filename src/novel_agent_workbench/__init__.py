"""Core package for the new novel agent workbench."""

from .drafts import DraftGenerationError, DraftGenerationRequest, DraftGenerationResult, DraftGenerationService
from .providers import (
    ModelRoleConfig,
    MockProviderClient,
    ProviderConfigError,
    ProviderClient,
    ProviderConnectionResult,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    create_provider_client,
    fake_test_model_role,
    generate_with_provider,
    get_model_role_config,
    read_provider_call_log,
    set_model_role_config,
)
from .storage import InvalidProjectIdError, ProjectLockError, ProjectRegistry, ProjectStore, StorageError

__all__ = [
    "InvalidProjectIdError",
    "ModelRoleConfig",
    "MockProviderClient",
    "ProviderConfigError",
    "ProviderClient",
    "ProviderConnectionResult",
    "ProviderError",
    "ProviderRequest",
    "ProviderResponse",
    "ProjectLockError",
    "ProjectRegistry",
    "ProjectStore",
    "StorageError",
    "create_provider_client",
    "DraftGenerationError",
    "DraftGenerationRequest",
    "DraftGenerationResult",
    "DraftGenerationService",
    "fake_test_model_role",
    "generate_with_provider",
    "get_model_role_config",
    "read_provider_call_log",
    "set_model_role_config",
]
