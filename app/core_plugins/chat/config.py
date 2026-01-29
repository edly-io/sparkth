from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.plugins.config_base import PluginConfig


class ChatConfig(PluginConfig, BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching API keys",
    )
    redis_key_ttl: int = Field(
        default=3600,
        description="TTL for cached API keys in seconds",
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="General rate limit",
    )
    rate_limit_chat_per_minute: int = Field(
        default=10,
        description="Chat endpoint rate limit",
    )
    rate_limit_concurrent_streams: int = Field(
        default=5,
        description="Maximum concurrent streams",
    )
    encryption_key: str = Field(
        ...,
        description="Fernet encryption key for API keys",
    )
    max_tokens_per_request: int = Field(
        default=4096,
        description="Maximum tokens per request",
    )
    default_temperature: float = Field(
        default=0.7,
        description="Default temperature",
    )
    max_conversation_history: int = Field(
        default=50,
        description="Maximum conversation history",
    )
