"""Tests for the organization-structure API (sparkth/api/v1/org). Authored with LLM (Claude) assistance."""

import uuid
from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.organization import memberships as membership_engine
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.lib.auth import get_current_user
from sparkth.lib.permissions.scopes import GLOBAL

ORG_PERMISSIONS = [
    "organization.unit.create",
    "organization.unit.read",
    "organization.unit.update",
    "organization.unit.delete",
]


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


async def test_create_root_unit_returns_201_with_path(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    response = await client.post("/api/v1/organization/units", json={"name": "University X", "kind": "university"})
    assert response.status_code == 201
    body = response.json()
    assert body["parent_id"] is None
    assert body["path"] == f"/{body['id']}/"


async def test_create_child_unit(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    root = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    response = await client.post("/api/v1/organization/units", json={"name": "CS Dept", "parent_id": root["id"]})
    assert response.status_code == 201
    assert response.json()["path"] == f"{root['path']}{response.json()['id']}/"


async def test_create_duplicate_sibling_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    await client.post("/api/v1/organization/units", json={"name": "University X"})
    response = await client.post("/api/v1/organization/units", json={"name": "University X"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Organizational unit name already taken among siblings: University X"


async def test_get_missing_unit_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    response = await client.get("/api/v1/organization/units/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Organizational unit not found: 99999"


async def test_list_units(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    await client.post("/api/v1/organization/units", json={"name": "University X"})
    response = await client.get("/api/v1/organization/units")
    assert response.status_code == 200
    assert any(u["name"] == "University X" for u in response.json())


async def test_patch_renames(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    created = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    response = await client.patch(f"/api/v1/organization/units/{created['id']}", json={"name": "University Y"})
    assert response.status_code == 200
    assert response.json()["name"] == "University Y"


async def test_patch_moves_unit(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    a = (await client.post("/api/v1/organization/units", json={"name": "Faculty A"})).json()
    b = (await client.post("/api/v1/organization/units", json={"name": "Faculty B"})).json()
    dept = (await client.post("/api/v1/organization/units", json={"name": "CS Dept", "parent_id": a["id"]})).json()
    response = await client.patch(f"/api/v1/organization/units/{dept['id']}", json={"parent_id": b["id"]})
    assert response.status_code == 200
    assert response.json()["parent_id"] == b["id"]
    assert response.json()["path"] == f"{b['path']}{dept['id']}/"


async def test_patch_move_to_root_with_null_parent(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    a = (await client.post("/api/v1/organization/units", json={"name": "Faculty A"})).json()
    dept = (await client.post("/api/v1/organization/units", json={"name": "CS Dept", "parent_id": a["id"]})).json()
    response = await client.patch(f"/api/v1/organization/units/{dept['id']}", json={"parent_id": None})
    assert response.status_code == 200
    assert response.json()["parent_id"] is None


async def test_patch_cycle_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    root = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    child = (await client.post("/api/v1/organization/units", json={"name": "CS Dept", "parent_id": root["id"]})).json()
    response = await client.patch(f"/api/v1/organization/units/{root['id']}", json={"parent_id": child["id"]})
    assert response.status_code == 409


async def test_patch_combined_rename_and_move(client: AsyncClient, session: AsyncSession) -> None:
    # The current parent already holds the target name; the destination does not. The
    # combined PATCH must validate against the destination's siblings and apply both.
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    a = (await client.post("/api/v1/organization/units", json={"name": "Faculty A"})).json()
    b = (await client.post("/api/v1/organization/units", json={"name": "Faculty B"})).json()
    await client.post("/api/v1/organization/units", json={"name": "CS Dept", "parent_id": a["id"]})
    dept = (await client.post("/api/v1/organization/units", json={"name": "Math Dept", "parent_id": a["id"]})).json()

    response = await client.patch(
        f"/api/v1/organization/units/{dept['id']}", json={"name": "CS Dept", "parent_id": b["id"]}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "CS Dept"
    assert response.json()["parent_id"] == b["id"]
    assert response.json()["path"] == f"{b['path']}{dept['id']}/"


async def test_patch_combined_failure_applies_nothing(client: AsyncClient, session: AsyncSession) -> None:
    # A rename combined with a move that 409s (cycle) must leave the rename unapplied.
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    root = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    child = (await client.post("/api/v1/organization/units", json={"name": "CS Dept", "parent_id": root["id"]})).json()

    response = await client.patch(
        f"/api/v1/organization/units/{root['id']}", json={"name": "University Y", "parent_id": child["id"]}
    )

    assert response.status_code == 409
    fresh = (await client.get(f"/api/v1/organization/units/{root['id']}")).json()
    assert fresh["name"] == "University X"


async def test_patch_empty_body_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    created = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    assert (await client.patch(f"/api/v1/organization/units/{created['id']}", json={})).status_code == 422


async def test_delete_leaf_returns_204(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ORG_PERMISSIONS))
    created = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    assert (await client.delete(f"/api/v1/organization/units/{created['id']}")).status_code == 204


async def test_delete_with_member_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user_with_permissions(session, ORG_PERMISSIONS)
    _override_current_user(client, user)
    created = (await client.post("/api/v1/organization/units", json={"name": "University X"})).json()
    assert user.id is not None
    await membership_engine.add_organization_member(user.id, created["id"], session)
    await session.commit()
    assert (await client.delete(f"/api/v1/organization/units/{created['id']}")).status_code == 409


async def test_endpoints_require_permission(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, []))
    assert (await client.get("/api/v1/organization/units")).status_code == 403
    assert (await client.post("/api/v1/organization/units", json={"name": "X"})).status_code == 403
    assert (await client.patch("/api/v1/organization/units/1", json={"name": "x"})).status_code == 403
    assert (await client.delete("/api/v1/organization/units/1")).status_code == 403
