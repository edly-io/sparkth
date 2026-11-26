import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.testing import make_user
from sparkth.services.users.exceptions import UserNotFound
from sparkth.services.users.service import get_user, list_users


async def test_list_users_orders_by_username(session: AsyncSession) -> None:
    await make_user(session, "bo")
    await make_user(session, "ada")

    assert [user.username for user in await list_users(None, 50, 0, session)] == ["ada", "bo"]


async def test_list_users_treats_wildcards_literally(session: AsyncSession) -> None:
    await make_user(session, "axb")
    await make_user(session, "a_b")

    assert await list_users("%", 50, 0, session) == []
    assert [user.username for user in await list_users("_", 50, 0, session)] == ["a_b"]


async def test_list_users_matches_name_username_or_email_ignoring_case(session: AsyncSession) -> None:
    session.add_all(
        [
            User(name="Grace Hopper", username="gh", email="gh@example.com", hashed_password="x"),
            User(name="T", username="linus", email="t@example.com", hashed_password="x"),
            User(name="T", username="other", email="ada@lovelace.org", hashed_password="x"),
        ]
    )
    await session.flush()

    for term, username in [("HOPPER", "gh"), ("LIN", "linus"), ("lovelace", "other")]:
        assert [user.username for user in await list_users(term, 50, 0, session)] == [username]


async def test_list_users_pages(session: AsyncSession) -> None:
    for username in ["a", "b", "c"]:
        await make_user(session, username)

    assert [user.username for user in await list_users(None, 1, 1, session)] == ["b"]


async def test_list_users_skips_soft_deleted(session: AsyncSession) -> None:
    ada = await make_user(session, "ada")
    await make_user(session, "bo")
    ada.soft_delete()
    await session.flush()

    assert [user.username for user in await list_users(None, 50, 0, session)] == ["bo"]


async def test_get_user_returns_the_user(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    assert user.id is not None

    assert (await get_user(user.id, session)).username == "ada"


async def test_get_user_raises_for_unknown_id(session: AsyncSession) -> None:
    with pytest.raises(UserNotFound):
        await get_user(999999, session)


async def test_get_user_raises_for_soft_deleted_user(session: AsyncSession) -> None:
    user = await make_user(session, "ada")
    assert user.id is not None
    user.soft_delete()
    await session.flush()

    with pytest.raises(UserNotFound):
        await get_user(user.id, session)
