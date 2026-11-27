"""Tests for the role-assignment API for users and groups (sparkth/api/v1/permissions/routes/role_assignments.py).
Authored with LLM (Claude) assistance."""

import uuid

from httpx import AsyncClient
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.models import Group, GroupRoleAssignment, Role, RoleAssignment
from sparkth.lib.permissions import AUDIT_READ, can
from sparkth.lib.permissions.scopes import GLOBAL
from sparkth.lib.plugins import get_plugin_loader
from sparkth.lib.testing import (
    AuditEventsFetcher,
    add_role_assignment,
    login_as,
    make_role,
    make_user,
    make_user_with_permissions,
)

RESPONSE_FIELDS = {
    "id",
    "user_id",
    "name",
    "username",
    "role_id",
    "role_name",
    "scope",
    "scope_object_id",
    "assigned_at",
}


GROUP_RESPONSE_FIELDS = {
    "id",
    "group_id",
    "group_name",
    "role_id",
    "role_name",
    "scope",
    "scope_object_id",
    "assigned_at",
}


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _get_id(row: Role | User | Group | RoleAssignment | GroupRoleAssignment | int) -> int:
    """The id of a persisted row, or the id itself when one is given."""
    if isinstance(row, int):
        return row
    assert row.id is not None
    return row.id


def _build_assignments_url(role: Role | int) -> str:
    return f"/api/v1/permissions/roles/{_get_id(role)}/assignments/users"


async def _count_assignments(user: User | int, role: Role, session: AsyncSession) -> int:
    statement = select(func.count()).select_from(RoleAssignment)
    statement = statement.where(
        RoleAssignment.user_id == _get_id(user),
        RoleAssignment.role_id == _get_id(role),
        RoleAssignment.is_deleted == False,
    )
    return (await session.exec(statement)).one()


async def test_assigned_user_gains_and_revoked_user_loses_the_role(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["role.assign", "role.revoke"])
    role = await make_role(session, _uniq("role"), ["audit.read"])
    target = await make_user(session, _uniq("target"))
    await session.commit()
    login_as(client, caller)

    assigned = await client.post(_build_assignments_url(role), json={"user_ids": [target.id], "scope": "global"})
    assert assigned.status_code == 201
    (body,) = assigned.json()
    assert (body["user_id"], body["role_id"], body["role_name"]) == (target.id, role.id, role.name)
    assert (body["scope"], body["scope_object_id"]) == ("global", None)
    assert await can(target, AUDIT_READ, GLOBAL, None, session)

    revoked = await client.request("DELETE", _build_assignments_url(role), json={"assignment_ids": [body["id"]]})
    assert revoked.status_code == 204
    assert not await can(target, AUDIT_READ, GLOBAL, None, session)


async def test_list_user_assignments_returns_active_rows_without_email(
    client: AsyncClient, session: AsyncSession
) -> None:
    caller = await make_user_with_permissions(session, ["role.read"])
    role = await make_role(session, _uniq("role"), [])
    holder = await make_user(session, _uniq("target"))
    former = await make_user(session, _uniq("target"))
    await add_role_assignment(session, holder, role, "global", None)
    (await add_role_assignment(session, former, role, "global", None)).soft_delete()
    await session.commit()
    login_as(client, caller)

    response = await client.get(_build_assignments_url(role))

    assert response.status_code == 200
    (row,) = response.json()
    assert set(row) == RESPONSE_FIELDS
    assert (row["user_id"], row["username"], row["role_id"], row["role_name"]) == (
        holder.id,
        holder.username,
        role.id,
        role.name,
    )


