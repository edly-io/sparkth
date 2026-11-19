from fastapi import APIRouter, Depends

from sparkth.plugins.compose.routes.analytics import router as _analytics_router
from sparkth.plugins.compose.routes.attachments import router as _attachments_router
from sparkth.plugins.compose.routes.completions import (
    router as _completions_router,
)
from sparkth.plugins.compose.routes.conversations import (
    router as _conversations_router,
)
from sparkth.plugins.compose.routes.dependencies import require_compose_use

compose_router = APIRouter()
compose_router.include_router(_completions_router, dependencies=[Depends(require_compose_use)])
compose_router.include_router(_conversations_router, dependencies=[Depends(require_compose_use)])
compose_router.include_router(_attachments_router, dependencies=[Depends(require_compose_use)])
# The analytics read is gated by analytics.read at the plugin scope, so it does not need plugin.use.
compose_router.include_router(_analytics_router)
