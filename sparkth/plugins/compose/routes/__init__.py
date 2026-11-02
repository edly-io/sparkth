from fastapi import APIRouter

from sparkth.plugins.compose.routes.analytics import router as _analytics_router
from sparkth.plugins.compose.routes.attachments import router as _attachments_router
from sparkth.plugins.compose.routes.completions import (
    router as _completions_router,
)
from sparkth.plugins.compose.routes.conversations import (
    router as _conversations_router,
)

compose_router = APIRouter()
compose_router.include_router(_completions_router)
compose_router.include_router(_conversations_router)
compose_router.include_router(_attachments_router)
compose_router.include_router(_analytics_router)
