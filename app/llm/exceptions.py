class LLMConfigNotFoundError(ValueError):
    """Raised when an LLM config is not found."""

    def __init__(self, config_id: int, user_id: int) -> None:
        super().__init__(f"LLMConfig {config_id} not found for user {user_id}")


class LLMConfigModelNotSetError(ValueError):
    """Raised when the model field is empty on an LLM config."""


class LLMConfigValidationError(ValueError):
    """Raised when a field value is invalid (e.g. model not allowed for provider)."""


class LLMConfigInactiveError(ValueError):
    """Raised when an LLM config exists but is inactive."""

    def __init__(self, config_id: int, user_id: int) -> None:
        super().__init__(
            "The selected AI configuration is deactivated. "
            "Go to AI Keys to reactivate it, or choose a different configuration in the chat settings."
        )


class LLMConfigDuplicateNameError(ValueError):
    """Raised when an LLM config with the same name already exists for the user."""

    def __init__(self, name: str) -> None:
        super().__init__(f"An LLM config with name '{name}' already exists for this user.")
