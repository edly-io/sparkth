"""Public API for the LLM library.

All plugins and external modules import LLM functionality from here. Nothing
outside ``app/llm/`` should import from ``app.llm.*`` directly.
"""

from app.llm.adapter import LLMConfigAdapter  # noqa: F401 — re-exported in __all__
from app.llm.exceptions import (  # noqa: F401 — re-exported in __all__
    LLMConfigDuplicateNameError,
    LLMConfigInactiveError,
    LLMConfigModelNotSetError,
    LLMConfigNotFoundError,
    LLMConfigValidationError,
)
from app.llm.providers import BaseChatProvider, get_provider  # noqa: F401 — re-exported in __all__
from app.llm.service import LLMConfigService, get_llm_service  # noqa: F401 — re-exported in __all__

__all__ = [
    "BaseChatProvider",
    "LLMConfigAdapter",
    "LLMConfigDuplicateNameError",
    "LLMConfigInactiveError",
    "LLMConfigModelNotSetError",
    "LLMConfigNotFoundError",
    "LLMConfigService",
    "LLMConfigValidationError",
    "get_llm_service",
    "get_provider",
]
