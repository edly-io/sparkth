"""Tests for the group tables and the group engine functions
(sparkth.core.permissions.groups). Authored with LLM (Claude) assistance."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.models import Group, GroupMembership, GroupRoleAssignment
from sparkth.lib.permissions.scopes import GLOBAL


async def test_group_round_trips(session: AsyncSession) -> None:
    group = Group(name="cs-staff", description="CS department staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    assert group.name == "cs-staff"
    assert group.description == "CS department staff"


async def test_group_membership_round_trips_with_manual_source(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None

    membership = GroupMembership(user_id=1, group_id=group.id)
    session.add(membership)
    await session.flush()
    assert membership.id is not None
    assert membership.source == "manual"
    assert membership.is_deleted is False


async def test_duplicate_active_membership_is_rejected(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    session.add(GroupMembership(user_id=1, group_id=group.id))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(GroupMembership(user_id=1, group_id=group.id))


async def test_soft_deleted_membership_does_not_block_readd(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    removed = GroupMembership(user_id=1, group_id=group.id)
    session.add(removed)
    await session.flush()
    removed.soft_delete()
    await session.flush()
    session.add(GroupMembership(user_id=1, group_id=group.id))
    await session.flush()


async def test_group_role_assignment_round_trips(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    assignment = GroupRoleAssignment(group_id=group.id, role_id=1, scope=GLOBAL.name, scope_object_id=None)
    session.add(assignment)
    await session.flush()
    assert assignment.id is not None
    assert assignment.is_deleted is False


async def test_duplicate_active_group_assignment_is_rejected(session: AsyncSession) -> None:
    group = Group(name="cs-staff")
    session.add(group)
    await session.flush()
    assert group.id is not None
    session.add(GroupRoleAssignment(group_id=group.id, role_id=1, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(GroupRoleAssignment(group_id=group.id, role_id=1, scope=GLOBAL.name, scope_object_id=None))
