"""Tests for the role-management API (app/api/v1/permissions)."""

import functools
import uuid
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.permissions.routes.roles import _build_role_response
from app.core.db import get_engine
from app.core.permissions import PERMISSIONS, Permission
from app.core.permissions.models import Role, RoleAssignment, RolePermission
from app.lib.auth import get_current_user
from app.models.user import User


def _record_statement(
    sink: list[str],
    conn: object,
    cursor: object,
    statement: str,
    parameters: object,
    context: object,
    executemany: bool,
) -> None:
    """SQLAlchemy before_cursor_execute listener that appends each SQL statement to sink."""
    sink.append(statement)


ROLE_PERMISSIONS = ["role.create", "role.read", "role.update", "role.delete", "permission.read"]


@pytest.fixture(autouse=True)
def _register_assignable_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    # add_role_permission validates the permission against the registry; register it on the
    # PERMISSIONS hook for one test (monkeypatch restores the backing dict afterwards).
    monkeypatch.setitem(PERMISSIONS._items, "assignment.grade", Permission("assignment.grade"))


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_user_with_permissions(
    session: AsyncSession,
    permissions: list[str],
    scope: str = "global",
    scope_object_id: str | None = None,
) -> User:
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
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id))
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


async def test_create_role_returns_201(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    response = await client.post("/api/v1/permissions/roles", json={"name": "grader", "description": "Grades"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "grader"
    assert body["description"] == "Grades"
    assert body["permissions"] == []


async def test_create_duplicate_role_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    await client.post("/api/v1/permissions/roles", json={"name": "grader"})
    response = await client.post("/api/v1/permissions/roles", json={"name": "grader"})
    assert response.status_code == 409


async def test_list_roles_returns_them(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    await client.post("/api/v1/permissions/roles", json={"name": "grader"})
    response = await client.get("/api/v1/permissions/roles")
    assert response.status_code == 200
    assert any(r["name"] == "grader" for r in response.json())


async def test_get_role_returns_it(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    response = await client.get(f"/api/v1/permissions/roles/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "grader"


async def test_get_missing_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    response = await client.get("/api/v1/permissions/roles/99999")
    assert response.status_code == 404


async def test_update_role(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    response = await client.patch(f"/api/v1/permissions/roles/{created['id']}", json={"description": "Updated"})
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"


async def test_update_role_empty_body_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    # A fully-empty update would silently no-op; it must be rejected before hitting the DB.
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    assert (await client.patch(f"/api/v1/permissions/roles/{created['id']}", json={})).status_code == 422


async def test_update_role_only_null_fields_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    response = await client.patch(f"/api/v1/permissions/roles/{created['id']}", json={"description": None})
    assert response.status_code == 422


async def test_delete_role_returns_204(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    response = await client.delete(f"/api/v1/permissions/roles/{created['id']}")
    assert response.status_code == 204
    assert (await client.get(f"/api/v1/permissions/roles/{created['id']}")).status_code == 404


async def test_delete_assigned_role_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user_with_permissions(session, ROLE_PERMISSIONS)
    assert user.id is not None
    _override_current_user(client, user)
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    session.add(RoleAssignment(user_id=user.id, role_id=created["id"], scope="global", scope_object_id=None))
    await session.flush()
    response = await client.delete(f"/api/v1/permissions/roles/{created['id']}")
    assert response.status_code == 409


async def test_add_permission_grants_it(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    response = await client.post(
        f"/api/v1/permissions/roles/{created['id']}/permissions", json={"permission": "assignment.grade"}
    )
    assert response.status_code == 200
    assert "assignment.grade" in response.json()["permissions"]


async def test_add_unregistered_permission_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    response = await client.post(
        f"/api/v1/permissions/roles/{created['id']}/permissions", json={"permission": "bogus.unregistered"}
    )
    assert response.status_code == 422


async def test_add_duplicate_permission_is_idempotent(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    path = f"/api/v1/permissions/roles/{created['id']}/permissions"
    await client.post(path, json={"permission": "assignment.grade"})
    response = await client.post(path, json={"permission": "assignment.grade"})
    assert response.status_code == 200
    assert response.json()["permissions"] == ["assignment.grade"]


async def test_remove_permission_returns_204(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()
    await client.post(f"/api/v1/permissions/roles/{created['id']}/permissions", json={"permission": "assignment.grade"})
    response = await client.delete(f"/api/v1/permissions/roles/{created['id']}/permissions/assignment.grade")
    assert response.status_code == 204
    got = await client.get(f"/api/v1/permissions/roles/{created['id']}")
    assert got.json()["permissions"] == []


async def test_available_permissions_lists_registered(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    response = await client.get("/api/v1/permissions")
    assert response.status_code == 200
    assert "assignment.grade" in response.json()


async def test_available_requires_permission_read(client: AsyncClient, session: AsyncSession) -> None:
    # The permission listing is gated on permission.read — holding the role.* permissions (which
    # manage roles) does not grant access to it.
    _override_current_user(client, await _create_user_with_permissions(session, ["role.read"]))
    assert (await client.get("/api/v1/permissions")).status_code == 403


async def test_regular_user_is_forbidden(client: AsyncClient, session: AsyncSession) -> None:
    # A user without any of the gating permissions cannot reach the endpoints.
    _override_current_user(client, await _create_user_with_permissions(session, []))
    assert (await client.get("/api/v1/permissions/roles")).status_code == 403
    assert (await client.post("/api/v1/permissions/roles", json={"name": "x"})).status_code == 403
    assert (await client.get("/api/v1/permissions")).status_code == 403


async def _add_role_with_permission(session: AsyncSession, permission: str) -> Role:
    role = Role(name=_uniq("role"))
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission=permission))
    await session.flush()
    return role


async def test_list_roles_returns_each_roles_own_permissions(client: AsyncClient, session: AsyncSession) -> None:
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    grader = await _add_role_with_permission(session, "assignment.grade")
    viewer = await _add_role_with_permission(session, "assignment.view")
    body = {role["id"]: role["permissions"] for role in (await client.get("/api/v1/permissions/roles")).json()}
    assert body[grader.id] == ["assignment.grade"]
    assert body[viewer.id] == ["assignment.view"]


async def test_list_roles_does_not_n_plus_1_on_permissions(client: AsyncClient, session: AsyncSession) -> None:
    # Grants for all roles must be fetched in a single batched query, not one SELECT per role.
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    for _ in range(5):
        await _add_role_with_permission(session, "assignment.grade")

    statements: list[str] = []
    listener = functools.partial(_record_statement, statements)
    sync_engine = get_engine().sync_engine
    event.listen(sync_engine, "before_cursor_execute", listener)
    try:
        response = await client.get("/api/v1/permissions/roles")
    finally:
        event.remove(sync_engine, "before_cursor_execute", listener)

    assert response.status_code == 200
    role_permission_selects = [
        s for s in statements if s.lstrip().lower().startswith("select") and "role_permission" in s.lower()
    ]
    # One permission-gate check (can()) + one batched grants query — not one grants query per role.
    assert len(role_permission_selects) <= 2, role_permission_selects


def test_build_role_response_without_id_raises() -> None:
    # A persisted role always has an id; if it is missing we fail loudly with a real guard, not a
    # bare assert (which `python -O` would strip), so RoleResponse is never built from bad data.
    with pytest.raises(RuntimeError):
        _build_role_response(Role(name="x"), [])


async def test_create_role_permission_fetches_role_once(client: AsyncClient, session: AsyncSession) -> None:
    # Granting a permission must not re-fetch the role: add_role_permission already loads and returns
    # it, so the handler builds the response from that instance (a single role-by-id SELECT).
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/roles", json={"name": "grader"})).json()

    statements: list[str] = []
    listener = functools.partial(_record_statement, statements)
    sync_engine = get_engine().sync_engine
    event.listen(sync_engine, "before_cursor_execute", listener)
    try:
        response = await client.post(
            f"/api/v1/permissions/roles/{created['id']}/permissions", json={"permission": "assignment.grade"}
        )
    finally:
        event.remove(sync_engine, "before_cursor_execute", listener)

    assert response.status_code == 200
    role_by_id_selects = [s for s in statements if "from role where" in " ".join(s.lower().split())]
    assert len(role_by_id_selects) == 1, role_by_id_selects


# --- Per-role scoping (issue #490) -------------------------------------------------------------
# The endpoints addressing one role by {role_id} authorize at the object-bearing `role` scope, so a
# grant can be delegated to a single role. A global grant still satisfies them via the cascade.


async def _create_target_role(session: AsyncSession) -> Role:
    """A plain role with an id, used as the object a per-role grant is scoped to."""
    role = Role(name=_uniq("target"))
    session.add(role)
    await session.flush()
    assert role.id is not None
    return role


async def test_role_scoped_manager_can_manage_only_that_role(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_role(session)
    other = await _create_target_role(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["role.update"], "role", str(target.id))
    )
    # Commit the setup so it survives each request's session close (a read request rolls back the
    # shared in-memory transaction, which would otherwise wipe uncommitted setup rows).
    await session.commit()
    # Can update the role it is scoped to.
    ok = await client.patch(f"/api/v1/permissions/roles/{target.id}", json={"description": "d"})
    assert ok.status_code == 200
    # Cannot touch a different role.
    denied = await client.patch(f"/api/v1/permissions/roles/{other.id}", json={"description": "d"})
    assert denied.status_code == 403


async def test_role_scoped_manager_can_edit_that_roles_permissions(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_role(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["role.update"], "role", str(target.id))
    )
    await session.commit()
    added = await client.post(
        f"/api/v1/permissions/roles/{target.id}/permissions", json={"permission": "assignment.grade"}
    )
    assert added.status_code == 200
    assert "assignment.grade" in added.json()["permissions"]
    removed = await client.delete(f"/api/v1/permissions/roles/{target.id}/permissions/assignment.grade")
    assert removed.status_code == 204


async def test_role_scoped_reader_can_get_only_that_role(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_role(session)
    other = await _create_target_role(session)
    _override_current_user(client, await _create_user_with_permissions(session, ["role.read"], "role", str(target.id)))
    await session.commit()
    assert (await client.get(f"/api/v1/permissions/roles/{target.id}")).status_code == 200
    assert (await client.get(f"/api/v1/permissions/roles/{other.id}")).status_code == 403


async def test_role_scoped_deleter_can_delete_that_role(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_role(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["role.delete"], "role", str(target.id))
    )
    await session.commit()
    assert (await client.delete(f"/api/v1/permissions/roles/{target.id}")).status_code == 204


async def test_role_scoped_grant_does_not_authorize_global_endpoints(
    client: AsyncClient, session: AsyncSession
) -> None:
    # A per-role grant must not leak into the list-all / create / vocabulary endpoints, which stay
    # gated at the global scope (a role-scoped grant does not cascade UP to global).
    target = await _create_target_role(session)
    _override_current_user(
        client,
        await _create_user_with_permissions(
            session, ["role.read", "role.create", "permission.read"], "role", str(target.id)
        ),
    )
    await session.commit()
    assert (await client.get("/api/v1/permissions/roles")).status_code == 403
    assert (await client.post("/api/v1/permissions/roles", json={"name": _uniq("x")})).status_code == 403
    assert (await client.get("/api/v1/permissions")).status_code == 403


async def test_global_admin_still_manages_every_role(client: AsyncClient, session: AsyncSession) -> None:
    # Existing global admins keep full authority over per-role endpoints via the global->role cascade.
    target = await _create_target_role(session)
    _override_current_user(client, await _create_user_with_permissions(session, ROLE_PERMISSIONS))
    await session.commit()
    assert (await client.get(f"/api/v1/permissions/roles/{target.id}")).status_code == 200
    assert (await client.patch(f"/api/v1/permissions/roles/{target.id}", json={"description": "d"})).status_code == 200
    assert (await client.delete(f"/api/v1/permissions/roles/{target.id}")).status_code == 204


async def test_unauthorized_user_gets_403_before_404_on_missing_role(
    client: AsyncClient, session: AsyncSession
) -> None:
    # The permission gate runs before the route's role lookup: an unauthorized user hitting a
    # nonexistent role id is denied (403), not told it is missing (404).
    _override_current_user(client, await _create_user_with_permissions(session, []))
    await session.commit()
    assert (await client.get("/api/v1/permissions/roles/99999")).status_code == 403
