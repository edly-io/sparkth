"""Permissions API router: assignable-permission listing, the self permission-check, and the
mounted role sub-router.

The router is mounted at ``/permissions``. The permission vocabulary is read here (``GET
/permissions``); ``GET /permissions/can`` answers whether the current user holds a permission;
role management lives under ``/permissions/roles`` via the role sub-router.
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.permissions.routes import roles
from sparkth.api.v1.permissions.schemas import PermissionCheckResponse
from sparkth.core.models.user import User
from sparkth.core.permissions.roles import available_permissions
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import PERMISSION_READ, can, get_permission, get_permission_scope

router = APIRouter()


@router.get(
    "",
    response_model=list[str],
    dependencies=[Depends(PERMISSION_READ.require_in_global_scope())],
)
async def list_permissions() -> list[str]:
    """List the permissions assignable to a role. Returns a list of permission strings."""
    return available_permissions()


@router.get("/can", response_model=PermissionCheckResponse)
async def check_permission(
    permission: str = Query(..., description="Permission name to check, e.g. 'analytics.read'."),
    scope: str = Query("global", description="Scope kind to check at (defaults to 'global')."),
    scope_object_id: str | None = Query(None, description="Object id for an object-bearing scope."),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PermissionCheckResponse:
    """Return whether the current user holds ``permission`` at the given scope.

    A self-check any authenticated user may call about their own grants. It is not a security
    boundary (endpoints enforce their own permissions and return 403); it lets a client gate UI
    precisely. The permission and scope names are resolved against the registered vocabulary
    (unknown → 422) and the decision is delegated to the engine's ``can()``.
    """
    permission_obj = get_permission(permission)
    scope_obj = get_permission_scope(scope)
    allowed = await can(current_user, permission_obj, scope_obj, scope_object_id, session)
    return PermissionCheckResponse(allowed=allowed)


router.include_router(roles.router, prefix="/roles")
