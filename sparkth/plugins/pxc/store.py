"""Reads and writes of ``pxc_activities``, scoped to the activity's owner.

Every read takes the owner's id. An author sees only their own activities, and asking for
someone else's looks the same as asking for one that does not exist.
"""

from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.models import PxcActivity


async def insert_activity(session: AsyncSession, activity: PxcActivity) -> None:
    """Record one freshly built activity and commit it."""
    session.add(activity)
    await session.commit()


async def list_owned_activities(
    session: AsyncSession, owner_user_id: int, limit: int | None = None
) -> list[PxcActivity]:
    """The activities this user built, newest first: all of them, or the newest ``limit``."""
    result = await session.exec(
        select(PxcActivity)
        .where(PxcActivity.owner_user_id == owner_user_id)
        .order_by(col(PxcActivity.created_at).desc())
        .limit(limit)
    )
    return list(result.all())


async def get_owned_activity(session: AsyncSession, activity_id: UUID, owner_user_id: int) -> PxcActivity:
    """One activity, provided this user owns it.

    Raises:
        PxcActivityNotFound: if no activity has this id, or another user owns it.
    """
    result = await session.exec(
        select(PxcActivity).where(PxcActivity.id == activity_id, PxcActivity.owner_user_id == owner_user_id)
    )
    activity = result.first()
    if activity is None:
        raise PxcActivityNotFound(f"Unknown activity: {activity_id}")
    return activity