async def test_list_user_assignments_leaves_out_a_soft_deleted_user(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["role.read"])
    role = await make_role(session, _uniq("role"), [])
    kept = await make_user(session, _uniq("kept"))
    gone = await make_user(session, _uniq("gone"))
    await add_role_assignment(session, kept, role, "global", None)
    await add_role_assignment(session, gone, role, "global", None)
    gone.soft_delete()
    await session.flush()
    await session.commit()
    login_as(client, caller)

    response = await client.get(_build_assignments_url(role))

    assert response.status_code == 200
    assert [row["user_id"] for row in response.json()] == [kept.id]


async def test_list_user_assignments_pages(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["role.read"])
    role = await make_role(session, _uniq("role"), [])
    holders = [await make_user(session, _uniq("target")) for _ in range(3)]
    rows = [await add_role_assignment(session, holder, role, "global", None) for holder in holders]
    await session.commit()
    login_as(client, caller)

    response = await client.get(_build_assignments_url(role), params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [rows[1].id]


async def test_list_user_assignments_requires_role_read_at_that_role(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    other = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.read"], "role", str(other.id)))
    await session.commit()

    assert (await client.get(_build_assignments_url(role))).status_code == 403


async def test_assign_records_the_audit_event_for_the_caller(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    caller = await make_user_with_permissions(session, ["role.assign"])
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    await session.commit()
    login_as(client, caller)

    await client.post(_build_assignments_url(role), json={"user_ids": [target.id], "scope": "global"})

    event = (await audit_events())[-1]
    assert (event.category, event.action, event.actor_id) == ("role", "assigned", str(caller.id))
    assert (event.target_type, event.target_id) == ("user", str(target.id))


async def test_assign_twice_returns_the_same_row_and_records_once(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()
    payload = {"user_ids": [target.id], "scope": "global"}

    first = await client.post(_build_assignments_url(role), json=payload)
    second = await client.post(_build_assignments_url(role), json=payload)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()[0]["id"] == second.json()[0]["id"]
    assert [e.action for e in await audit_events() if e.category == "role"].count("assigned") == 1


async def test_assign_at_an_object_scope(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    group = Group(name=_uniq("group"))
    session.add(group)
    await session.flush()
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role),
        json={"user_ids": [target.id], "scope": "group", "scope_object_id": str(group.id)},
    )

    assert response.status_code == 201
    (body,) = response.json()
    assert (body["scope"], body["scope_object_id"]) == ("group", str(group.id))


async def test_assign_unknown_user_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": [999999], "scope": "global"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found: 999999"
    assert await _count_assignments(999999, role, session) == 0


async def test_assign_soft_deleted_user_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    gone = await make_user(session, _uniq("target"))
    gone.soft_delete()
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": [gone.id], "scope": "global"})

    assert response.status_code == 404
    assert await _count_assignments(gone, role, session) == 0


async def test_assign_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(999999), json={"user_ids": [target.id], "scope": "global"})

    assert response.status_code == 404


async def test_list_user_assignments_of_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, ["role.read"]))
    await session.commit()

    assert (await client.get(_build_assignments_url(999999))).status_code == 404


async def test_revoke_under_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    assert (
        await client.request("DELETE", _build_assignments_url(999999), json={"assignment_ids": [1]})
    ).status_code == 404


async def test_assign_unknown_scope_kind_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": [target.id], "scope": "galaxy"})

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 0


async def test_assign_objectless_scope_with_an_object_id_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role), json={"user_ids": [target.id], "scope": "global", "scope_object_id": "1"}
    )

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 0


async def test_assign_object_scope_without_an_object_id_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": [target.id], "scope": "group"})

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 0


async def test_assign_at_an_unloaded_plugin_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role),
        json={"user_ids": [target.id], "scope": "plugin", "scope_object_id": "no-such-plugin"},
    )

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 0


async def test_assign_at_a_loaded_plugin_returns_201(client: AsyncClient, session: AsyncSession) -> None:
    loaded = get_plugin_loader().get_loaded_plugins()
    assert loaded
    plugin_name = loaded[0][0]
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role),
        json={"user_ids": [target.id], "scope": "plugin", "scope_object_id": plugin_name},
    )

    assert response.status_code == 201
    (body,) = response.json()
    assert (body["scope"], body["scope_object_id"]) == ("plugin", plugin_name)


