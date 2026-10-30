"""Every role, role-assignment, and group change leaves an audit row in the
caller's transaction; an idempotent no-op call leaves none."""

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent
from sparkth.core.permissions import PERMISSIONS, Permission, assign_role, groups, revoke_role, roles
from sparkth.core.permissions.models import (
    Group,
    GroupMembership,
    GroupRoleAssignment,
    Role,
    RoleAssignment,
    RolePermission,
)
from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import BaseAuditEvent, RoleDeletedAuditEvent
from sparkth.lib.permissions.scopes import GLOBAL, ROLE
from sparkth.lib.testing import AuditEventsFetcher


@pytest.fixture(autouse=True)
def _register_test_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(PERMISSIONS._items, "assignment.grade", Permission("assignment.grade"))


def _assert_envelope(event: AuditEvent, event_type: str, target_type: str, target_id: object) -> None:
    category, _, action = event_type.partition(".")
    assert (event.category, event.action) == (category, action)
    assert event.outcome == "success"
    assert event.target_type == target_type
    assert event.target_id == str(target_id)


async def _role(session: AsyncSession, name: str = "grader") -> Role:
    return await roles.create_role(name, "Grades stuff", session)


async def _group(session: AsyncSession, name: str = "cs-staff") -> Group:
    return await groups.create_group(name, "CS staff", session)


async def _record_event_failing_on_role_deleted(session: AsyncSession, event: BaseAuditEvent) -> AuditEvent:
    """Delegate to the real ``record_event``, except raise for ``role.deleted`` (the last write of a delete)."""
    if isinstance(event, RoleDeletedAuditEvent):
        raise SQLAlchemyError("audit write failed")
    return await record_event(session, event)


GLOBAL_GRANT = {"role": "grader", "scope": "global", "scope_object_id": None}


