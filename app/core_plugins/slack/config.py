"""Configuration for the Slack TA Bot plugin."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.plugins.config_base import PluginConfig


class SlackSettings(BaseSettings):
    """System-level Slack tuning read from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SLACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # Slack TA Bot OAuth
    client_id: str = ""
    client_secret: str = ""
    signing_secret: str = ""
    redirect_uri: str = ""

    state_max_age: int = 600
    max_timestamp_delta: int = 300
    max_agent_files: int = 5
    max_question_len: int = 500
    frontend_path: str = "/dashboard/slack"
    bot_scopes: list[str] = Field(
        default=[
            "app_mentions:read",
            "channels:history",
            "chat:write",
            "im:history",
            "im:read",
            "im:write",
        ]
    )

    @field_validator("bot_scopes", mode="before")
    @classmethod
    def parse_scopes(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


class SlackConfig(PluginConfig):
    """Per-user Slack TA Bot configuration stored in the user-plugins table."""

    bot_name: str = Field(
        default="TA Bot",
        description="Display name the bot uses when posting to Slack",
    )
    fallback_message: str = Field(
        default="I couldn't find an answer in the course material. Please contact your instructor.",
        description="Message sent when no RAG match is found",
    )
    greeting_message: str = Field(
        default="Hello! I'm your TA Bot. How can I help you?",
        description="Message sent in response to casual greetings",
    )
    allowed_sources: list[str] = Field(
        default_factory=list,
        description="Document sources this bot can search. Empty list means all sources.",
    )
    llm_config_id: int | None = Field(
        default=None,
        description="ID of an LLMConfig row for answer synthesis. None disables synthesis.",
    )
    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM synthesis. Low values for factual Q&A.",
    )
    llm_model_override: str | None = Field(
        default=None,
        description="Override the model from the selected LLMConfig. None uses the config's model.",
    )


@lru_cache
def get_slack_settings() -> SlackSettings:
    return SlackSettings()