async def test_assign_without_a_scope_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    assert (await client.post(_build_assignments_url(role), json={"user_ids": [target.id]})).status_code == 422


async def test_assign_with_an_overlong_object_id_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role),
        json={"user_ids": [target.id], "scope": "group", "scope_object_id": "9" * 101},
    )

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 0


async def test_revoke_records_the_audit_event_for_the_caller(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    caller = await make_user_with_permissions(session, ["role.revoke"])
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    assignment = await add_role_assignment(session, target, role, "global", None)
    await session.commit()
    login_as(client, caller)

    await client.request("DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]})

    event = (await audit_events())[-1]
    assert (event.category, event.action, event.actor_id) == ("role", "unassigned", str(caller.id))
    assert (event.target_type, event.target_id) == ("user", str(target.id))


async def test_revoke_unknown_assignment_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request("DELETE", _build_assignments_url(role), json={"assignment_ids": [999999]})

    assert response.status_code == 404
    assert response.json()["detail"] == "Role assignment not found: 999999"


async def test_revoke_an_assignment_of_another_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role_a = await make_role(session, _uniq("role"), [])
    role_b = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    assignment = await add_role_assignment(session, target, role_b, "global", None)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role_a), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert response.status_code == 404
    assert await _count_assignments(target, role_b, session) == 1


async def test_revoke_twice_returns_404_the_second_time(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    assignment = await add_role_assignment(session, target, role, "global", None)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    first = await client.request("DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]})
    second = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert (first.status_code, second.status_code) == (204, 404)


async def test_revoke_an_assignment_at_an_unregistered_scope_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    assignment = await add_role_assignment(session, target, role, "ghost", None)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 1


async def test_role_assign_does_not_allow_revoke(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    assignment = await add_role_assignment(session, target, role, "global", None)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    assert (
        await client.request("DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]})
    ).status_code == 403


async def test_role_revoke_does_not_allow_assign(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": [target.id], "scope": "global"})

    assert response.status_code == 403


def _build_group_assignments_url(role: Role | int) -> str:
    return f"/api/v1/permissions/roles/{_get_id(role)}/assignments/groups"


async def _make_group(session: AsyncSession) -> Group:
    group = Group(name=_uniq("group"))
    session.add(group)
    await session.flush()
    return group


async def _add_group_assignment(
    group: Group, role: Role, session: AsyncSession, scope: str = "global"
) -> GroupRoleAssignment:
    assignment = GroupRoleAssignment(group_id=_get_id(group), role_id=_get_id(role), scope=scope, scope_object_id=None)
    session.add(assignment)
    await session.flush()
    return assignment


async def _count_group_assignments(group: Group | int, role: Role, session: AsyncSession) -> int:
    statement = select(func.count()).select_from(GroupRoleAssignment)
    statement = statement.where(
        GroupRoleAssignment.group_id == _get_id(group),
        GroupRoleAssignment.role_id == _get_id(role),
        GroupRoleAssignment.is_deleted == False,
    )
    return (await session.exec(statement)).one()


async def test_group_assignment_gives_and_takes_the_role_for_members(
    client: AsyncClient, session: AsyncSession
) -> None:
    caller = await make_user_with_permissions(session, ["role.assign", "role.revoke"])
    role = await make_role(session, _uniq("role"), ["audit.read"])
    group = await _make_group(session)
    member = await make_user(session, _uniq("member"))
    await group_engine.add_group_member(_get_id(member), _get_id(group), session)
    await session.commit()
    login_as(client, caller)
    assert not await can(member, AUDIT_READ, GLOBAL, None, session)

    assigned = await client.post(_build_group_assignments_url(role), json={"group_ids": [group.id], "scope": "global"})
    assert assigned.status_code == 201
    (body,) = assigned.json()
    assert (body["group_id"], body["role_id"], body["role_name"]) == (group.id, role.id, role.name)
    assert (body["scope"], body["scope_object_id"]) == ("global", None)
    assert await can(member, AUDIT_READ, GLOBAL, None, session)

    revoked = await client.request("DELETE", _build_group_assignments_url(role), json={"assignment_ids": [body["id"]]})
    assert revoked.status_code == 204
    assert not await can(member, AUDIT_READ, GLOBAL, None, session)


async def test_list_group_assignments_returns_active_rows(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["role.read"])
    role = await make_role(session, _uniq("role"), [])
    holder = await _make_group(session)
    former = await _make_group(session)
    await _add_group_assignment(holder, role, session)
    (await _add_group_assignment(former, role, session)).soft_delete()
    await session.commit()
    login_as(client, caller)

    response = await client.get(_build_group_assignments_url(role))

    assert response.status_code == 200
    (row,) = response.json()
    assert set(row) == GROUP_RESPONSE_FIELDS
    assert (row["group_id"], row["group_name"], row["role_id"], row["role_name"]) == (
        holder.id,
        holder.name,
        role.id,
        role.name,
    )


async def test_assign_to_group_records_the_audit_event_for_the_caller(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    caller = await make_user_with_permissions(session, ["role.assign"])
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    await session.commit()
    login_as(client, caller)

    await client.post(_build_group_assignments_url(role), json={"group_ids": [group.id], "scope": "global"})

    event = (await audit_events())[-1]
    assert (event.category, event.action, event.actor_id) == ("group", "role_assigned", str(caller.id))
    assert (event.target_type, event.target_id) == ("group", str(group.id))


async def test_assign_to_group_twice_returns_the_same_row_and_records_once(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()
    payload = {"group_ids": [group.id], "scope": "global"}

    first = await client.post(_build_group_assignments_url(role), json=payload)
    second = await client.post(_build_group_assignments_url(role), json=payload)

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()[0]["id"] == second.json()[0]["id"]
    assert [e.action for e in await audit_events() if e.category == "group"].count("role_assigned") == 1


async def test_assign_to_unknown_group_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_group_assignments_url(role), json={"group_ids": [999999], "scope": "global"})

    assert response.status_code == 404
    assert await _count_group_assignments(999999, role, session) == 0


async def test_assign_to_group_at_an_unknown_scope_kind_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_group_assignments_url(role), json={"group_ids": [group.id], "scope": "galaxy"})

    assert response.status_code == 422
    assert await _count_group_assignments(group, role, session) == 0


async def test_revoke_from_group_records_the_audit_event_for_the_caller(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    caller = await make_user_with_permissions(session, ["role.revoke"])
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    assignment = await _add_group_assignment(group, role, session)
    await session.commit()
    login_as(client, caller)

    await client.request("DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]})

    event = (await audit_events())[-1]
    assert (event.category, event.action, event.actor_id) == ("group", "role_revoked", str(caller.id))
    assert (event.target_type, event.target_id) == ("group", str(group.id))


async def test_revoke_unknown_group_assignment_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request("DELETE", _build_group_assignments_url(role), json={"assignment_ids": [999999]})

    assert response.status_code == 404


async def test_revoke_a_group_assignment_of_another_role_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    role_a = await make_role(session, _uniq("role"), [])
    role_b = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    assignment = await _add_group_assignment(group, role_b, session)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role_a), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert response.status_code == 404
    assert await _count_group_assignments(group, role_b, session) == 1


async def test_assign_to_group_with_an_overlong_object_id_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_group_assignments_url(role),
        json={"group_ids": [group.id], "scope": "group", "scope_object_id": "9" * 101},
    )

    assert response.status_code == 422
    assert await _count_group_assignments(group, role, session) == 0


async def test_assign_to_group_objectless_scope_with_an_object_id_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_group_assignments_url(role), json={"group_ids": [group.id], "scope": "global", "scope_object_id": "1"}
    )

    assert response.status_code == 422
    assert await _count_group_assignments(group, role, session) == 0


async def test_assign_to_group_object_scope_without_an_object_id_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_group_assignments_url(role), json={"group_ids": [group.id], "scope": "group"})

    assert response.status_code == 422
    assert await _count_group_assignments(group, role, session) == 0


async def test_revoke_a_group_assignment_at_an_unregistered_scope_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    assignment = await _add_group_assignment(group, role, session, "ghost")
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert response.status_code == 422
    assert await _count_group_assignments(group, role, session) == 1


async def test_list_group_assignments_of_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, ["role.read"]))
    await session.commit()

    assert (await client.get(_build_group_assignments_url(999999))).status_code == 404


async def test_assign_to_group_under_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_group_assignments_url(999999), json={"group_ids": [group.id], "scope": "global"}
    )

    assert response.status_code == 404


async def test_revoke_from_group_under_unknown_role_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    assert (
        await client.request("DELETE", _build_group_assignments_url(999999), json={"assignment_ids": [1]})
    ).status_code == 404


async def test_revoke_a_group_assignment_twice_returns_404_the_second_time(
    client: AsyncClient, session: AsyncSession
) -> None:
    role = await make_role(session, _uniq("role"), [])
    assignment = await _add_group_assignment(await _make_group(session), role, session)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    first = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]}
    )
    second = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert (first.status_code, second.status_code) == (204, 404)


