"""Google Drive route package — assembles sub-routers into one router."""

from fastapi import APIRouter

from .files import router as _files_router
from .folders import router as _folder_router
from .oauth import router as _oauth_router

router = APIRouter()
router.include_router(_oauth_router)
router.include_router(_folder_router)
router.include_router(_files_router)

__all__ = ["router"]
