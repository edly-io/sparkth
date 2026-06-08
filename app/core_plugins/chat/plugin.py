from app.core_plugins.chat.config import ChatUserConfig
from app.core_plugins.chat.models import (  # noqa: F401 — registers tables in SQLModel metadata for Alembic
    Conversation,
    Message,
)
from app.core_plugins.chat.routes import chat_router
from app.lib.log import get_logger
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name, config_schema=ChatUserConfig)

        self.add_route(chat_router)

        logger.info("Chat plugin initialized")

        if not self.config_schema:
            raise ValueError("ChatUserConfig is required")

        logger.info("Chat plugin configuration validated")

    def get_route_prefix(self) -> str:
        return "/api/v1"
