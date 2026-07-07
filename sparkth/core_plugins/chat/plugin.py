from sparkth.core_plugins.chat.adapter import ChatConfigAdapter
from sparkth.core_plugins.chat.config import ChatUserConfig
from sparkth.core_plugins.chat.models import (  # noqa: F401 — registers tables in SQLModel metadata for Alembic
    Conversation,
    Message,
)
from sparkth.core_plugins.chat.routes import chat_router
from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        register_router(self, chat_router)
        CONFIG_SCHEMAS.add_item(self, ChatUserConfig)
        CONFIG_ADAPTERS.add_item(self, ChatConfigAdapter())
