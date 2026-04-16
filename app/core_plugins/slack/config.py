"""Configuration for the Slack TA Bot plugin."""

from pydantic import Field

from app.plugins.config_base import PluginConfig

MAX_TIMESTAMP_DELTA = 60 * 5  # 5 minutes


class SlackBotConfig(PluginConfig):
    """Per-user Slack TA Bot configuration stored in the user-plugins table."""

    bot_name: str = Field(
        default="TA Bot",
        description="Display name the bot uses when posting to Slack",
    )
    fallback_message: str = Field(
        default="I couldn't find an answer in the course material. Please contact your instructor.",
        description="Message sent when no RAG match is found",
    )
