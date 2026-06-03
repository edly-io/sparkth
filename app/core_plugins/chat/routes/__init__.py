from fastapi import APIRouter

from app.core_plugins.chat.routes.attachments import router as _attachments_router
from app.core_plugins.chat.routes.completions import (
    router as _completions_router,
)
from app.core_plugins.chat.routes.conversations import (
    router as _conversations_router,
)

chat_router = APIRouter(prefix="/chat", tags=["Chat"])
chat_router.include_router(_completions_router)
chat_router.include_router(_conversations_router)
chat_router.include_router(_attachments_router)
