"""Tests for the saved Explore views service."""

import uuid

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.services.analytics_views import (
    AnalyticsViewAlreadyExists,
    AnalyticsViewNotFound,
    create_view,
    delete_view,
    get_view,
    list_views,
    update_view,
)

CONFIG = {"event": "auth.login", "filters": [], "measure": "count", "chart": "line"}


@pytest.fixture(autouse=True)
async def _users(session: AsyncSession) -> None:
    for i in (1, 2):
        session.add(User(id=i, name=f"U{i}", username=f"u{i}", email=f"u{i}@example.com", hashed_password="x"))
    await session.commit()


async def test_create_then_list_returns_only_own_views(session: AsyncSession) -> None:
    mine = await create_view(session, 1, "Logins", CONFIG)
    await create_view(session, 2, "Theirs", CONFIG)

    views = await list_views(session, 1)

    assert [v.id for v in views] == [mine.id]
    assert views[0].name == "Logins"
    assert views[0].config == CONFIG


async def test_get_update_delete_of_another_users_view_raise_not_found(session: AsyncSession) -> None:
    theirs = await create_view(session, 2, "Theirs", CONFIG)

    with pytest.raises(AnalyticsViewNotFound):
        await get_view(session, 1, theirs.id)
    with pytest.raises(AnalyticsViewNotFound):
        await update_view(session, 1, theirs.id, name="Mine now", config=None)
    with pytest.raises(AnalyticsViewNotFound):
        await delete_view(session, 1, theirs.id)
    with pytest.raises(AnalyticsViewNotFound):
        await get_view(session, 1, uuid.uuid4())
    assert (await get_view(session, 2, theirs.id)).name == "Theirs"


async def test_duplicate_name_for_same_owner_raises_already_exists(session: AsyncSession) -> None:
    await create_view(session, 1, "Logins", CONFIG)

    with pytest.raises(AnalyticsViewAlreadyExists):
        await create_view(session, 1, "Logins", CONFIG)


async def test_same_name_for_different_owners_is_allowed(session: AsyncSession) -> None:
    await create_view(session, 1, "Logins", CONFIG)
    await create_view(session, 2, "Logins", CONFIG)

    assert len(await list_views(session, 2)) == 1


async def test_rename_to_an_existing_name_raises_already_exists(session: AsyncSession) -> None:
    await create_view(session, 1, "Logins", CONFIG)
    other = await create_view(session, 1, "Tools", CONFIG)

    with pytest.raises(AnalyticsViewAlreadyExists):
        await update_view(session, 1, other.id, name="Logins", config=None)


async def test_update_changes_name_and_config_and_delete_removes(session: AsyncSession) -> None:
    view = await create_view(session, 1, "Logins", CONFIG)

    updated = await update_view(session, 1, view.id, name="Renamed", config={"event": None})
    assert (updated.name, updated.config) == ("Renamed", {"event": None})

    await delete_view(session, 1, view.id)
    assert await list_views(session, 1) == []
