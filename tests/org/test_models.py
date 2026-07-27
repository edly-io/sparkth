"""Tests for the org-tree table models (sparkth.core.org.models).
Authored with LLM (Claude) assistance."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.org.models import OrgMembership, OrgUnit


async def test_org_unit_round_trips(session: AsyncSession) -> None:
    unit = OrgUnit(name="University X", kind="university", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    assert unit.parent_id is None
    assert unit.kind == "university"


async def test_org_unit_child_references_parent(session: AsyncSession) -> None:
    root = OrgUnit(name="University X", path="")
    session.add(root)
    await session.flush()
    assert root.id is not None
    child = OrgUnit(name="Faculty of Science", parent_id=root.id, path="")
    session.add(child)
    await session.flush()
    assert child.parent_id == root.id


async def test_duplicate_sibling_name_is_rejected(session: AsyncSession) -> None:
    root = OrgUnit(name="University X", path="/1/")
    session.add(root)
    await session.flush()
    assert root.id is not None
    session.add(OrgUnit(name="CS Dept", parent_id=root.id, path="/1/2/"))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(OrgUnit(name="CS Dept", parent_id=root.id, path="/1/3/"))


async def test_same_name_under_different_parents_is_allowed(session: AsyncSession) -> None:
    a = OrgUnit(name="Faculty A", path="")
    b = OrgUnit(name="Faculty B", path="")
    session.add(a)
    session.add(b)
    await session.flush()
    assert a.id is not None and b.id is not None
    session.add(OrgUnit(name="CS Dept", parent_id=a.id, path=""))
    session.add(OrgUnit(name="CS Dept", parent_id=b.id, path=""))
    await session.flush()


async def test_org_membership_round_trips(session: AsyncSession) -> None:
    unit = OrgUnit(name="University X", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    membership = OrgMembership(user_id=1, org_unit_id=unit.id)
    session.add(membership)
    await session.flush()
    assert membership.id is not None
    assert membership.is_deleted is False


async def test_duplicate_active_org_membership_is_rejected(session: AsyncSession) -> None:
    unit = OrgUnit(name="University X", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    session.add(OrgMembership(user_id=1, org_unit_id=unit.id))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(OrgMembership(user_id=1, org_unit_id=unit.id))


async def test_soft_deleted_org_membership_does_not_block_readd(session: AsyncSession) -> None:
    unit = OrgUnit(name="University X", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    removed = OrgMembership(user_id=1, org_unit_id=unit.id)
    session.add(removed)
    await session.flush()
    removed.soft_delete()
    await session.flush()
    session.add(OrgMembership(user_id=1, org_unit_id=unit.id))
    await session.flush()
