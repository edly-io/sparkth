from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.plugins.config_base import PluginConfig

# class ChatConfig(PluginConfig, BaseSettings):
#     model_config = SettingsConfigDict(
#         env_prefix="CHAT_",
#         env_file=".env",
#         env_file_encoding="utf-8",
#         extra="ignore",
#     )

#     redis_url: str = Field(
#         default="redis://localhost:6379/0",
#         description="Redis connection URL for caching API keys",
#     )
#     redis_key_ttl: int = Field(
#         default=3600,
#         description="TTL for cached API keys in seconds",
#     )
#     rate_limit_requests_per_minute: int = Field(
#         default=60,
#         description="General rate limit",
#     )
#     rate_limit_chat_per_minute: int = Field(
#         default=10,
#         description="Chat endpoint rate limit",
#     )
#     rate_limit_concurrent_streams: int = Field(
#         default=5,
#         description="Maximum concurrent streams",
#     )
#     encryption_key: str = Field(
#         ...,
#         description="Fernet encryption key for API keys",
#     )
#     max_tokens_per_request: int = Field(
#         default=4096,
#         description="Maximum tokens per request",
#     )
#     default_temperature: float = Field(
#         default=0.7,
#         description="Default temperature",
#     )
#     max_conversation_history: int = Field(
#         default=50,
#         description="Maximum conversation history",
#     )


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
    # provider_api_key: str = Field(..., description="Provider API Key")
    provider_api_key_ref: str = Field(..., description="Reference to stored API key")

    # max_tokens_per_request: int = Field(4096, ge=256, le=32768)
    # default_temperature: float = Field(0.7, ge=0.0, le=2.0)
    # max_conversation_history: int = Field(50, ge=1, le=200)


class APIKeySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    staging_anthropic_api_key: str | None = None

    def get_default_key(self) -> str | None:
        return getattr(self, "staging_anthropic_api_key", None)

api_key_settings = APIKeySettings()