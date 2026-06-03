"""Slack TA Bot plugin for Sparkth."""

from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.models import BotResponseLog, SlackWorkspace
from app.core_plugins.slack.routes import router
from app.lib.routes.hooks import ROUTES
from app.plugins.base import SparkthPlugin


class Slack(SparkthPlugin):
    """Slack TA Bot — OAuth-connected RAG assistant for Slack workspaces."""

    def __init__(self, name: str = "slack") -> None:
        super().__init__(
            name=name,
            config_schema=SlackConfig,
            is_core=True,
            version="1.0.0",
            description="Slack TA Bot — RAG-powered course assistant for Slack workspaces",
            author="Sparkth Team",
        )

        self.add_model(SlackWorkspace)
        self.add_model(BotResponseLog)
        ROUTES.add_item(self, ("/api/v1/slack", ["Slack TA Bot"], router))