class TestRoleEvents:
    async def test_create_records_created(self, session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
        role = await _role(session)

        (event,) = await audit_events()
        _assert_envelope(event, "role.created", "role", role.id)
        assert event.old_values is None
        assert event.new_values == {"name": "grader", "description": "Grades stuff"}

    async def test_update_records_before_and_after(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await roles.update_role(role.id, "marker", "Marks stuff", session)

        _, event = await audit_events()
        _assert_envelope(event, "role.updated", "role", role.id)
        assert event.old_values == {"name": "grader", "description": "Grades stuff"}
        assert event.new_values == {"name": "marker", "description": "Marks stuff"}

    async def test_update_that_changes_nothing_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await roles.update_role(role.id, None, None, session)
        await roles.update_role(role.id, "grader", "Grades stuff", session)

        assert [e.action for e in await audit_events()] == ["created"]

    async def test_delete_records_deleted(self, session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
        role = await _role(session)
        assert role.id is not None
        role_id = role.id
        await roles.delete_role(role_id, session)

        _, event = await audit_events()
        _assert_envelope(event, "role.deleted", "role", role_id)
        assert event.old_values == {"name": "grader", "description": "Grades stuff"}
        assert event.new_values is None

    async def test_delete_records_unassigned_for_active_grants_scoped_to_role(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        target = await _role(session, "target")
        manager = await _role(session, "manager")
        assert target.id is not None and manager.id is not None
        target_id = target.id
        object_id = str(target_id)
        session.add(RoleAssignment(user_id=1, role_id=manager.id, scope="role", scope_object_id=object_id))
        session.add(GroupRoleAssignment(group_id=2, role_id=manager.id, scope="role", scope_object_id=object_id))
        revoked = RoleAssignment(user_id=3, role_id=manager.id, scope="role", scope_object_id=object_id)
        revoked.soft_delete()
        session.add(revoked)
        await session.flush()
        before = len(await audit_events())
        await roles.delete_role(target_id, session)

        unassigned, group_revoked, deleted = (await audit_events())[before:]
        snapshot = {"role": "manager", "scope": "role", "scope_object_id": object_id}
        _assert_envelope(unassigned, "role.unassigned", "user", 1)
        assert unassigned.old_values == snapshot
        _assert_envelope(group_revoked, "group.role_revoked", "group", 2)
        assert group_revoked.old_values == snapshot
        _assert_envelope(deleted, "role.deleted", "role", target_id)

    async def test_delete_records_unassigned_for_active_assignments(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        group = await _group(session)
        assert role.id is not None and group.id is not None
        await assign_role(1, "grader", GLOBAL, None, session)
        await assign_role(2, "grader", GLOBAL, None, session)
        await revoke_role(2, "grader", GLOBAL, None, session)
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
        before = len(await audit_events())
        await roles.delete_role(role.id, session)

        unassigned, group_revoked, deleted = (await audit_events())[before:]
        _assert_envelope(unassigned, "role.unassigned", "user", 1)
        assert unassigned.old_values == GLOBAL_GRANT
        _assert_envelope(group_revoked, "group.role_revoked", "group", group.id)
        assert group_revoked.old_values == GLOBAL_GRANT
        _assert_envelope(deleted, "role.deleted", "role", role.id)

    async def test_delete_records_one_event_for_a_row_matching_both_cascades(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await assign_role(1, "grader", ROLE, str(role.id), session)
        before = len(await audit_events())
        await roles.delete_role(role.id, session)

        events = (await audit_events())[before:]
        assert [e.category + "." + e.action for e in events] == ["role.unassigned", "role.deleted"]

    async def test_delete_tolerates_assignments_at_unregistered_scope_kinds(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        session.add(RoleAssignment(user_id=1, role_id=role.id, scope="course", scope_object_id="5"))
        await session.flush()
        before = len(await audit_events())
        await roles.delete_role(role.id, session)

        unassigned, _ = (await audit_events())[before:]
        _assert_envelope(unassigned, "role.unassigned", "user", 1)
        assert unassigned.old_values == {"role": "grader", "scope": "course", "scope_object_id": "5"}

    async def test_delete_is_fail_closed_when_audit_write_fails(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        role = await _role(session)
        group = await _group(session)
        assert role.id is not None and group.id is not None
        role_id = role.id
        await roles.add_role_permission(role_id, "assignment.grade", session)
        await assign_role(1, "grader", GLOBAL, None, session)
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
        await session.commit()

        monkeypatch.setattr("sparkth.core.permissions.roles.record_event", _record_event_failing_on_role_deleted)
        with pytest.raises(SQLAlchemyError):
            await roles.delete_role(role_id, session)
        await session.rollback()

        assert (await session.exec(select(Role).where(Role.id == role_id))).first() is not None
        assert (await session.exec(select(RolePermission).where(RolePermission.role_id == role_id))).all() != []
        assert (await session.exec(select(RoleAssignment).where(RoleAssignment.role_id == role_id))).all() != []
        assert (
            await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.role_id == role_id))
        ).all() != []

    async def test_grant_records_permission_granted(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await roles.add_role_permission(role.id, "assignment.grade", session)

        _, event = await audit_events()
        _assert_envelope(event, "role.permission_granted", "role", role.id)
        assert event.new_values == {"permission": "assignment.grade"}

    async def test_repeated_grant_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await roles.add_role_permission(role.id, "assignment.grade", session)
        await roles.add_role_permission(role.id, "assignment.grade", session)

        assert [e.action for e in await audit_events()] == ["created", "permission_granted"]

    async def test_revoke_records_permission_revoked(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await roles.add_role_permission(role.id, "assignment.grade", session)
        await roles.remove_role_permission(role.id, "assignment.grade", session)

        event = (await audit_events())[-1]
        _assert_envelope(event, "role.permission_revoked", "role", role.id)
        assert event.old_values == {"permission": "assignment.grade"}

    async def test_revoking_an_absent_grant_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        role = await _role(session)
        assert role.id is not None
        await roles.remove_role_permission(role.id, "assignment.grade", session)

        assert [e.action for e in await audit_events()] == ["created"]


class TestRoleAssignmentEvents:
    async def test_assign_records_assigned(self, session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
        await _role(session)
        await assign_role(7, "grader", GLOBAL, None, session)

        _, event = await audit_events()
        _assert_envelope(event, "role.assigned", "user", 7)
        assert event.new_values == GLOBAL_GRANT

    async def test_repeated_assign_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        await assign_role(7, "grader", GLOBAL, None, session)
        await assign_role(7, "grader", GLOBAL, None, session)

        assert [e.action for e in await audit_events()] == ["created", "assigned"]

    async def test_revoke_records_unassigned(self, session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
        await _role(session)
        await assign_role(7, "grader", GLOBAL, None, session)
        await revoke_role(7, "grader", GLOBAL, None, session)

        event = (await audit_events())[-1]
        _assert_envelope(event, "role.unassigned", "user", 7)
        assert event.old_values == GLOBAL_GRANT

    async def test_revoking_an_absent_assignment_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        await revoke_role(7, "grader", GLOBAL, None, session)

        assert [e.action for e in await audit_events()] == ["created"]

    async def test_rollback_discards_the_revocation_and_its_record(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        await assign_role(7, "grader", GLOBAL, None, session)
        await session.commit()
        await revoke_role(7, "grader", GLOBAL, None, session)
        assert [e.action for e in await audit_events()] == ["created", "assigned", "unassigned"]
        await session.rollback()

        assert [e.action for e in await audit_events()] == ["created", "assigned"]
        assert [a.is_deleted for a in (await session.exec(select(RoleAssignment))).all()] == [False]


class TestGroupEvents:
    async def test_create_records_created(self, session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
        group = await _group(session)

        (event,) = await audit_events()
        _assert_envelope(event, "group.created", "group", group.id)
        assert event.new_values == {"name": "cs-staff", "description": "CS staff"}

    async def test_update_records_before_and_after(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        await groups.update_group(group.id, "math-staff", None, session)

        _, event = await audit_events()
        _assert_envelope(event, "group.updated", "group", group.id)
        assert event.old_values == {"name": "cs-staff", "description": "CS staff"}
        assert event.new_values == {"name": "math-staff", "description": "CS staff"}

    async def test_update_that_changes_nothing_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        await groups.update_group(group.id, None, None, session)
        await groups.update_group(group.id, "cs-staff", "CS staff", session)

        assert [e.action for e in await audit_events()] == ["created"]

    async def test_delete_records_deleted(self, session: AsyncSession, audit_events: AuditEventsFetcher) -> None:
        group = await _group(session)
        assert group.id is not None
        group_id = group.id
        await groups.delete_group(group_id, session)

        _, event = await audit_events()
        _assert_envelope(event, "group.deleted", "group", group_id)
        assert event.old_values == {"name": "cs-staff", "description": "CS staff"}

    async def test_add_member_records_member_added(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        await groups.add_group_member(7, group.id, session)

        _, event = await audit_events()
        _assert_envelope(event, "group.member_added", "group", group.id)
        assert event.new_values == {"user_id": 7}

    async def test_repeated_add_member_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        await groups.add_group_member(7, group.id, session)
        await groups.add_group_member(7, group.id, session)

        assert [e.action for e in await audit_events()] == ["created", "member_added"]

    async def test_remove_member_records_member_removed(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        await groups.add_group_member(7, group.id, session)
        await groups.remove_group_member(7, group.id, session)

        event = (await audit_events())[-1]
        _assert_envelope(event, "group.member_removed", "group", group.id)
        assert event.old_values == {"user_id": 7}

    async def test_removing_a_non_member_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        await groups.remove_group_member(7, group.id, session)

        assert [e.action for e in await audit_events()] == ["created"]

    async def test_assign_role_records_role_assigned(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        group = await _group(session)
        assert group.id is not None
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)

        event = (await audit_events())[-1]
        _assert_envelope(event, "group.role_assigned", "group", group.id)
        assert event.new_values == GLOBAL_GRANT

    async def test_repeated_assign_role_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        group = await _group(session)
        assert group.id is not None
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)

        assert [(e.category, e.action) for e in await audit_events()] == [
            ("role", "created"),
            ("group", "created"),
            ("group", "role_assigned"),
        ]

    async def test_revoke_role_records_role_revoked(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        group = await _group(session)
        assert group.id is not None
        await groups.assign_role_to_group(group.id, "grader", GLOBAL, None, session)
        await groups.revoke_role_from_group(group.id, "grader", GLOBAL, None, session)

        event = (await audit_events())[-1]
        _assert_envelope(event, "group.role_revoked", "group", group.id)
        assert event.old_values == GLOBAL_GRANT

    async def test_revoking_an_absent_group_role_records_nothing(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        await _role(session)
        group = await _group(session)
        assert group.id is not None
        await groups.revoke_role_from_group(group.id, "grader", GLOBAL, None, session)

        assert [(e.category, e.action) for e in await audit_events()] == [("role", "created"), ("group", "created")]

    async def test_rollback_discards_the_removal_and_its_record(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        group = await _group(session)
        assert group.id is not None
        group_id = group.id
        await groups.add_group_member(7, group_id, session)
        await session.commit()
        await groups.remove_group_member(7, group_id, session)
        assert [e.action for e in await audit_events()] == ["created", "member_added", "member_removed"]
        await session.rollback()

        assert [e.action for e in await audit_events()] == ["created", "member_added"]
        assert [m.is_deleted for m in (await session.exec(select(GroupMembership))).all()] == [False]