async def test_user_assignment_id_on_the_groups_path_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    holder = await make_user(session, _uniq("target"))
    group_assignment = await _add_group_assignment(await _make_group(session), role, session)
    user_assignment = await add_role_assignment(session, holder, role, "global", None)
    assert user_assignment.id != group_assignment.id
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(user_assignment)]}
    )

    assert response.status_code == 404
    assert await _count_assignments(holder, role, session) == 1


async def test_group_assignment_id_on_the_users_path_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    holder = await make_user(session, _uniq("target"))
    user_assignment = await add_role_assignment(session, holder, role, "global", None)
    group = await _make_group(session)
    group_assignment = await _add_group_assignment(group, role, session)
    assert group_assignment.id != user_assignment.id
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(group_assignment)]}
    )

    assert response.status_code == 404
    assert await _count_group_assignments(group, role, session) == 1


async def test_role_assign_does_not_allow_group_revoke(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    assignment = await _add_group_assignment(await _make_group(session), role, session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    assert (
        await client.request(
            "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(assignment)]}
        )
    ).status_code == 403


async def test_role_revoke_does_not_allow_group_assign(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.post(_build_group_assignments_url(role), json={"group_ids": [group.id], "scope": "global"})

    assert response.status_code == 403


async def test_role_assign_held_at_another_role_does_not_allow_group_assign(
    client: AsyncClient, session: AsyncSession
) -> None:
    held = await make_role(session, _uniq("role"), [])
    other = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"], "role", str(held.id)))
    await session.commit()

    response = await client.post(_build_group_assignments_url(other), json={"group_ids": [group.id], "scope": "global"})

    assert response.status_code == 403
    assert await _count_group_assignments(group, other, session) == 0


async def test_role_revoke_held_at_another_role_does_not_allow_group_revoke(
    client: AsyncClient, session: AsyncSession
) -> None:
    held = await make_role(session, _uniq("role"), [])
    other = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    assignment = await _add_group_assignment(group, other, session)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"], "role", str(held.id)))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(other), json={"assignment_ids": [_get_id(assignment)]}
    )

    assert response.status_code == 403
    assert await _count_group_assignments(group, other, session) == 1


async def test_role_scoped_assigner_reaches_only_that_role(client: AsyncClient, session: AsyncSession) -> None:
    role_a = await make_role(session, _uniq("role"), [])
    role_b = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"], "role", str(role_a.id)))
    await session.commit()
    payload = {"user_ids": [target.id], "scope": "global"}

    assert (await client.post(_build_assignments_url(role_a), json=payload)).status_code == 201
    assert (await client.post(_build_assignments_url(role_b), json=payload)).status_code == 403


async def test_assign_role_to_several_users_in_one_request(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), ["audit.read"])
    targets = [await make_user(session, _uniq("target")) for _ in range(3)]
    ids = [_get_id(target) for target in targets]
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": ids, "scope": "global"})

    assert response.status_code == 201
    assert [row["user_id"] for row in response.json()] == ids
    for target in targets:
        assert await can(target, AUDIT_READ, GLOBAL, None, session)


async def test_assign_to_users_is_all_or_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    first = await make_user(session, _uniq("first"))
    second = await make_user(session, _uniq("second"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role), json={"user_ids": [first.id, second.id, 999999], "scope": "global"}
    )

    assert response.status_code == 404
    assert [await _count_assignments(user, role, session) for user in (first, second)] == [0, 0]
    assert "assigned" not in [e.action for e in await audit_events()]


async def test_assign_to_users_counts_a_repeated_user_once(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    first = await make_user(session, _uniq("first"))
    second = await make_user(session, _uniq("second"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role), json={"user_ids": [first.id, first.id, second.id], "scope": "global"}
    )

    assert response.status_code == 201
    assert [row["user_id"] for row in response.json()] == [first.id, second.id]
    assert [await _count_assignments(user, role, session) for user in (first, second)] == [1, 1]


async def test_assign_to_users_rejects_an_empty_list(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_assignments_url(role), json={"user_ids": [], "scope": "global"})

    assert response.status_code == 422


async def test_assign_to_users_rejects_more_than_the_limit(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_assignments_url(role), json={"user_ids": [target.id, *range(1, 101)], "scope": "global"}
    )

    assert response.status_code == 422
    assert await _count_assignments(target, role, session) == 0
    assert "assigned" not in [e.action for e in await audit_events()]


async def test_revoke_several_user_assignments_in_one_request(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    targets = [await make_user(session, _uniq("target")) for _ in range(2)]
    assignments = [await add_role_assignment(session, target, role, "global", None) for target in targets]
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(row) for row in assignments]}
    )

    assert response.status_code == 204
    assert [await _count_assignments(target, role, session) for target in targets] == [0, 0]
    assert [e.action for e in await audit_events()].count("unassigned") == 2


