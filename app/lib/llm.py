"""Public API for the LLM library.

All plugins and external modules import LLM functionality from here. Nothing
outside ``app/llm/`` should import from ``app.llm.*`` directly.
"""

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
from app.llm.service import LLMConfigService, get_llm_service

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
