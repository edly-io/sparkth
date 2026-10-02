import asyncio
from collections.abc import AsyncIterator
from contextvars import Context
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

import sparkth.api.v1.auth as api_auth
import sparkth.lib.auth as lib_auth
from sparkth.core.models.user import User
from sparkth.core.security import create_access_token
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.main import app


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


class TestGetCurrentUserBindsAuditActor:
    """Every authenticated request attributes its audit events to the caller."""

    async def test_full_lookup_binds_the_actor(self, session: AsyncSession) -> None:
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials

        from sparkth.lib.audit.context import AuditRequestContext, UserActor, audit_context, current_audit_context

        user = await _seed_user(session, "actoruser")
        request = Request({"type": "http", "headers": [], "state": {}})
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_access_token({"sub": user.username})
        )

        with audit_context(AuditRequestContext(request_id="r1")):
            await lib_auth.get_current_user(request, credentials, session)
            assert current_audit_context().actor == UserActor(id=str(user.id), label=user.username)

    async def test_cached_gate_user_binds_the_actor(self, session: AsyncSession) -> None:
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials

        from sparkth.lib.audit.context import AuditRequestContext, UserActor, audit_context, current_audit_context

        user = await _seed_user(session, "cacheduser")
        request = Request({"type": "http", "headers": [], "state": {}})
        request.state.user = user
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="ignored")

        with audit_context(AuditRequestContext(request_id="r2")):
            await lib_auth.get_current_user(request, credentials, session)
            assert current_audit_context().actor == UserActor(id=str(user.id), label=user.username)


# A minimal app whose streamed body reads the id from a task it spawns, as chat's stream does.
_probe_app = FastAPI()


async def _read_owner() -> int:
    return lib_auth.current_user_id()


async def _owner_stream() -> AsyncIterator[str]:
    yield str(await asyncio.create_task(_read_owner()))


@_probe_app.get("/owner", dependencies=[Depends(lib_auth.get_current_user)])
async def _owner() -> StreamingResponse:
    return StreamingResponse(_owner_stream())


class TestCurrentUserId:
    """Tool handlers learn who is calling from here, never from a model-supplied argument."""

    def test_nothing_bound_raises(self) -> None:
        with pytest.raises(NoAuthenticatedUser):
            Context().run(lib_auth.current_user_id)

    async def test_full_lookup_binds_the_id(self, session: AsyncSession) -> None:
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials

        user = await _seed_user(session, "iduser")
        request = Request({"type": "http", "headers": [], "state": {}})
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_access_token({"sub": user.username})
        )

        await lib_auth.get_current_user(request, credentials, session)

        assert lib_auth.current_user_id() == user.id

    async def test_cached_gate_user_binds_the_id(self, session: AsyncSession) -> None:
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials

        user = await _seed_user(session, "cachedid")
        request = Request({"type": "http", "headers": [], "state": {}})
        request.state.user = user

        await lib_auth.get_current_user(
            request, HTTPAuthorizationCredentials(scheme="Bearer", credentials="x"), session
        )

        assert lib_auth.current_user_id() == user.id

    async def test_the_id_reaches_a_task_spawned_by_a_streamed_response(self, session: AsyncSession) -> None:
        """Chat runs tools on a task detached from its streamed response; the id must follow."""
        user = await _seed_user(session, "streamid")
        token = create_access_token({"sub": user.username})

        async with AsyncClient(transport=ASGITransport(app=_probe_app), base_url="http://test") as client:
            response = await client.get("/owner", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.text == str(user.id)

    async def test_the_current_user_fixture_binds_the_id(self, current_user: User) -> None:
        await app.dependency_overrides[lib_auth.get_current_user]()

        assert lib_auth.current_user_id() == current_user.id
