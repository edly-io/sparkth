"""Permissions the PXC plugin declares, their check against one user's activity, and loading the activity
a caller may act on."""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import current_user_id
from sparkth.lib.db import session_scope
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.lib.permissions import Permission, PermissionCheckQuery, PermissionRisk, batched_can, can
from sparkth.lib.permissions.scopes import GLOBAL, USER, PermissionScope, build_scope_path
from sparkth.plugins.pxc.activities import parse_activity_id
from sparkth.plugins.pxc.constants import PXC_NOT_PERMITTED_MESSAGE
from sparkth.plugins.pxc.exceptions import PxcActivityNotPermitted
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.store import get_activity

logger = get_logger(__name__)

# The category this plugin's permissions are listed under.
_CATEGORY = gettext_noop("PXC Activities")

# Actions on one user's activities, checked at that owner's user scope.
PXC_ACTIVITY_READ = Permission.create(
    "pxc.activity.read",
    gettext_noop("See activities"),
    gettext_noop("List activities, preview them as a learner and read their files."),
    _CATEGORY,
)
PXC_ACTIVITY_UPDATE = Permission.create(
    "pxc.activity.update",
    gettext_noop("Edit activities"),
    gettext_noop("Preview activities as their author and change them from chat."),
    _CATEGORY,
)
PXC_ACTIVITY_DELETE = Permission.create(
    "pxc.activity.delete",
    gettext_noop("Delete activities"),
    gettext_noop("Delete activities, with their learners' data, from every course that uses them."),
    _CATEGORY,
    risks=(PermissionRisk.DELETES,),
)
PXC_ACTIVITY_PLACE = Permission.create(
    "pxc.activity.place",
    gettext_noop("Place activities"),
    gettext_noop("Put activities into LMS courses."),
    _CATEGORY,
)

# The levels a launch runs at, apart from the permissions that manage the record.
PXC_ACTIVITY_PLAY = Permission.create(
    "pxc.activity.play",
    gettext_noop("Play activities"),
    gettext_noop("Open activities as a learner."),
    _CATEGORY,
)
PXC_ACTIVITY_EDIT = Permission.create(
    "pxc.activity.edit",
    gettext_noop("Edit activities as an author"),
    gettext_noop("Open activities as their author, which also opens them as a learner."),
    _CATEGORY,
)


async def has_activity_permission(
    session: AsyncSession, permission: Permission, owner_user_id: int, caller_user_id: int
) -> bool:
    """Whether this user holds the permission at the activity owner's user scope.

    A grant at the owner's scope or at global counts. A user id that names no account holds nothing.
    Records nothing.
    """
    user = await session.get(User, caller_user_id)
    if user is None:
        logger.warning("PXC permission %s checked for unknown user %s", permission.name, caller_user_id)
        return False
    return await can(user, permission, USER, build_scope_path(USER, str(owner_user_id)), session)


async def require_activity_permission(
    session: AsyncSession, permission: Permission, owner_user_id: int, caller_user_id: int
) -> None:
    """Require the user to hold the permission at the activity owner's user scope, and record a refusal.

    A grant at the owner's scope or at global counts.

    Raises:
        PxcActivityNotPermitted: if the user does not hold the permission.
    """
    if await has_activity_permission(session, permission, owner_user_id, caller_user_id):
        return
    logger.warning(
        "PXC permission %s denied for user %s on activities of user %s", permission.name, caller_user_id, owner_user_id
    )
    await permission.record_denial(USER, build_scope_path(USER, str(owner_user_id)))
    raise PxcActivityNotPermitted(PXC_NOT_PERMITTED_MESSAGE.format(permission.name))


def get_launch_permissions(level: str) -> tuple[Permission, ...]:
    """Return the permissions that allow a launch at this level, any one of which is enough.

    ``edit`` needs the edit permission. ``play`` and ``view`` need the play permission or the edit permission.

    Raises:
        ValueError: if the level is none of ``edit``, ``play`` and ``view``.
    """
    if level == "edit":
        return (PXC_ACTIVITY_EDIT,)
    if level in ("play", "view"):
        return (PXC_ACTIVITY_PLAY, PXC_ACTIVITY_EDIT)
    raise ValueError(f"Unknown launch level {level!r}.")


def _get_launch_scope(owner_user_id: int | None) -> tuple[PermissionScope, str | None]:
    """Return the scope and path a launch is checked at: the owner's user scope, or global for no owner."""
    if owner_user_id is None:
        return GLOBAL, None
    return USER, build_scope_path(USER, str(owner_user_id))


async def has_launch_permission(
    session: AsyncSession, level: str, owner_user_id: int | None, caller_user_id: int
) -> bool:
    """Whether this user holds a permission that allows a launch at this level.

    The permissions are checked at the activity owner's user scope, or at global for an activity with no
    owner; a grant at global counts either way. A user id that names no account holds nothing.
    Records nothing.
    """
    user = await session.get(User, caller_user_id)
    if user is None:
        logger.warning("PXC launch at level %s checked for unknown user %s", level, caller_user_id)
        return False
    scope, scope_path = _get_launch_scope(owner_user_id)
    queries = [PermissionCheckQuery(permission, scope, scope_path) for permission in get_launch_permissions(level)]
    return any(await batched_can(user, queries, session))


async def record_launch_denial(level: str, owner_user_id: int | None) -> None:
    """Record a refused launch as a denial of the first permission that allows the level."""
    scope, scope_path = _get_launch_scope(owner_user_id)
    await get_launch_permissions(level)[0].record_denial(scope, scope_path)


async def get_permitted_activity(activity_id: str, permission: Permission) -> PxcActivity:
    """Return the activity the id names, provided the signed-in user holds the permission over its owner's activities.

    The activity is looked up before the permission is checked, so an id that names no activity records nothing.

    Raises:
        NoAuthenticatedUser: if no user is signed in.
        PxcActivityNotFound: if the id names no activity.
        PxcActivityNotPermitted: if the user lacks the permission; the refusal is recorded.
    """
    caller_user_id = current_user_id()
    parsed_id = parse_activity_id(activity_id)
    async with session_scope() as session:
        activity = await get_activity(session, parsed_id)
        await require_activity_permission(session, permission, activity.owner_user_id, caller_user_id)
    return activity
