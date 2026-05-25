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

    max_tool_executions: int = 50
    title_max_length: int = 60


class ChatUserConfig(PluginConfig):
    llm_config_id: int = Field(..., description="Reference to an LLMConfig row")
    llm_model_override: str | None = Field(
        default=None,
        description="Overrides the default model in the selected LLMConfig",
    )
