from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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


class ChatUserConfig(PluginConfig):
    provider: str = Field(..., description="LLM provider (openai | anthropic | google)")
    provider_api_key_ref: int = Field(..., description="Reference to stored API key")
    model: str = Field(
        default="claude-sonnet-4-20250514",
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
