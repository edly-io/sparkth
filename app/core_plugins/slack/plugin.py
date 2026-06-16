"""Slack TA Bot plugin for Sparkth."""

import app.core_plugins.slack.models  # noqa: F401 — registers tables in SQLModel metadata for Alembic
from app.core_plugins.slack.adapter import SlackConfigAdapter
from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.routes import router
from app.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from app.lib.plugins import SparkthPlugin
from app.lib.routes import register_router


class Slack(SparkthPlugin):
    """Slack TA Bot — OAuth-connected RAG assistant for Slack workspaces."""

    def __init__(self, name: str = "slack") -> None:
        super().__init__(name)
        CONFIG_SCHEMAS.add_item(self, SlackConfig)
        CONFIG_ADAPTERS.add_item(self, SlackConfigAdapter())
        register_router(self, router)
