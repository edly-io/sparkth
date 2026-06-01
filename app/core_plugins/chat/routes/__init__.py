from fastapi import APIRouter

from app.core_plugins.chat.routes.attachments import router as _attachments_router
from app.core_plugins.chat.routes.completions import (
    router as _completions_router,
)
from app.core_plugins.chat.routes.completions import (
    stream_chat_response,
)
from app.core_plugins.chat.routes.conversations import (
    router as _conversations_router,
)
from app.core_plugins.chat.routes.dependencies import (
    get_chat_service,
    get_chat_system_config,
    get_rag_context_service,
)
from app.core_plugins.chat.routes.tool_endpoints import router as _tool_endpoints_router

__all__ = [
    "chat_router",
    "stream_chat_response",
    "get_chat_service",
    "get_chat_system_config",
    "get_rag_context_service",
]

chat_router = APIRouter(prefix="/chat", tags=["Chat"])
chat_router.include_router(_completions_router)
chat_router.include_router(_conversations_router)
chat_router.include_router(_attachments_router)
chat_router.include_router(_tool_endpoints_router)
