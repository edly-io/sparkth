"""Slack TA Bot plugin for Sparkth."""

import sparkth.plugins.slack.models  # noqa: F401 — registers tables in SQLModel metadata for Alembic
from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from sparkth.lib.frontend.hooks import (
    DISPLAY_INFO,
    FRONTEND_APPS,
    SIDEBAR_ENTRIES,
    DisplayInfo,
    FrontendApp,
    SidebarEntry,
)
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.slack.adapter import SlackConfigAdapter
from sparkth.plugins.slack.config import SlackConfig
from sparkth.plugins.slack.routes import router


class Slack(SparkthPlugin):
    """Slack TA Bot — OAuth-connected RAG assistant for Slack workspaces."""

    def __init__(self) -> None:
        super().__init__("slack")
        CONFIG_SCHEMAS.add_item(self, SlackConfig)
        CONFIG_ADAPTERS.add_item(self, SlackConfigAdapter())
        register_router(self, router)
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo("Slack TA Bot", "Answer student questions in Slack from your course materials", icon="slack"),
        )
        SIDEBAR_ENTRIES.add_item(self, SidebarEntry("Slack TA Bot", icon="slack", order=3))
        FRONTEND_APPS.add_item(self, FrontendApp())
