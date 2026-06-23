"""Public API for the LLM library.

All plugins and external modules import LLM functionality from here. Nothing
outside ``app/llm/`` should import from ``app.llm.*`` directly.
"""

from app.core.cache import get_cache_service
from app.core.config import get_settings
from app.core.encryption import get_encryption_service
from app.llm.adapter import LLMConfigAdapter
from app.llm.exceptions import (
    LLMConfigDuplicateNameError,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigValidationError,
)
from app.llm.providers import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    BaseChatProvider,
    get_provider,
    get_provider_catalog,
)
from app.llm.schemas import (
    LLMConfigCreate,
    LLMConfigListResponse,
    LLMConfigResponse,
    LLMConfigRotateKey,
    LLMConfigSetActive,
    LLMConfigUpdate,
    ProviderCatalogResponse,
    ProviderInfo,
)
from app.llm.service import LLMConfigService

__all__ = [
    "BaseChatProvider",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "LLMConfigAdapter",
    "LLMConfigCreate",
    "LLMConfigDuplicateNameError",
    "LLMConfigInactiveError",
    "LLMConfigListResponse",
    "LLMConfigModelNotSetError",
    "LLMConfigNotFoundError",
    "LLMConfigResponse",
    "LLMConfigRotateKey",
    "LLMConfigService",
    "LLMConfigSetActive",
    "LLMConfigUpdate",
    "LLMConfigValidationError",
    "ProviderCatalogResponse",
    "ProviderInfo",
    "get_llm_service",
    "get_provider",
    "get_provider_catalog",
]


def get_llm_service() -> LLMConfigService:
    settings = get_settings()
    return LLMConfigService(
        get_encryption_service(settings.LLM_ENCRYPTION_KEY),
        get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL),
    )
