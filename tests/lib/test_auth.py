from datetime import timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

import sparkth.api.v1.auth as api_auth
import sparkth.lib.auth as lib_auth
from sparkth.core.models.user import User
from sparkth.core.security import create_access_token


async def _seed_user(session: AsyncSession, username: str) -> User:
    user = User(
        name="Auth Test",
        username=username,
        email=f"{username}@example.com",
        hashed_password="not-a-real-hash",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def test_get_current_user_lives_in_lib_auth() -> None:
    assert callable(lib_auth.get_current_user)


def test_get_current_user_not_reexported_from_api_auth() -> None:
    # get_current_user has a single canonical home in sparkth.lib.auth; every caller (routes, the
    # permission dependency, and the test harness's dependency_overrides) imports it from there
    # so they all share one object. sparkth.api.v1.auth must NOT re-export it — a compat shim would
    # split the canonical location and let a dependency_overrides key silently miss.
    assert not hasattr(api_auth, "get_current_user")


class TestDecodeTokenUsername:
    """Reading the subject out of a bearer token.

    Shared by get_current_user and PluginAccessMiddleware so both read tokens the same way.
    """

    def test_returns_the_token_subject(self) -> None:
        token = create_access_token({"sub": "tokenuser"})

        assert lib_auth.decode_token_username(token) == "tokenuser"

    def test_returns_none_for_a_malformed_token(self) -> None:
        assert lib_auth.decode_token_username("not-a-real-token") is None

    def test_returns_none_for_an_expired_token(self) -> None:
        token = create_access_token({"sub": "tokenuser"}, expires_delta=timedelta(minutes=-1))

        assert lib_auth.decode_token_username(token) is None

    def test_returns_none_when_the_token_carries_no_subject(self) -> None:
        assert lib_auth.decode_token_username(create_access_token({})) is None


class TestGetUserByUsername:
    """Looking a user up by username."""

    async def test_returns_the_matching_user(self, session: AsyncSession) -> None:
        await _seed_user(session, "lookupuser")

        found = await lib_auth.get_user_by_username("lookupuser", session)

        assert found is not None
        assert found.username == "lookupuser"

    async def test_returns_none_when_no_user_matches(self, session: AsyncSession) -> None:
        assert await lib_auth.get_user_by_username("nobody-here", session) is None
