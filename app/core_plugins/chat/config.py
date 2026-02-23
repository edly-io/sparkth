from pydantic import Field
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


class ChatUserConfig(PluginConfig):
    provider: str = Field(..., description="LLM provider")
    provider_api_key_ref: str = Field(..., description="Reference to stored API key")


class APIKeySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str | None = None

    def get_default_key(self) -> str | None:
        return getattr(self, "anthropic_api_key", None)


api_key_settings = APIKeySettings()