async def test_revoke_user_assignments_is_all_or_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    assignment = await add_role_assignment(session, target, role, "global", None)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(assignment), 999999]}
    )

    assert response.status_code == 404
    assert await _count_assignments(target, role, session) == 1
    assert "unassigned" not in [e.action for e in await audit_events()]


async def test_revoke_user_assignments_is_all_or_nothing_across_roles(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    other = await make_role(session, _uniq("role"), [])
    target = await make_user(session, _uniq("target"))
    own = await add_role_assignment(session, target, role, "global", None)
    foreign = await add_role_assignment(session, target, other, "global", None)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": [_get_id(own), _get_id(foreign)]}
    )

    assert response.status_code == 404
    assert [await _count_assignments(target, r, session) for r in (role, other)] == [1, 1]
    assert "unassigned" not in [e.action for e in await audit_events()]


async def test_revoke_user_assignments_requires_at_least_one_id(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    assert (
        await client.request("DELETE", _build_assignments_url(role), json={"assignment_ids": []})
    ).status_code == 422


async def test_revoke_user_assignments_rejects_more_than_the_limit(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_assignments_url(role), json={"assignment_ids": list(range(1, 102))}
    )

    assert response.status_code == 422


async def test_assign_role_to_several_groups_in_one_request(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), ["audit.read"])
    groups = [await _make_group(session) for _ in range(3)]
    members = [await make_user(session, _uniq("member")) for _ in groups]
    for group, member in zip(groups, members):
        await group_engine.add_group_member(_get_id(member), _get_id(group), session)
    ids = [_get_id(group) for group in groups]
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_group_assignments_url(role), json={"group_ids": ids, "scope": "global"})

    assert response.status_code == 201
    assert [row["group_id"] for row in response.json()] == ids
    for member in members:
        assert await can(member, AUDIT_READ, GLOBAL, None, session)


