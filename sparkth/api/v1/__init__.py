"""Version 1 of the REST API.

Assembles ``api_router`` from every endpoint module in this package. Each module
exposes a ``router`` — declared in a single file (``auth.py``) or exported by a package's
``__init__.py`` (``user/``) — and is mounted here under its URL prefix and OpenAPI tag.
``sparkth.main.assemble_app`` mounts the result at ``/api/v1``, so every path in this
file is relative to that.

Prefixes are the public URL contract: changing one here moves an endpoint for every
client, independently of how the module behind it is laid out on disk.
"""

from fastapi import APIRouter

from sparkth.api.v1 import (
    analytics,
    audit,
    auth,
    file_upload,
    language,
    llm,
    permissions,
    plugins,
    user,
    users,
    whitelist,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(language.router, prefix="/languages", tags=["Languages"])
api_router.include_router(plugins.router, prefix="/plugins", tags=["Plugins"])
api_router.include_router(file_upload.router, prefix="/parser", tags=["File Parser"])
api_router.include_router(whitelist.router, prefix="/whitelist", tags=["Whitelist"])
api_router.include_router(llm.router, prefix="/llm", tags=["LLM Configuration"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])

__all__ = ["api_router"]
