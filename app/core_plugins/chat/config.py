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
    llm_config_id: int = Field(..., description="Reference to an LLMConfig row")
    llm_model_override: str | None = Field(
        default=None,
        description="Overrides the default model in the selected LLMConfig",
    )
