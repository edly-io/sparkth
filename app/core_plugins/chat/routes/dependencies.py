from functools import lru_cache

from app.core_plugins.chat.config import ChatSystemConfig
from app.core_plugins.chat.service import ChatService
from app.rag.context_service import RAGContextService
from app.rag.provider import get_provider as get_rag_provider


@lru_cache
def get_chat_system_config() -> ChatSystemConfig:
    """Dependency to get chat system configuration from environment variables."""
    return ChatSystemConfig()


def get_chat_service() -> ChatService:
    """Dependency to get chat service."""
    return ChatService()


def get_rag_context_service() -> RAGContextService:
    """FastAPI dependency: returns a stateless RAGContextService."""
    return RAGContextService(embedding_provider=get_rag_provider())
