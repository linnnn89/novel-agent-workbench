"""Core package for the new novel agent workbench."""

from .application_service import WorkbenchApplicationService
from .drafts import (
    DraftCommitResult,
    DraftGenerationError,
    DraftGenerationRequest,
    DraftGenerationResult,
    DraftGenerationService,
)
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
from .project_state import public_project_state
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
    "WorkbenchApplicationService",
    "create_provider_client",
    "DraftCommitResult",
    "DraftGenerationError",
    "DraftGenerationRequest",
    "DraftGenerationResult",
    "DraftGenerationService",
    "fake_test_model_role",
    "generate_with_provider",
    "get_model_role_config",
    "read_provider_call_log",
    "public_project_state",
    "set_model_role_config",
]
