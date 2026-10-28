from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.services.users import get_usernames


async def _users(session: AsyncSession) -> None:
    session.add_all(
        [
            User(id=1, name="Ada", username="ada", email="ada@example.com", hashed_password="x"),
            User(id=2, name="Bo", username="bo", email="bo@example.com", hashed_password="x"),
        ]
    )
    await session.flush()


async def test_maps_each_known_id_to_its_username(session: AsyncSession) -> None:
    await _users(session)

    assert await get_usernames(session, [1, 2, 999]) == {1: "ada", 2: "bo"}


async def test_no_ids_gives_no_names(session: AsyncSession) -> None:
    await _users(session)

    assert await get_usernames(session, []) == {}
