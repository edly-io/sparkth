"""Reads and writes of ``pxc_activities`` and ``pxc_action_failures``.

Activity reads are scoped to the owner: each takes the owner's id. An author sees only their own
activities, and asking for someone else's looks the same as asking for one that does not exist.
"""

from uuid import UUID

from sqlalchemy import delete, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import utc_now
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.models import PxcActionFailure, PxcActivity


async def insert_activity(session: AsyncSession, activity: PxcActivity) -> None:
    """Record one freshly built activity and commit it."""
    session.add(activity)
    await session.commit()


async def mark_placed(session: AsyncSession, activity_id: UUID) -> None:
    """Record that this activity has been placed in a course, unless that is already recorded, and commit."""
    await session.exec(
        update(PxcActivity)
        .where(col(PxcActivity.id) == activity_id, col(PxcActivity.placed_at).is_(None))
        .values(placed_at=utc_now())
    )
    await session.commit()


async def update_activity_details(session: AsyncSession, activity_id: UUID, title: str, description: str) -> None:
    """Replace one activity's title and description, and commit."""
    await session.exec(
        update(PxcActivity).where(col(PxcActivity.id) == activity_id).values(title=title, description=description)
    )
    await session.commit()


async def list_owned_activities(
    session: AsyncSession, owner_user_id: int, limit: int | None = None
) -> list[PxcActivity]:
    """The activities this user built, newest first: the `limit` newest, or every one when it is None."""
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


async def insert_action_failure(session: AsyncSession, failure: PxcActionFailure, keep: int) -> None:
    """Record one failed preview action, drop all but the activity's ``keep`` newest, and commit."""
    session.add(failure)
    await session.flush()
    newest = (
        select(PxcActionFailure.id)
        .where(PxcActionFailure.activity_id == failure.activity_id)
        .order_by(col(PxcActionFailure.created_at).desc(), col(PxcActionFailure.id).desc())
        .limit(keep)
    )
    await session.exec(
        delete(PxcActionFailure).where(
            col(PxcActionFailure.activity_id) == failure.activity_id, col(PxcActionFailure.id).not_in(newest)
        )
    )
    await session.commit()


async def list_action_failures(
    session: AsyncSession, activity_id: UUID, revision: str | None, limit: int
) -> list[PxcActionFailure]:
    """The activity's recorded failures from one revision, newest first: the ``limit`` newest."""
    result = await session.exec(
        select(PxcActionFailure)
        .where(PxcActionFailure.activity_id == activity_id, PxcActionFailure.revision == revision)
        .order_by(col(PxcActionFailure.created_at).desc(), col(PxcActionFailure.id).desc())
        .limit(limit)
    )
    return list(result.all())
