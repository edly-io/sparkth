from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from sparkth.lib.plugins import ConfigWidget, PluginConfig, widget
from sparkth.lib.settings import ENV_FILES


class ComposeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COMPOSE_",
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_tool_executions: int = 50
    title_max_length: int = 60
    title_prompt_max_chars: int = 500
    title_llm_max_tokens: int = 20
    title_db_max_length: int = 255
    title_llm_temperature: float = 0.3


class ComposeUserConfig(PluginConfig):
    llm_config_id: int = Field(
        ...,
        description="Reference to an LLMConfig row",
        json_schema_extra=widget(ConfigWidget.LLM_CONFIG),
    )
    llm_model_override: str | None = Field(
        default=None,
        description="Overrides the default model in the selected LLMConfig",
        json_schema_extra=widget(ConfigWidget.LLM_MODEL),
    )


@lru_cache
def get_compose_settings() -> ComposeSettings:
    """Dependency to get compose settings from environment variables."""
    return ComposeSettings()
