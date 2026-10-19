"""Reads, writes and deletes of ``pxc_activities`` and ``pxc_action_failures``.

Activity reads are scoped to the owner: each takes the owner's id. An author sees only their own
activities, and asking for someone else's looks the same as asking for one that does not exist.
"""

from uuid import UUID

from sqlalchemy import delete, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import AuditChange, AuditOutcome, AuditTarget
from sparkth.lib.log import get_logger
from sparkth.lib.models import utc_now
from sparkth.plugins.pxc.audit import PXC_ACTIVITY_TARGET, PxcActivityDeletedAuditEvent
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.models import PxcActionFailure, PxcActivity

logger = get_logger(__name__)


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


def _create_audit_snapshot(activity: PxcActivity) -> dict[str, str | bool]:
    return {"title": activity.title, "placed": activity.placed_at is not None}


async def delete_activity(session: AsyncSession, activity: PxcActivity) -> None:
    """Delete one activity, record ``pxc.activity_deleted`` and commit.

    The audit row commits atomically with the deletion (fail-closed), and the database deletes the
    activity's failure rows with it. A delete that matches no row, because a concurrent delete got
    there first, records nothing. The caller has already checked ownership.

    Raises:
        PxcActivityNotFound: if the activity's row is already gone.
        SQLAlchemyError: if the delete or its audit record cannot be committed.
    """
    snapshot = _create_audit_snapshot(activity)
    target = AuditTarget(type=PXC_ACTIVITY_TARGET, id=str(activity.id))
    result = await session.exec(delete(PxcActivity).where(col(PxcActivity.id) == activity.id))
    if result.rowcount == 0:
        logger.info("PXC activity %s was already deleted", activity.id)
        raise PxcActivityNotFound(f"Unknown activity: {activity.id}")
    await record_event(
        session,
        PxcActivityDeletedAuditEvent(outcome=AuditOutcome.SUCCESS, target=target, change=AuditChange(old=snapshot)),
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
    """The activity's recorded failures from one revision, newest first: the ``limit`` newest.

    Not scoped to an owner: check ownership with ``get_owned_activity`` first.
    """
    result = await session.exec(
        select(PxcActionFailure)
        .where(PxcActionFailure.activity_id == activity_id, PxcActionFailure.revision == revision)
        .order_by(col(PxcActionFailure.created_at).desc(), col(PxcActionFailure.id).desc())
        .limit(limit)
    )
    return list(result.all())
