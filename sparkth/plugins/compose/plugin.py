from fastapi import status

from sparkth.lib.analytics import register_event_schemas, register_summary_figure
from sparkth.lib.compose.hooks import register_chat_capability
from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from sparkth.lib.documents import DOCUMENT_DELETED
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.frontend.hooks import (
    DISPLAY_INFO,
    FRONTEND_APPS,
    SIDEBAR_ENTRIES,
    DisplayInfo,
    FrontendApp,
    SidebarEntry,
)
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.llm import LLMConfigAdapter
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.compose.analytics import events
from sparkth.plugins.compose.analytics.reads import SUMMARY_FIGURES_COMPOSE
from sparkth.plugins.compose.capabilities import COURSE_DESIGN
from sparkth.plugins.compose.config import ComposeUserConfig
from sparkth.plugins.compose.exceptions import ConversationNotFound, DocumentNotFound
from sparkth.plugins.compose.models import (  # noqa: F401 — registers tables in SQLModel metadata for Alembic
    Conversation,
    Message,
)
from sparkth.plugins.compose.routes import compose_router
from sparkth.plugins.compose.service import detach_deleted_document

logger = get_logger(__name__)

# Registered here rather than in ComposePlugin.__init__: a second registration of the same
# type raises, and the plugin class is instantiated more than once across a test session.
register_exception_handler(ConversationNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(DocumentNotFound, status.HTTP_404_NOT_FOUND)


class ComposePlugin(SparkthPlugin):
    def __init__(self) -> None:
        super().__init__("chat")
        register_router(self, compose_router)
        DOCUMENT_DELETED.add_item(self, detach_deleted_document)
        CONFIG_SCHEMAS.add_item(self, ComposeUserConfig)
        CONFIG_ADAPTERS.add_item(self, LLMConfigAdapter())
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(
                gettext_noop("Compose"),
                gettext_noop("Transform your resources into courses with AI"),
                icon="plus",
            ),
        )
        SIDEBAR_ENTRIES.add_item(self, SidebarEntry(gettext_noop("Compose"), icon="plus", order=1))
        FRONTEND_APPS.add_item(self, FrontendApp())
        register_chat_capability(self, COURSE_DESIGN)

        register_event_schemas(self, events)
        for figure in SUMMARY_FIGURES_COMPOSE:
            register_summary_figure(self, figure)
