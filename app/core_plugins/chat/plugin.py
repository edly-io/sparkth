from app.core_plugins.chat.config import ChatUserConfig
from app.core_plugins.chat.models import Conversation, Message
from app.core_plugins.chat.routes import chat_router
from app.lib.log import get_logger
from app.lib.routes.hooks import ROUTES
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            plugin_name,
            config_schema=ChatUserConfig,
            is_core=True,
            version="1.0.0",
            description="Multi-provider chat support with LangChain",
            author="Sparkth Team",
        )

        self.add_model(Conversation)
        self.add_model(Message)

        ROUTES.add_item(self, ("/api/v1", ["chat"], chat_router))

        logger.info("Chat plugin initialized")

        if not self.config_schema:
            raise ValueError("ChatUserConfig is required")

        logger.info("Chat plugin configuration validated")