async def test_assign_to_groups_is_all_or_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    first = await _make_group(session)
    second = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_group_assignments_url(role),
        json={"group_ids": [first.id, second.id, 999999], "scope": "global"},
    )

    assert response.status_code == 404
    assert [await _count_group_assignments(group, role, session) for group in (first, second)] == [0, 0]
    assert "role_assigned" not in [e.action for e in await audit_events()]


async def test_assign_to_groups_counts_a_repeated_group_once(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    first = await _make_group(session)
    second = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_group_assignments_url(role),
        json={"group_ids": [first.id, first.id, second.id], "scope": "global"},
    )

    assert response.status_code == 201
    assert [row["group_id"] for row in response.json()] == [first.id, second.id]
    assert [await _count_group_assignments(group, role, session) for group in (first, second)] == [1, 1]


async def test_assign_to_groups_rejects_an_empty_list(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(_build_group_assignments_url(role), json={"group_ids": [], "scope": "global"})

    assert response.status_code == 422


async def test_assign_to_groups_rejects_more_than_the_limit(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    login_as(client, await make_user_with_permissions(session, ["role.assign"]))
    await session.commit()

    response = await client.post(
        _build_group_assignments_url(role),
        json={"group_ids": [group.id, *range(1, 101)], "scope": "global"},
    )

    assert response.status_code == 422
    assert await _count_group_assignments(group, role, session) == 0
    assert "role_assigned" not in [e.action for e in await audit_events()]


async def test_revoke_several_group_assignments_in_one_request(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    groups = [await _make_group(session) for _ in range(2)]
    assignments = [await _add_group_assignment(group, role, session) for group in groups]
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(row) for row in assignments]}
    )

    assert response.status_code == 204
    assert [await _count_group_assignments(group, role, session) for group in groups] == [0, 0]
    assert [e.action for e in await audit_events()].count("role_revoked") == 2


