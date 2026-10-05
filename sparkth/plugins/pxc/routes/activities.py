"""The author-facing surface, mounted beside the learner routes at ``/api/v1/pxc``.

Every route here depends on ``get_current_user``, which is what turns away a request with no
signed-in author. The learner routes carry a launch token instead and declare no such
dependency, so they are unaffected.
"""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.models import User
from sparkth.plugins.pxc.activities import activity_dir, preview_url
from sparkth.plugins.pxc.enums import PreviewPermission
from sparkth.plugins.pxc.schemas import ActivityLaunch, ActivitySummary
from sparkth.plugins.pxc.store import get_owned_activity, list_owned_activities
from sparkth.plugins.pxc.tokens import mint_preview_token

router = APIRouter()


@router.get("/activities")
async def list_activities(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)
) -> list[ActivitySummary]:
    """The activities this user built, newest first."""
    activities = await list_owned_activities(session, cast(int, user.id))
    return [
        ActivitySummary(
            id=activity.id,
            title=activity.title,
            description=activity.description,
            created_at=activity.created_at,
            preview_url=preview_url(activity.id),
        )
        for activity in activities
    ]


@router.get("/activities/{activity_id}/launch")
async def launch_activity(
    activity_id: UUID,
    request: Request,
    permission: PreviewPermission = Query(),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ActivityLaunch:
    """An embed URL that previews one of this user's activities, as a learner or as its author.

    The activity's files are resolved before a token is minted, so a row whose files are
    missing from ``PXC_DATA_DIR`` never yields an embed URL that would fail on load.

    Raises:
        PxcActivityNotFound: if the activity does not exist, another user owns it, or its files
            are missing.
        PxcLaunchNotConfigured: if no launch secret is configured.
    """
    await get_owned_activity(session, activity_id, cast(int, user.id))
    activity_dir(str(activity_id))
    token = mint_preview_token(activity_id, cast(int, user.id), permission)
    return ActivityLaunch(embed_url=str(request.url_for("embed_activity").include_query_params(token=token)))
