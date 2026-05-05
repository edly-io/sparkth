"""Configuration for the Slack TA Bot plugin."""

from pydantic import Field

from app.plugins.config_base import PluginConfig

MAX_TIMESTAMP_DELTA = 60 * 5  # 5 minutes


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
