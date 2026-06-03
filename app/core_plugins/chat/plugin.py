from app.core_plugins.chat.config import ChatUserConfig
from app.core_plugins.chat.models import (  # noqa: F401 — registers tables in SQLModel metadata for Alembic
    Conversation,
    Message,
)
from app.core_plugins.chat.routes import chat_router
from app.lib.config.hooks import CONFIG_SCHEMAS
from app.lib.log import get_logger
from app.lib.routes.hooks import ROUTES
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        ROUTES.add_item(self, (chat_router, "/api/v1", ["chat"]))
        CONFIG_SCHEMAS.add_item(self, ChatUserConfig)
