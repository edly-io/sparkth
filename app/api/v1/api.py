from fastapi import APIRouter

from app.api.v1 import auth, file_parser, user, user_plugins

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(user_plugins.router, prefix="/user-plugins", tags=["User Plugins"])
api_router.include_router(file_parser.router, prefix="/parser", tags=["File Parser"])
