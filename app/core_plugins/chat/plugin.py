from app.core_plugins.chat.config import ChatUserConfig
from app.core_plugins.chat.models import (  # noqa: F401 — registers tables in SQLModel metadata for Alembic
    Conversation,
    Message,
)
from app.core_plugins.chat.routes import chat_router
from app.lib.config.hooks import CONFIG_SCHEMAS
from app.lib.log import get_logger
from app.lib.routes import register_router
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        register_router(self, chat_router)
        CONFIG_SCHEMAS.add_item(self, ChatUserConfig)
