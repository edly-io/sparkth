from fastapi import APIRouter

from app.api.v1 import auth, user_plugins

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user_plugins.router, prefix="/user-plugins", tags=["User Plugins"])
