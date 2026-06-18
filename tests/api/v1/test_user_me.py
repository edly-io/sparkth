from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.permissions.models import Role, RoleAssignment


def _override(client: AsyncClient, user: User) -> None:
    app_instance = cast(FastAPI, cast(ASGITransport, client._transport).app)
    snapshot = User(
        id=user.id, name=user.name, username=user.username, email=user.email, hashed_password=user.hashed_password
    )
    make_transient(snapshot)

    async def override() -> User:
        return snapshot

    app_instance.dependency_overrides[get_current_user] = override


async def _make_user(session: AsyncSession, username: str) -> User:
    user = User(name="T", username=username, email=f"{username}@e.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


async def test_me_is_admin_true_for_admin(client: AsyncClient, session: AsyncSession) -> None:
    user = await _make_user(session, "alice")
    role = Role(name="admin")
    session.add(role)
    await session.flush()
    assert user.id is not None and role.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id))
    await session.flush()
    _override(client, user)

    resp = await client.get("/api/v1/user/me")
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True


async def test_me_is_admin_false_without_admin_role(client: AsyncClient, session: AsyncSession) -> None:
    user = await _make_user(session, "bob")
    _override(client, user)

    resp = await client.get("/api/v1/user/me")
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False
