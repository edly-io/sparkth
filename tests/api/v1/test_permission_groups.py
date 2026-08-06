"""Tests for the group-management API (sparkth/api/v1/permissions/routes/groups.py).
Authored with LLM (Claude) assistance."""

import uuid
from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.lib.auth import get_current_user
from sparkth.lib.permissions.scopes import GLOBAL

GROUP_PERMISSIONS = ["group.create", "group.read", "group.update", "group.delete"]


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_user_with_permissions(session: AsyncSession, permissions: list[str]) -> User:
    user = User(name="Admin", username=_uniq("admin"), email=f"{_uniq('admin')}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    assert user.id is not None
    role = Role(name=_uniq("role"))
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
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


async def test_create_group_returns_201(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    response = await client.post("/api/v1/permissions/groups", json={"name": "cs-staff", "description": "CS"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "cs-staff"
    assert body["description"] == "CS"


async def test_create_duplicate_group_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})
    response = await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Group already exists: cs-staff"


async def test_list_groups_returns_them(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})
    response = await client.get("/api/v1/permissions/groups")
    assert response.status_code == 200
    assert any(g["name"] == "cs-staff" for g in response.json())


async def test_get_group_returns_it(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    response = await client.get(f"/api/v1/permissions/groups/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "cs-staff"


async def test_get_missing_group_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    response = await client.get("/api/v1/permissions/groups/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Group not found: 99999"


async def test_update_group(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    response = await client.patch(f"/api/v1/permissions/groups/{created['id']}", json={"description": "Updated"})
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"


async def test_update_group_empty_body_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    # A fully-empty update would silently no-op; it must be rejected before hitting the DB.
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    assert (await client.patch(f"/api/v1/permissions/groups/{created['id']}", json={})).status_code == 422


async def test_delete_group_returns_204(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    assert (await client.delete(f"/api/v1/permissions/groups/{created['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/permissions/groups/{created['id']}")).status_code == 404


async def test_delete_group_with_active_assignment_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    role = Role(name=_uniq("granted"))
    session.add(role)
    await session.flush()
    await group_engine.assign_role_to_group(created["id"], role.name, GLOBAL, None, session)
    await session.commit()
    response = await client.delete(f"/api/v1/permissions/groups/{created['id']}")
    assert response.status_code == 409


async def test_group_endpoints_require_permission(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, []))
    assert (await client.get("/api/v1/permissions/groups")).status_code == 403
    assert (await client.post("/api/v1/permissions/groups", json={"name": "x"})).status_code == 403
