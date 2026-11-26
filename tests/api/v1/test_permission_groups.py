"""Tests for the group-management API (sparkth/api/v1/permissions/routes/groups.py).
Authored with LLM (Claude) assistance."""

import uuid

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.models import Group, Role
from sparkth.lib.permissions import AUDIT_READ, can
from sparkth.lib.permissions.scopes import GLOBAL
from sparkth.lib.testing import (
    AuditEventsFetcher,
    grant_permissions,
    login_as,
    make_role,
    make_user,
    make_user_with_permissions,
)

GROUP_PERMISSIONS = ["group.create", "group.read", "group.update", "group.delete"]


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_target_group(session: AsyncSession) -> Group:
    """A plain group with an id, used as the object a per-group grant is scoped to."""
    group = Group(name=_uniq("target"))
    session.add(group)
    await session.flush()
    assert group.id is not None
    return group


async def test_create_group_returns_201(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    response = await client.post("/api/v1/permissions/groups", json={"name": "cs-staff", "description": "CS"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "cs-staff"
    assert body["description"] == "CS"


async def test_create_duplicate_group_returns_409(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})
    response = await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Group already exists: cs-staff"


async def test_list_groups_returns_them(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})
    response = await client.get("/api/v1/permissions/groups")
    assert response.status_code == 200
    assert any(g["name"] == "cs-staff" for g in response.json())


async def test_get_group_returns_it(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    response = await client.get(f"/api/v1/permissions/groups/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "cs-staff"


async def test_get_missing_group_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    response = await client.get("/api/v1/permissions/groups/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Group not found: 99999"


async def test_update_group(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    response = await client.patch(f"/api/v1/permissions/groups/{created['id']}", json={"description": "Updated"})
    assert response.status_code == 200
    assert response.json()["description"] == "Updated"


async def test_update_group_empty_body_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    # A fully-empty update would silently no-op; it must be rejected before hitting the DB.
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    assert (await client.patch(f"/api/v1/permissions/groups/{created['id']}", json={})).status_code == 422


async def test_delete_group_returns_204(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    assert (await client.delete(f"/api/v1/permissions/groups/{created['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/permissions/groups/{created['id']}")).status_code == 404


async def test_delete_group_with_active_assignment_returns_204(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, GROUP_PERMISSIONS))
    created = (await client.post("/api/v1/permissions/groups", json={"name": "cs-staff"})).json()
    role = Role(name=_uniq("granted"))
    session.add(role)
    await session.flush()
    await group_engine.assign_role_to_group(created["id"], role.name, GLOBAL, None, session)
    await session.commit()
    response = await client.delete(f"/api/v1/permissions/groups/{created['id']}")
    assert response.status_code == 204


async def test_group_endpoints_require_permission(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, []))
    assert (await client.get("/api/v1/permissions/groups")).status_code == 403
    assert (await client.post("/api/v1/permissions/groups", json={"name": "x"})).status_code == 403


# --- Per-group scoping -------------------------------------------------------------------------
# The endpoints addressing one group by {group_id} authorize at the object-bearing `group` scope, so
# a grant can be delegated to a single group. A global grant still satisfies them via the cascade
# (covered by the global-grant tests above).


async def test_group_scoped_updater_can_update_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    other = await _create_target_group(session)
    login_as(client, await make_user_with_permissions(session, ["group.update"], "group", str(target.id)))
    await session.commit()
    ok = await client.patch(f"/api/v1/permissions/groups/{target.id}", json={"description": "d"})
    assert ok.status_code == 200
    denied = await client.patch(f"/api/v1/permissions/groups/{other.id}", json={"description": "d"})
    assert denied.status_code == 403


async def test_group_scoped_reader_can_get_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    other = await _create_target_group(session)
    login_as(client, await make_user_with_permissions(session, ["group.read"], "group", str(target.id)))
    await session.commit()
    assert (await client.get(f"/api/v1/permissions/groups/{target.id}")).status_code == 200
    assert (await client.get(f"/api/v1/permissions/groups/{other.id}")).status_code == 403
    # A missing group is denied, not reported missing, so group ids cannot be probed.
    assert (await client.get("/api/v1/permissions/groups/99999")).status_code == 403


async def test_group_scoped_deleter_can_delete_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    other = await _create_target_group(session)
    login_as(client, await make_user_with_permissions(session, ["group.delete"], "group", str(target.id)))
    await session.commit()
    assert (await client.delete(f"/api/v1/permissions/groups/{other.id}")).status_code == 403
    assert (await client.delete(f"/api/v1/permissions/groups/{target.id}")).status_code == 204


async def test_group_scoped_reader_lists_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    await _create_target_group(session)
    login_as(client, await make_user_with_permissions(session, ["group.read"], "group", str(target.id)))
    await session.commit()
    response = await client.get("/api/v1/permissions/groups")
    assert response.status_code == 200
    assert [group["id"] for group in response.json()] == [target.id]


async def test_reader_at_two_groups_lists_both(client: AsyncClient, session: AsyncSession) -> None:
    first = await _create_target_group(session)
    second = await _create_target_group(session)
    await _create_target_group(session)
    user = await make_user_with_permissions(session, ["group.read"], "group", str(first.id))
    await grant_permissions(session, user, ["group.read"], "group", str(second.id))
    login_as(client, user)
    await session.commit()
    response = await client.get("/api/v1/permissions/groups")
    assert response.status_code == 200
    assert [group["id"] for group in response.json()] == [first.id, second.id]


async def test_group_reader_at_no_group_is_refused_listing(client: AsyncClient, session: AsyncSession) -> None:
    await _create_target_group(session)
    login_as(client, await make_user_with_permissions(session, ["group.update"]))
    await session.commit()
    assert (await client.get("/api/v1/permissions/groups")).status_code == 403


async def test_group_scoped_grant_does_not_authorize_creating_groups(
    client: AsyncClient, session: AsyncSession
) -> None:
    # Creating a group stays gated at the global scope; a per-group grant does not cascade UP to global.
    target = await _create_target_group(session)
    login_as(
        client,
        await make_user_with_permissions(session, ["group.create"], "group", str(target.id)),
    )
    await session.commit()
    assert (await client.post("/api/v1/permissions/groups", json={"name": _uniq("x")})).status_code == 403


# --- Members -----------------------------------------------------------------------------------


def _build_members_url(group_id: int, user_id: int | None = None) -> str:
    suffix = "" if user_id is None else f"/{user_id}"
    return f"/api/v1/permissions/groups/{group_id}/members{suffix}"


async def test_added_member_gains_and_removed_member_loses_the_group_role(
    client: AsyncClient, session: AsyncSession
) -> None:
    caller = await make_user_with_permissions(session, ["group.member.add", "group.member.remove"])
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    role = await make_role(session, _uniq("reader"), ["audit.read"])
    await group_engine.assign_role_to_group(group.id, role.name, GLOBAL, None, session)
    await session.commit()
    login_as(client, caller)

    added = await client.post(_build_members_url(group.id), json={"user_id": member.id})
    assert added.status_code == 201
    assert added.json()["user_id"] == member.id
    assert await can(member, AUDIT_READ, GLOBAL, None, session)

    removed = await client.delete(_build_members_url(group.id, member.id))
    assert removed.status_code == 204
    assert not await can(member, AUDIT_READ, GLOBAL, None, session)


async def test_list_group_members_returns_members_without_email(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["group.read"])
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    await group_engine.add_group_member(member.id, group.id, session)
    await session.commit()
    login_as(client, caller)

    response = await client.get(_build_members_url(group.id))

    assert response.status_code == 200
    (row,) = response.json()
    assert set(row) == {"user_id", "name", "username", "added_at"}
    assert (row["user_id"], row["username"]) == (member.id, member.username)


async def test_list_group_members_requires_group_read_at_that_group(client: AsyncClient, session: AsyncSession) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    other = await _create_target_group(session)
    assert other.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.read"], "group", str(other.id)))
    await session.commit()

    assert (await client.get(_build_members_url(group.id))).status_code == 403


def _build_group_roles_url(group_id: int) -> str:
    return f"/api/v1/permissions/groups/{group_id}/roles"


async def test_list_group_roles_returns_active_assignments(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["group.read"])
    group = await _create_target_group(session)
    assert group.id is not None
    grader = await make_role(session, "grader", ["audit.read"])
    revoked = await make_role(session, _uniq("revoked"), ["audit.read"])
    await group_engine.assign_role_to_group(group.id, grader.name, GLOBAL, None, session)
    await group_engine.assign_role_to_group(group.id, revoked.name, GLOBAL, None, session)
    await group_engine.revoke_role_from_group(group.id, revoked.name, GLOBAL, None, session)
    await session.commit()
    login_as(client, caller)

    response = await client.get(_build_group_roles_url(group.id))

    assert response.status_code == 200
    (row,) = response.json()
    assert (row["role_name"], row["scope"], row["scope_object_id"]) == ("grader", "global", None)
    assert (row["group_id"], row["group_name"], row["role_id"]) == (group.id, group.name, grader.id)


async def test_list_group_roles_requires_group_read_at_that_group(client: AsyncClient, session: AsyncSession) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    other = await _create_target_group(session)
    assert other.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.read"], "group", str(other.id)))
    await session.commit()

    assert (await client.get(_build_group_roles_url(group.id))).status_code == 403


async def test_list_roles_of_unknown_group_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    login_as(client, await make_user_with_permissions(session, ["group.read"]))
    await session.commit()

    assert (await client.get(_build_group_roles_url(99999))).status_code == 404


async def test_add_member_records_the_audit_event_for_the_caller(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    caller = await make_user_with_permissions(session, ["group.member.add"])
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    await session.commit()
    login_as(client, caller)

    await client.post(_build_members_url(group.id), json={"user_id": member.id})

    event = (await audit_events())[-1]
    assert (event.category, event.action, event.actor_id) == ("group", "member_added", str(caller.id))
    assert (event.target_type, event.target_id) == ("group", str(group.id))


async def test_add_existing_member_returns_201_and_records_nothing_new(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.add"]))
    await session.commit()

    first = await client.post(_build_members_url(group.id), json={"user_id": member.id})
    second = await client.post(_build_members_url(group.id), json={"user_id": member.id})

    assert (first.status_code, second.status_code) == (201, 201)
    members = await group_engine.get_group_members(group.id, session)
    assert [membership.user_id for membership, _ in members].count(member.id) == 1
    assert [e.action for e in await audit_events() if e.category == "group"].count("member_added") == 1


async def test_add_unknown_user_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.add"]))
    await session.commit()

    response = await client.post(_build_members_url(group.id), json={"user_id": 999999})

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found: 999999"
    members = await group_engine.get_group_members(group.id, session)
    assert [membership.user_id for membership, _ in members].count(999999) == 0


async def test_add_soft_deleted_user_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    gone = await make_user(session, _uniq("gone"))
    assert gone.id is not None
    gone.soft_delete()
    login_as(client, await make_user_with_permissions(session, ["group.member.add"]))
    await session.commit()

    assert (await client.post(_build_members_url(group.id), json={"user_id": gone.id})).status_code == 404
    members = await group_engine.get_group_members(group.id, session)
    assert [membership.user_id for membership, _ in members].count(gone.id) == 0


async def test_add_member_to_unknown_group_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.add"]))
    await session.commit()

    assert (await client.post(_build_members_url(99999), json={"user_id": member.id})).status_code == 404


async def test_remove_member_records_the_audit_event_for_the_caller(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    caller = await make_user_with_permissions(session, ["group.member.remove"])
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    await group_engine.add_group_member(member.id, group.id, session)
    await session.commit()
    login_as(client, caller)

    await client.delete(_build_members_url(group.id, member.id))

    event = (await audit_events())[-1]
    assert (event.category, event.action, event.actor_id) == ("group", "member_removed", str(caller.id))
    assert (event.target_type, event.target_id) == ("group", str(group.id))


async def test_remove_non_member_returns_204_and_records_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    stranger = await make_user(session, _uniq("stranger"))
    assert stranger.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.remove"]))
    await session.commit()

    response = await client.delete(_build_members_url(group.id, stranger.id))

    assert response.status_code == 204
    assert "member_removed" not in [e.action for e in await audit_events()]


async def test_remove_member_from_unknown_group_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.remove"]))
    await session.commit()

    assert (await client.delete(_build_members_url(99999, member.id))).status_code == 404


async def test_member_add_does_not_allow_remove(client: AsyncClient, session: AsyncSession) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.add"]))
    await session.commit()

    assert (await client.delete(_build_members_url(group.id, member.id))).status_code == 403


async def test_member_remove_does_not_allow_add(client: AsyncClient, session: AsyncSession) -> None:
    group = await _create_target_group(session)
    assert group.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.remove"]))
    await session.commit()

    assert (await client.post(_build_members_url(group.id), json={"user_id": member.id})).status_code == 403


async def test_group_scoped_member_manager_reaches_only_that_group(client: AsyncClient, session: AsyncSession) -> None:
    target = await _create_target_group(session)
    assert target.id is not None
    other = await _create_target_group(session)
    assert other.id is not None
    member = await make_user(session, _uniq("member"))
    assert member.id is not None
    login_as(client, await make_user_with_permissions(session, ["group.member.add"], "group", str(target.id)))
    await session.commit()

    assert (await client.post(_build_members_url(target.id), json={"user_id": member.id})).status_code == 201
    assert (await client.post(_build_members_url(other.id), json={"user_id": member.id})).status_code == 403
