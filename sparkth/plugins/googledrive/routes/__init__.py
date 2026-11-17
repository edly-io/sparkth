"""Google Drive route package — assembles sub-routers into one router."""

from fastapi import APIRouter, Depends

from .analytics import router as _analytics_router
from .dependencies import require_drive_use
from .files import router as _files_router
from .folders import router as _folder_router
from .oauth import router as _oauth_router

router = APIRouter()
# The OAuth routes gate themselves one by one, because the callback is checked by its signed state instead.
router.include_router(_oauth_router)
router.include_router(_folder_router, dependencies=[Depends(require_drive_use)])
router.include_router(_files_router, dependencies=[Depends(require_drive_use)])
# The analytics read is gated by analytics.read at the plugin scope, so it does not need plugin.use.
router.include_router(_analytics_router)

__all__ = ["router"]
