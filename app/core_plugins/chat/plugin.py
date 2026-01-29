from starlette.middleware import Middleware

from app.core.logger import get_logger
from app.core_plugins.chat.config import ChatConfig
from app.core_plugins.chat.models import Conversation, Message, ProviderAPIKey
from app.core_plugins.chat.routes import router
from app.plugins.base import SparkthPlugin

logger = get_logger(__name__)


class ChatPlugin(SparkthPlugin):
    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            plugin_name,
            config_schema=ChatConfig,
            is_core=True,
            version="1.0.0",
            description="Multi-provider chat support with LangChain",
            author="Sparkth Team",
        )

        self.add_model(ProviderAPIKey)
        self.add_model(Conversation)
        self.add_model(Message)

        self.add_route(router)

        logger.info("Chat plugin initialized")

    def initialize(self) -> None:
        super().initialize()

        if not self.config_schema:
            raise ValueError("ChatConfig is required")

        logger.info("Chat plugin configuration validated")

    def enable(self) -> None:
        super().enable()
        
        logger.info("Chat plugin enabled with providers: OpenAI, Anthropic, Google")

    def get_route_prefix(self) -> str:
        return "/api/v1"

    def get_middleware(self) -> list[Middleware]:
        return []
