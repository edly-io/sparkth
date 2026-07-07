"""Public API for the LLM library.

All plugins and external modules import LLM functionality from here. Nothing
outside ``sparkth/llm/`` should import from ``sparkth.llm.*`` directly.
"""

from sparkth.core.cache import get_cache_service
from sparkth.core.config import get_settings
from sparkth.core.encryption import get_encryption_service
from sparkth.llm.adapter import LLMConfigAdapter
from sparkth.llm.exceptions import (
    LLMConfigDuplicateNameError,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigValidationError,
)
from sparkth.llm.providers import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    BaseChatProvider,
    get_provider,
    get_provider_catalog,
)
from sparkth.llm.schemas import (
    LLMConfigCreate,
    LLMConfigListResponse,
    LLMConfigResponse,
    LLMConfigRotateKey,
    LLMConfigSetActive,
    LLMConfigUpdate,
    ProviderCatalogResponse,
    ProviderInfo,
)
from sparkth.llm.service import LLMConfigService

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
