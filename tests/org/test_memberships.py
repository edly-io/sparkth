"""Tests for org membership management (sparkth.core.org.memberships).
Authored with LLM (Claude) assistance."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.org import memberships, units
from sparkth.core.org.exceptions import OrgUnitNotFound
from sparkth.core.org.models import OrgMembership


async def make_user(session: AsyncSession, username: str) -> User:
    user = User(name="T", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    return user


async def test_add_member_is_idempotent(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    unit = await units.create_org_unit("CS Dept", None, None, session)
    assert user.id is not None and unit.id is not None
    first = await memberships.add_org_member(user.id, unit.id, session)
    second = await memberships.add_org_member(user.id, unit.id, session)
    assert first.id == second.id


async def test_add_member_missing_unit_raises(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    with pytest.raises(OrgUnitNotFound):
        await memberships.add_org_member(user.id, 999, session)


async def test_remove_member_soft_deletes(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    unit = await units.create_org_unit("CS Dept", None, None, session)
    assert user.id is not None and unit.id is not None
    await memberships.add_org_member(user.id, unit.id, session)
    await memberships.remove_org_member(user.id, unit.id, session)
    assert await memberships.get_org_members(unit.id, session) == []
    rows = (await session.exec(select(OrgMembership).where(OrgMembership.org_unit_id == unit.id))).all()
    assert len(rows) == 1 and rows[0].is_deleted is True


async def test_remove_member_noop_when_absent(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    unit = await units.create_org_unit("CS Dept", None, None, session)
    assert user.id is not None and unit.id is not None
    await memberships.remove_org_member(user.id, unit.id, session)


async def test_get_members_lists_active(session: AsyncSession) -> None:
    alice = await make_user(session, "alice")
    bob = await make_user(session, "bob")
    unit = await units.create_org_unit("CS Dept", None, None, session)
    assert alice.id is not None and bob.id is not None and unit.id is not None
    await memberships.add_org_member(alice.id, unit.id, session)
    await memberships.add_org_member(bob.id, unit.id, session)
    assert sorted(await memberships.get_org_members(unit.id, session)) == sorted([alice.id, bob.id])


async def test_membership_is_not_inherited_by_descendants(session: AsyncSession) -> None:
    # Membership in a unit is NOT membership in its children — the rule layer decides that later.
    user = await make_user(session, "alice")
    parent = await units.create_org_unit("Faculty", None, None, session)
    assert parent.id is not None
    child = await units.create_org_unit("CS Dept", None, parent.id, session)
    assert user.id is not None and child.id is not None
    await memberships.add_org_member(user.id, parent.id, session)
    assert await memberships.get_org_members(child.id, session) == []
