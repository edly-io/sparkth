class LLMConfigNotFoundError(ValueError):
    """Raised when an LLM config is not found."""


class LLMConfigModelNotSetError(ValueError):
    """Raised when the model field is empty on an LLM config."""


class LLMConfigValidationError(ValueError):
    """Raised when a field value is invalid (e.g. model not allowed for provider)."""
