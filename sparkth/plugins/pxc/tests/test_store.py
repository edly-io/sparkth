"""Owner-scoped reads and writes of generated activities."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from sqlite3 import Connection
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import User, utc_now
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.plugins.pxc.enums import PreviewPermission, PxcFailureKind
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.models import PxcActionFailure, PxcActivity
from sparkth.plugins.pxc.store import (
    delete_activity,
    get_owned_activity,
    insert_action_failure,
    insert_activity,
    list_action_failures,
    list_owned_activities,
)

OWNER = 1
OTHER_USER = 2


def _activity(owner_user_id: int, title: str = "Fractions") -> PxcActivity:
    return PxcActivity(owner_user_id=owner_user_id, title=title, description="Order three fractions")


async def test_an_inserted_activity_is_listed_for_its_owner(session: AsyncSession) -> None:
    activity = _activity(OWNER)
    await insert_activity(session, activity)

    assert [listed.id for listed in await list_owned_activities(session, OWNER)] == [activity.id]


async def test_another_users_activities_are_not_listed(session: AsyncSession) -> None:
    await insert_activity(session, _activity(OTHER_USER))

    assert await list_owned_activities(session, OWNER) == []


async def test_activities_are_listed_newest_first(session: AsyncSession) -> None:
    # Inserted newest first, so an insertion-ordered listing would fail this.
    await insert_activity(session, _activity(OWNER, "Newer"))
    older = PxcActivity(
        owner_user_id=OWNER,
        title="Older",
        description="Order three fractions",
        created_at=utc_now() - timedelta(days=1),
    )
    await insert_activity(session, older)

    assert [listed.title for listed in await list_owned_activities(session, OWNER)] == ["Newer", "Older"]


async def test_the_owner_gets_their_activity(session: AsyncSession) -> None:
    activity = _activity(OWNER)
    await insert_activity(session, activity)

    assert (await get_owned_activity(session, activity.id, OWNER)).title == "Fractions"


async def test_another_users_activity_is_not_found(session: AsyncSession) -> None:
    activity = _activity(OTHER_USER)
    await insert_activity(session, activity)

    with pytest.raises(PxcActivityNotFound):
        await get_owned_activity(session, activity.id, OWNER)


async def test_an_unknown_activity_is_not_found(session: AsyncSession) -> None:
    with pytest.raises(PxcActivityNotFound):
        await get_owned_activity(session, uuid7(), OWNER)


async def test_two_activities_with_the_same_title_are_both_kept(session: AsyncSession) -> None:
    # Every edit is a new immutable activity, so no uniqueness rule may refuse the second.
    for _ in range(2):
        await insert_activity(session, _activity(OWNER, "Quiz"))

    assert [activity.title for activity in await list_owned_activities(session, OWNER)] == ["Quiz", "Quiz"]


def _failure(activity_id: UUID, revision: str | None, action: str) -> PxcActionFailure:
    return PxcActionFailure(
        activity_id=activity_id,
        revision=revision,
        kind=PxcFailureKind.FAILED,
        action=action,
        permission=PreviewPermission.PLAY,
        value="[0]",
        error="boom",
    )


async def test_failures_are_listed_newest_first_for_one_revision(session: AsyncSession) -> None:
    activity = _activity(OWNER)
    await insert_activity(session, activity)
    for action in ("first", "second"):
        await insert_action_failure(session, _failure(activity.id, "rev-a", action), 20)
    await insert_action_failure(session, _failure(activity.id, "rev-b", "other revision"), 20)

    listed = await list_action_failures(session, activity.id, "rev-a", 20)

    assert [failure.action for failure in listed] == ["second", "first"]


async def test_only_an_activitys_newest_failures_are_kept(session: AsyncSession) -> None:
    activity, other = _activity(OWNER), _activity(OWNER, "Other")
    await insert_activity(session, activity)
    await insert_activity(session, other)
    await insert_action_failure(session, _failure(other.id, None, "other activity"), 2)
    for action in ("1", "2", "3"):
        await insert_action_failure(session, _failure(activity.id, None, action), 2)

    assert [failure.action for failure in await list_action_failures(session, activity.id, None, 20)] == ["3", "2"]
    assert len(await list_action_failures(session, other.id, None, 20)) == 1


def _enforce_foreign_keys(dbapi_connection: Connection, _record: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def fk_session() -> AsyncGenerator[AsyncSession]:
    """A session on its own SQLite database that enforces foreign keys, which the shared one does not."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    event.listen(engine.sync_engine, "connect", _enforce_foreign_keys)
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as fk_session:
        yield fk_session
    await engine.dispose()


async def test_deleting_an_activity_deletes_its_failures_and_no_others(fk_session: AsyncSession) -> None:
    fk_session.add(User(id=OWNER, name="Owner", username="owner", email="owner@example.com", hashed_password="x"))
    await fk_session.commit()
    first, second = _activity(OWNER, "First"), _activity(OWNER, "Second")
    for activity in (first, second):
        await insert_activity(fk_session, activity)
        await insert_action_failure(fk_session, _failure(activity.id, None, "play"), 20)

    await fk_session.delete(first)
    await fk_session.commit()

    remaining = (await fk_session.exec(select(PxcActionFailure.activity_id))).all()
    assert remaining == [second.id]


async def _failing_record_event(session: AsyncSession, event: object) -> None:
    raise SQLAlchemyError("audit unavailable")


async def test_deleting_an_activity_removes_its_row_and_records_it(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    activity = PxcActivity(owner_user_id=OWNER, title="Fractions", description="d", placed_at=utc_now())
    await insert_activity(session, activity)

    await delete_activity(session, activity)

    assert await list_owned_activities(session, OWNER) == []
    (event,) = await audit_events()
    assert (event.category, event.action) == ("pxc", "activity_deleted")
    assert event.outcome == "success"
    assert (event.target_type, event.target_id) == ("pxc_activity", str(activity.id))
    assert event.old_values == {"title": "Fractions", "placed": True}
    assert event.new_values is None


async def test_an_activity_is_not_deleted_when_its_audit_record_fails(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    activity = _activity(OWNER)
    await insert_activity(session, activity)
    activity_id = activity.id
    monkeypatch.setattr("sparkth.plugins.pxc.store.record_event", _failing_record_event)

    with pytest.raises(SQLAlchemyError):
        await delete_activity(session, activity)

    await session.rollback()
    assert (await get_owned_activity(session, activity_id, OWNER)).id == activity_id
