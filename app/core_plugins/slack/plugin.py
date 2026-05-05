"""Slack TA Bot plugin for Sparkth."""

from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.models import BotResponseLog, SlackWorkspace
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

    def initialize(self) -> None:
        from app.core_plugins.slack.routes import router

        super().initialize()
        self.add_model(SlackWorkspace)
        self.add_model(BotResponseLog)
        self.add_route(router)

    def get_route_prefix(self) -> str:
        return "/api/v1/slack"

    def get_route_tags(self) -> list[str]:
        return ["Slack TA Bot"]
