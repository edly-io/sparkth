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
from sparkth.core.permissions.models import Group, Role, RoleAssignment, RolePermission
from sparkth.lib.auth import get_current_user
from sparkth.lib.permissions.scopes import GLOBAL, GROUP

GROUP_PERMISSIONS = ["group.create", "group.read", "group.update", "group.delete"]


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


async def _create_target_group(session: AsyncSession) -> Group:
    """A plain group with an id, used as the object a per-group grant is scoped to."""
    group = Group(name=_uniq("target"))
    session.add(group)
    await session.flush()
    assert group.id is not None
    return group


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


# --- Per-group scoping -------------------------------------------------------------------------
# The endpoints addressing one group by {group_id} authorize at the object-bearing `group` scope, so
# a grant can be delegated to a single group. A global grant still satisfies them via the cascade
# (covered by the global-grant tests above).


async def test_group_scoped_updater_can_update_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    other = await _create_target_group(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["group.update"], "group", str(target.id))
    )
    await session.commit()
    ok = await client.patch(f"/api/v1/permissions/groups/{target.id}", json={"description": "d"})
    assert ok.status_code == 200
    denied = await client.patch(f"/api/v1/permissions/groups/{other.id}", json={"description": "d"})
    assert denied.status_code == 403


async def test_group_scoped_reader_can_get_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    other = await _create_target_group(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["group.read"], "group", str(target.id))
    )
    await session.commit()
    assert (await client.get(f"/api/v1/permissions/groups/{target.id}")).status_code == 200
    assert (await client.get(f"/api/v1/permissions/groups/{other.id}")).status_code == 403
    # A missing group is denied, not reported missing, so group ids cannot be probed.
    assert (await client.get("/api/v1/permissions/groups/99999")).status_code == 403


async def test_group_scoped_deleter_can_delete_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["group.delete"], "group", str(target.id))
    )
    await session.commit()
    assert (await client.delete(f"/api/v1/permissions/groups/{target.id}")).status_code == 204


async def test_group_scoped_grant_does_not_authorize_global_endpoints(
    client: AsyncClient, session: AsyncSession
) -> None:
    # Creating groups stays gated at the global scope; a per-group grant does not cascade UP to global.
    target = await _create_target_group(session)
    _override_current_user(
        client,
        await _create_user_with_permissions(session, ["group.read", "group.create"], "group", str(target.id)),
    )
    await session.commit()
    assert (await client.post("/api/v1/permissions/groups", json={"name": _uniq("x")})).status_code == 403


# --- Filtered list -----------------------------------------------------------------------------
# A caller without a global group.read grant sees only the groups they hold group.read for.


async def _list_group_ids(client: AsyncClient) -> list[int]:
    response = await client.get("/api/v1/permissions/groups")
    assert response.status_code == 200
    return [group["id"] for group in response.json()]


async def test_group_scoped_reader_lists_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    await _create_target_group(session)
    _override_current_user(
        client, await _create_user_with_permissions(session, ["group.read"], "group", str(target.id))
    )
    await session.commit()
    assert await _list_group_ids(client) == [target.id]


async def test_group_read_via_membership_lists_that_group(client: AsyncClient, session: AsyncSession) -> None:
    # group.read at group:<target> is granted to a group the caller belongs to, not to the caller.
    target = await _create_target_group(session)
    await _create_target_group(session)
    managers = await _create_target_group(session)
    user = await _create_user_with_permissions(session, [])
    assert user.id is not None and managers.id is not None
    reader = Role(name=_uniq("reader"))
    session.add(reader)
    await session.flush()
    assert reader.id is not None
    session.add(RolePermission(role_id=reader.id, permission="group.read"))
    await session.flush()
    await group_engine.add_group_member(user.id, managers.id, session)
    await group_engine.assign_role_to_group(managers.id, reader.name, GROUP, str(target.id), session)
    _override_current_user(client, user)
    await session.commit()
    assert await _list_group_ids(client) == [target.id]


async def test_non_numeric_group_grant_is_ignored(client: AsyncClient, session: AsyncSession) -> None:
    # The CLI stores any string as the scope object id; one that names no group id is skipped.
    target = await _create_target_group(session)
    user = await _create_user_with_permissions(session, ["group.read"], "group", "abc")
    assert user.id is not None
    reader = Role(name=_uniq("reader"))
    session.add(reader)
    await session.flush()
    assert reader.id is not None
    session.add(RolePermission(role_id=reader.id, permission="group.read"))
    session.add(RoleAssignment(user_id=user.id, role_id=reader.id, scope="group", scope_object_id=str(target.id)))
    _override_current_user(client, user)
    await session.commit()
    assert await _list_group_ids(client) == [target.id]
