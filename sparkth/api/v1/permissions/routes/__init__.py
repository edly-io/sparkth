"""Permissions API router: the assignable-permission listing plus the mounted sub-routers.

The router is mounted at ``/permissions``. The permission vocabulary is read here (``GET
/permissions``); role management lives under ``/permissions/roles`` via the role sub-router,
group management under ``/permissions/groups`` via the group sub-router.
"""

from fastapi import APIRouter, Depends

from sparkth.api.v1.permissions.routes import groups, roles
from sparkth.core.permissions.roles import available_permissions
from sparkth.lib.permissions import PERMISSION_READ

router = APIRouter()


@router.get(
    "",
    response_model=list[str],
    dependencies=[Depends(PERMISSION_READ.require_in_global_scope())],
)
async def list_permissions() -> list[str]:
    """List the permissions assignable to a role. Returns a list of permission strings."""
    return available_permissions()


router.include_router(roles.router, prefix="/roles")
router.include_router(groups.router, prefix="/groups")
