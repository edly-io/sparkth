"""Tests for the organization-structure table models (sparkth.core.organization.models).
Authored with LLM (Claude) assistance."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.organization.models import OrganizationalUnit, OrganizationMembership


def test_path_index_uses_varchar_pattern_ops() -> None:
    # Postgres btree under a non-C collation cannot serve LIKE 'prefix%'; without
    # varchar_pattern_ops the descendant lookups would seq-scan in production.
    table = OrganizationalUnit.metadata.tables["organizational_unit"]
    index = next(ix for ix in table.indexes if ix.name == "ix_organizational_unit_path")
    assert index.dialect_options["postgresql"]["ops"] == {"path": "varchar_pattern_ops"}


async def test_organizational_unit_round_trips(session: AsyncSession) -> None:
    unit = OrganizationalUnit(name="University X", kind="university", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    assert unit.parent_id is None
    assert unit.kind == "university"


async def test_organizational_unit_child_references_parent(session: AsyncSession) -> None:
    root = OrganizationalUnit(name="University X", path="")
    session.add(root)
    await session.flush()
    assert root.id is not None
    child = OrganizationalUnit(name="Faculty of Science", parent_id=root.id, path="")
    session.add(child)
    await session.flush()
    assert child.parent_id == root.id


async def test_duplicate_sibling_name_is_rejected(session: AsyncSession) -> None:
    root = OrganizationalUnit(name="University X", path="/1/")
    session.add(root)
    await session.flush()
    assert root.id is not None
    session.add(OrganizationalUnit(name="CS Dept", parent_id=root.id, path="/1/2/"))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(OrganizationalUnit(name="CS Dept", parent_id=root.id, path="/1/3/"))


async def test_duplicate_root_name_is_rejected(session: AsyncSession) -> None:
    # Two roots share parent_id NULL; coalesce(parent_id, 0) in the unique index makes
    # them collide despite SQL's NULL-is-distinct semantics.
    session.add(OrganizationalUnit(name="University X", path="/1/"))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(OrganizationalUnit(name="University X", path="/2/"))


async def test_same_name_under_different_parents_is_allowed(session: AsyncSession) -> None:
    a = OrganizationalUnit(name="Faculty A", path="")
    b = OrganizationalUnit(name="Faculty B", path="")
    session.add(a)
    session.add(b)
    await session.flush()
    assert a.id is not None and b.id is not None
    session.add(OrganizationalUnit(name="CS Dept", parent_id=a.id, path=""))
    session.add(OrganizationalUnit(name="CS Dept", parent_id=b.id, path=""))
    await session.flush()


async def test_organization_membership_round_trips(session: AsyncSession) -> None:
    unit = OrganizationalUnit(name="University X", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    membership = OrganizationMembership(user_id=1, organizational_unit_id=unit.id)
    session.add(membership)
    await session.flush()
    assert membership.id is not None
    assert membership.is_deleted is False


async def test_duplicate_active_organization_membership_is_rejected(session: AsyncSession) -> None:
    unit = OrganizationalUnit(name="University X", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    session.add(OrganizationMembership(user_id=1, organizational_unit_id=unit.id))
    await session.flush()
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(OrganizationMembership(user_id=1, organizational_unit_id=unit.id))


async def test_soft_deleted_organization_membership_does_not_block_readd(session: AsyncSession) -> None:
    unit = OrganizationalUnit(name="University X", path="")
    session.add(unit)
    await session.flush()
    assert unit.id is not None
    removed = OrganizationMembership(user_id=1, organizational_unit_id=unit.id)
    session.add(removed)
    await session.flush()
    removed.soft_delete()
    await session.flush()
    session.add(OrganizationMembership(user_id=1, organizational_unit_id=unit.id))
    await session.flush()