async def test_revoke_group_assignments_is_all_or_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    assignment = await _add_group_assignment(group, role, session)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(assignment), 999999]}
    )

    assert response.status_code == 404
    assert await _count_group_assignments(group, role, session) == 1
    assert "role_revoked" not in [e.action for e in await audit_events()]


async def test_revoke_group_assignments_is_all_or_nothing_across_roles(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    role = await make_role(session, _uniq("role"), [])
    other = await make_role(session, _uniq("role"), [])
    group = await _make_group(session)
    own = await _add_group_assignment(group, role, session)
    foreign = await _add_group_assignment(group, other, session)
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": [_get_id(own), _get_id(foreign)]}
    )

    assert response.status_code == 404
    assert [await _count_group_assignments(group, r, session) for r in (role, other)] == [1, 1]
    assert "role_revoked" not in [e.action for e in await audit_events()]


async def test_revoke_group_assignments_requires_at_least_one_id(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request("DELETE", _build_group_assignments_url(role), json={"assignment_ids": []})

    assert response.status_code == 422


async def test_revoke_group_assignments_rejects_more_than_the_limit(client: AsyncClient, session: AsyncSession) -> None:
    role = await make_role(session, _uniq("role"), [])
    login_as(client, await make_user_with_permissions(session, ["role.revoke"]))
    await session.commit()

    response = await client.request(
        "DELETE", _build_group_assignments_url(role), json={"assignment_ids": list(range(1, 102))}
    )

    assert response.status_code == 422
