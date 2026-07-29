"""Role-management API package.

This module was generated with LLM (Claude) assistance.

Exports the router and registers the role-management domain-exception → HTTP status mappings.
Core registers at import time; ``sparkth.main.assemble_app`` wires the registry onto the app
at startup (Starlette dispatches by MRO).
"""

from fastapi import status

from sparkth.api.v1.permissions.routes import router
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.permissions.exceptions import (
    PermissionNotFound,
    PermissionScopeNotFound,
    RoleAlreadyExists,
    RoleInUse,
    RoleNotFound,
)

register_exception_handler(RoleNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(RoleAlreadyExists, status.HTTP_409_CONFLICT)
register_exception_handler(RoleInUse, status.HTTP_409_CONFLICT)
register_exception_handler(PermissionNotFound, status.HTTP_422_UNPROCESSABLE_CONTENT)
register_exception_handler(PermissionScopeNotFound, status.HTTP_422_UNPROCESSABLE_CONTENT)

__all__ = ["router"]
