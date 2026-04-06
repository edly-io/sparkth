from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core_plugins.chat.providers import DEFAULT_MODEL
from app.plugins.config_base import PluginConfig


class ChatSystemConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    encryption_key: str  # REQUIRED, env-only

    redis_url: str = "redis://localhost:6379/0"
    redis_key_ttl: int = 3600

    rate_limit_requests_per_minute: int = 60
    rate_limit_chat_per_minute: int = 10
    rate_limit_concurrent_streams: int = 5

    max_tool_executions: int = 50

    title_max_length: int = 60

    # Platform-owned credentials for background tasks like title generation.
    # When set, these are used instead of the user's provider/key, so title
    # generation does not consume user quota or use an expensive model.
    title_generation_api_key: str = ""
    title_generation_model: str = ""
    title_generation_provider: str = ""


class ChatUserConfig(PluginConfig):
    provider: str = Field(..., description="LLM provider (openai | anthropic | google)")
    provider_api_key_ref: int = Field(..., description="Reference to stored API key")
    model: str = Field(
        default=DEFAULT_MODEL,
        description="Model ID for the selected provider",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        from app.core_plugins.chat.providers import get_supported_providers

        supported = get_supported_providers()
        if v.lower() not in supported:
            raise ValueError(f"Unsupported provider '{v}'. Supported: {', '.join(supported)}")
        return v.lower()

    @model_validator(mode="after")
    def validate_model_for_provider(self) -> "ChatUserConfig":
        from app.core_plugins.chat.providers import get_models_for_provider

        allowed = get_models_for_provider(self.provider)
        if self.model not in allowed:
            raise ValueError(
                f"Model '{self.model}' is not available for provider '{self.provider}'. Allowed: {', '.join(allowed)}"
            )
        return self
