"""Owner-scoped reads and writes of generated activities."""

from datetime import timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import utc_now
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.store import get_owned_activity, insert_activity, list_owned_activities

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
