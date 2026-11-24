"""Permissions the PXC plugin declares, and the check of them against one user's activity."""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.lib.permissions import Permission, can
from sparkth.lib.permissions.scopes import USER, build_scope_path
from sparkth.plugins.pxc.exceptions import PxcActivityNotPermitted

logger = get_logger(__name__)

# Actions on one user's activities, checked at that owner's user scope.
PXC_ACTIVITY_READ = Permission.create("pxc.activity.read")
PXC_ACTIVITY_UPDATE = Permission.create("pxc.activity.update")
PXC_ACTIVITY_DELETE = Permission.create("pxc.activity.delete")
PXC_ACTIVITY_PLACE = Permission.create("pxc.activity.place")


async def has_activity_permission(
    session: AsyncSession, permission: Permission, owner_user_id: int, user_id: int
) -> bool:
    """Whether this user holds the permission at the activity owner's user scope.

    A grant at the owner's scope or at global counts. A user id that names no account holds nothing.
    Records nothing.
    """
    user = await session.get(User, user_id)
    if user is None:
        logger.warning("PXC permission %s checked for unknown user %s", permission.name, user_id)
        return False
    return await can(user, permission, USER, build_scope_path(USER, str(owner_user_id)), session)


async def require_activity_permission(
    session: AsyncSession, permission: Permission, owner_user_id: int, user_id: int
) -> None:
    """Require the user to hold the permission at the activity owner's user scope, and record a refusal.

    A grant at the owner's scope or at global counts.

    Raises:
        PxcActivityNotPermitted: if the user does not hold the permission.
    """
    if await has_activity_permission(session, permission, owner_user_id, user_id):
        return
    logger.warning(
        "PXC permission %s denied for user %s on activities of user %s", permission.name, user_id, owner_user_id
    )
    await permission.record_denial(USER, build_scope_path(USER, str(owner_user_id)))
    raise PxcActivityNotPermitted(f"You are not allowed to do this; it needs the {permission.name} permission.")
