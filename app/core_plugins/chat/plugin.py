from app.core_plugins.chat.config import ChatUserConfig
from app.core_plugins.chat.models import Conversation, Message
from app.core_plugins.chat.routes import chat_router
from app.lib.config.hooks import CONFIG_SCHEMAS
from app.lib.log import get_logger
from app.lib.models.hooks import MODELS
from app.lib.routes.hooks import ROUTES
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            plugin_name,
            is_core=True,
            version="1.0.0",
            description="Multi-provider chat support with LangChain",
            author="Sparkth Team",
        )

        CONFIG_SCHEMAS.add_item(self, ChatUserConfig)
        MODELS.add_item(self, Conversation)
        MODELS.add_item(self, Message)

        ROUTES.add_item(self, ("/api/v1", ["chat"], chat_router))

        logger.info("Chat plugin initialized")
