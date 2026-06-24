"""Tests for the /user/me endpoint, focused on the computed is_admin flag.

is_admin is not a stored column — it is derived from whether the user holds the
global ``admin`` role, so these tests seed role assignments and assert the
endpoint reflects them.
"""

from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.permissions import assign_role
from app.core.permissions.constants import SCOPE_GLOBAL
from app.core.permissions.models import Role
from app.models.user import User


async def _create_user(session: AsyncSession, username: str) -> User:
    user = User(
        name="Test",
        username=username,
        email=f"{username}@example.com",
        hashed_password="fakehash",
    )
    session.add(user)
    await session.flush()
    return user


def _override_current_user(client: AsyncClient, user: User) -> None:
    transport = cast(ASGITransport, client._transport)
    app_instance = cast(FastAPI, transport.app)
    snapshot = User(
        id=user.id,
        name=user.name,
        username=user.username,
        email=user.email,
        hashed_password=user.hashed_password,
    )
    make_transient(snapshot)

    async def override() -> User:
        return snapshot

    app_instance.dependency_overrides[get_current_user] = override


async def test_me_reports_admin_when_user_holds_global_admin_role(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "root")
    assert user.id is not None
    session.add(Role(name="admin"))
    await session.flush()
    await assign_role(user.id, "admin", SCOPE_GLOBAL, None, session)
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["is_admin"] is True


async def test_me_reports_non_admin_for_regular_user(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "regular")
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["is_admin"] is False


async def test_me_admin_role_at_other_scope_does_not_grant_global_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _create_user(session, "scoped")
    assert user.id is not None
    session.add(Role(name="admin"))
    await session.flush()
    await assign_role(user.id, "admin", "course", "1", session)
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["is_admin"] is False
