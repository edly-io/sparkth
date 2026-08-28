from fastapi import status

from sparkth.lib.analytics import register_event_schema
from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
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
from sparkth.plugins.chat.analytics import (
    ChatCompletionServed,
    ChatConversationStarted,
    ChatMessageSent,
    ChatToolInvoked,
)
from sparkth.plugins.chat.config import ChatUserConfig
from sparkth.plugins.chat.exceptions import ConversationNotFound, DocumentNotFound
from sparkth.plugins.chat.models import (  # noqa: F401 — registers tables in SQLModel metadata for Alembic
    Conversation,
    Message,
)
from sparkth.plugins.chat.routes import chat_router

logger = get_logger(__name__)

# Registered here rather than in ChatPlugin.__init__: a second registration of the same
# type raises, and the plugin class is instantiated more than once across a test session.
register_exception_handler(ConversationNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(DocumentNotFound, status.HTTP_404_NOT_FOUND)


class ChatPlugin(SparkthPlugin):
    def __init__(self) -> None:
        super().__init__("chat")
        register_router(self, chat_router)
        CONFIG_SCHEMAS.add_item(self, ChatUserConfig)
        CONFIG_ADAPTERS.add_item(self, LLMConfigAdapter())
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(
                gettext_noop("Create Course"),
                gettext_noop("Transform your resources into courses with AI"),
                icon="plus",
            ),
        )
        SIDEBAR_ENTRIES.add_item(self, SidebarEntry(gettext_noop("Create Course"), icon="plus", order=1))
        FRONTEND_APPS.add_item(self, FrontendApp())

        for event_schema in (
            ChatConversationStarted,
            ChatMessageSent,
            ChatCompletionServed,
            ChatToolInvoked,
        ):
            register_event_schema(self, event_schema)
