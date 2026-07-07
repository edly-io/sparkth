from fastapi import APIRouter

from sparkth.api.v1 import analytics, auth, file_parser, llm, permissions, user, user_plugins, whitelist

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(user_plugins.router, prefix="/user-plugins", tags=["User Plugins"])
api_router.include_router(file_parser.router, prefix="/parser", tags=["File Parser"])
api_router.include_router(whitelist.router, prefix="/whitelist", tags=["Whitelist"])
api_router.include_router(llm.router, prefix="/llm", tags=["LLM Configuration"])
api_router.include_router(analytics.router, prefix="/events", tags=["Analytics"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
