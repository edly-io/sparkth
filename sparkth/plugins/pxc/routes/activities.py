"""The author-facing surface, mounted beside the learner routes at ``/api/v1/pxc``.

Every route here needs a signed-in author who holds ``plugin.use`` at ``plugin:pxc``. The learner
routes carry a launch token instead and declare no such dependency, so they are unaffected.

An activity is checked at the ``user`` scope of its owner. A route that names one activity answers
404 for an unknown id before it checks the permission, and 403 for a caller without the permission.
Listing takes the owner from the ``owner_id`` query parameter and defaults to the caller. Launching
checks ``pxc.activity.play`` or ``pxc.activity.edit`` for the requested view, not the permissions that
manage the activity record.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user_id
from sparkth.lib.db import get_async_session
from sparkth.lib.log import get_logger
from sparkth.lib.permissions import get_listed_owner_id
from sparkth.lib.permissions.scopes import USER
from sparkth.plugins.pxc.activities import activity_dir, preview_url
from sparkth.plugins.pxc.enums import PreviewLevel
from sparkth.plugins.pxc.exceptions import PxcActivityNotPermitted
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.permissions import (
    PXC_ACTIVITY_DELETE,
    PXC_ACTIVITY_READ,
    get_launch_permissions,
    has_launch_permission,
    record_launch_denial,
)
from sparkth.plugins.pxc.revisions import remove_activity_files
from sparkth.plugins.pxc.schemas import ActivityLaunch, ActivitySummary
from sparkth.plugins.pxc.store import delete_activity, get_activity, list_owned_activities
from sparkth.plugins.pxc.tokens import mint_preview_token

logger = get_logger(__name__)

router = APIRouter()


async def get_activity_record(activity_id: UUID, session: AsyncSession = Depends(get_async_session)) -> PxcActivity:
    """Resolve the activity id in the path to its row, whoever owns it.

    Raises:
        PxcActivityNotFound: if no activity has this id, before any permission is checked.
    """
    return await get_activity(session, activity_id)


async def get_activity_owner_id(activity: PxcActivity = Depends(get_activity_record)) -> int:
    """The id of the user who owns the activity named in the path."""
    return activity.owner_user_id


@router.get(
    "/activities",
    dependencies=[Depends(PXC_ACTIVITY_READ.require_for_object(USER, get_listed_owner_id))],
)
async def list_activities(
    owner_id: int = Depends(get_listed_owner_id), session: AsyncSession = Depends(get_async_session)
) -> list[ActivitySummary]:
    """The activities a user built, newest first: the ``owner_id`` user's, or the caller's own without it.

    Needs ``pxc.activity.read`` at the listed owner's scope.
    """
    activities = await list_owned_activities(session, owner_id)
    return [
        ActivitySummary(
            id=activity.id,
            title=activity.title,
            description=activity.description,
            created_at=activity.created_at,
            preview_url=preview_url(activity.id),
            placed=activity.placed_at is not None,
        )
        for activity in activities
    ]


@router.get("/activities/{activity_id}/launch")
async def launch_activity(
    activity_id: UUID,
    request: Request,
    permission: PreviewLevel = Query(),
    activity: PxcActivity = Depends(get_activity_record),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
) -> ActivityLaunch:
    """An embed URL that previews an activity, as a learner or as its author.

    A learner preview needs ``pxc.activity.play`` or ``pxc.activity.edit`` and an author preview
    needs ``pxc.activity.edit``, both at the activity owner's scope. The permission depends on the
    requested view, so it is checked in the handler, not in the route's dependencies. The activity's
    files are resolved before a token is minted, so a row whose files are missing from
    ``PXC_DATA_DIR`` never yields an embed URL that would fail on load.

    Raises:
        PxcActivityNotFound: if the activity does not exist or its files are missing.
        PxcActivityNotPermitted: if the caller lacks the permission the view needs.
        PxcLaunchNotConfigured: if no launch secret is configured.
    """
    if not await has_launch_permission(session, permission, activity.owner_user_id, user_id):
        needed = get_launch_permissions(permission)[0]
        logger.warning(
            "PXC launch at level %s denied for user %s on activities of user %s",
            permission,
            user_id,
            activity.owner_user_id,
        )
        await record_launch_denial(permission, activity.owner_user_id)
        raise PxcActivityNotPermitted(f"You are not allowed to do this; it needs the {needed.name} permission.")
    activity_dir(str(activity_id))
    token = mint_preview_token(activity_id, user_id, permission)
    return ActivityLaunch(embed_url=str(request.url_for("embed_activity").include_query_params(token=token)))


@router.delete(
    "/activities/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(PXC_ACTIVITY_DELETE.require_for_object(USER, get_activity_owner_id))],
)
async def remove_activity(
    activity_id: UUID,
    activity: PxcActivity = Depends(get_activity_record),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete an activity: its row, failure rows, files and learner data.

    Needs ``pxc.activity.delete`` at the activity owner's scope. Deletes the row and its
    ``pxc.activity_deleted`` audit event in one commit, then removes the files. A file that cannot
    be removed is logged and left behind.

    Raises:
        PxcActivityNotFound: if the activity does not exist.
        SQLAlchemyError: if the delete or its audit record cannot be committed; nothing is removed.
    """
    await delete_activity(session, activity)
    remove_activity_files(activity_id)
