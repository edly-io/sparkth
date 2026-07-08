"""Slack TA Bot plugin for Sparkth."""

import sparkth.plugins.slack.models  # noqa: F401 — registers tables in SQLModel metadata for Alembic
from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.slack.adapter import SlackConfigAdapter
from sparkth.plugins.slack.config import SlackConfig
from sparkth.plugins.slack.routes import router


class Slack(SparkthPlugin):
    """Slack TA Bot — OAuth-connected RAG assistant for Slack workspaces."""

    def __init__(self, name: str = "slack") -> None:
        super().__init__(name)
        CONFIG_SCHEMAS.add_item(self, SlackConfig)
        CONFIG_ADAPTERS.add_item(self, SlackConfigAdapter())
        register_router(self, router)
