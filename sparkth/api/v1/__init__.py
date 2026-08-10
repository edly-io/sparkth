"""Version 1 of the REST API.

Assembles ``api_router`` from every endpoint module in this package. Each module
exposes a ``router`` — whether it is a single file (``auth.py``) or a package with
its own ``routes.py`` and ``schemas.py`` (``user/``) — and is mounted here under
its URL prefix and OpenAPI tag. ``sparkth.main.assemble_app`` mounts the result at
``/api/v1``, so every path in this file is relative to that.

Prefixes are the public URL contract: changing one here moves an endpoint for every
client, independently of how the module behind it is laid out on disk.
"""

from fastapi import APIRouter

from sparkth.api.v1 import analytics, auth, file_parser, language, llm, permissions, user, user_plugins, whitelist

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(language.router, prefix="/languages", tags=["Languages"])
api_router.include_router(user_plugins.router, prefix="/user-plugins", tags=["User Plugins"])
api_router.include_router(file_parser.router, prefix="/parser", tags=["File Parser"])
api_router.include_router(whitelist.router, prefix="/whitelist", tags=["Whitelist"])
api_router.include_router(llm.router, prefix="/llm", tags=["LLM Configuration"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

__all__ = ["api_router"]
