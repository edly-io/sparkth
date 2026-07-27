"""Tests for the organizational-unit CRUD engine (sparkth.core.organization.units).
Authored with LLM (Claude) assistance."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.organization import units
from sparkth.core.organization.exceptions import (
    OrganizationalUnitAlreadyExists,
    OrganizationalUnitInUse,
    OrganizationalUnitNotFound,
    OrganizationCycleError,
)
from sparkth.core.organization.models import OrganizationalUnit, OrganizationMembership


async def make_tree(session: AsyncSession) -> tuple[OrganizationalUnit, OrganizationalUnit, OrganizationalUnit]:
    """University X → Faculty of Science → CS Dept."""
    university = await units.create_organizational_unit("University X", "university", None, session)
    assert university.id is not None
    faculty = await units.create_organizational_unit("Faculty of Science", "faculty", university.id, session)
    assert faculty.id is not None
    department = await units.create_organizational_unit("CS Dept", "department", faculty.id, session)
    return university, faculty, department


async def test_create_root_builds_path(session: AsyncSession) -> None:
    unit = await units.create_organizational_unit("University X", None, None, session)
    assert unit.id is not None
    assert unit.path == f"/{unit.id}/"


async def test_create_child_extends_parent_path(session: AsyncSession) -> None:
    university, faculty, department = await make_tree(session)
    assert faculty.path == f"{university.path}{faculty.id}/"
    assert department.path == f"{faculty.path}{department.id}/"


async def test_create_with_missing_parent_raises(session: AsyncSession) -> None:
    with pytest.raises(OrganizationalUnitNotFound):
        await units.create_organizational_unit("Orphan", None, 999, session)


async def test_create_duplicate_sibling_name_raises(session: AsyncSession) -> None:
    university = await units.create_organizational_unit("University X", None, None, session)
    assert university.id is not None
    await units.create_organizational_unit("CS Dept", None, university.id, session)
    with pytest.raises(OrganizationalUnitAlreadyExists):
        await units.create_organizational_unit("CS Dept", None, university.id, session)


async def test_create_same_name_other_parent_ok(session: AsyncSession) -> None:
    a = await units.create_organizational_unit("Faculty A", None, None, session)
    b = await units.create_organizational_unit("Faculty B", None, None, session)
    assert a.id is not None and b.id is not None
    await units.create_organizational_unit("CS Dept", None, a.id, session)
    await units.create_organizational_unit("CS Dept", None, b.id, session)


async def test_get_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(OrganizationalUnitNotFound):
        await units.get_organizational_unit(999, session)


async def test_list_returns_all(session: AsyncSession) -> None:
    await make_tree(session)
    assert len(await units.list_organizational_units(session)) == 3


async def test_update_renames_and_rekinds(session: AsyncSession) -> None:
    unit = await units.create_organizational_unit("University X", None, None, session)
    assert unit.id is not None
    updated = await units.update_organizational_unit(unit.id, "University Y", "university", session)
    assert updated.name == "University Y"
    assert updated.kind == "university"


async def test_update_duplicate_sibling_name_raises(session: AsyncSession) -> None:
    root = await units.create_organizational_unit("University X", None, None, session)
    assert root.id is not None
    await units.create_organizational_unit("Physics", None, root.id, session)
    chemistry = await units.create_organizational_unit("Chemistry", None, root.id, session)
    assert chemistry.id is not None
    with pytest.raises(OrganizationalUnitAlreadyExists):
        await units.update_organizational_unit(chemistry.id, "Physics", None, session)


async def test_move_rewrites_subtree_paths(session: AsyncSession) -> None:
    university, faculty, department = await make_tree(session)
    other = await units.create_organizational_unit("University Z", None, None, session)
    assert faculty.id is not None and other.id is not None and department.id is not None
    moved = await units.move_organizational_unit(faculty.id, other.id, session)
    assert moved.parent_id == other.id
    assert moved.path == f"{other.path}{faculty.id}/"
    refreshed_department = await units.get_organizational_unit(department.id, session)
    assert refreshed_department.path == f"{moved.path}{department.id}/"


async def test_move_to_root(session: AsyncSession) -> None:
    university, faculty, _ = await make_tree(session)
    assert faculty.id is not None
    moved = await units.move_organizational_unit(faculty.id, None, session)
    assert moved.parent_id is None
    assert moved.path == f"/{faculty.id}/"


async def test_move_under_own_descendant_raises(session: AsyncSession) -> None:
    university, faculty, department = await make_tree(session)
    assert university.id is not None and department.id is not None
    with pytest.raises(OrganizationCycleError):
        await units.move_organizational_unit(university.id, department.id, session)


async def test_move_under_self_raises(session: AsyncSession) -> None:
    unit = await units.create_organizational_unit("University X", None, None, session)
    assert unit.id is not None
    with pytest.raises(OrganizationCycleError):
        await units.move_organizational_unit(unit.id, unit.id, session)


async def test_move_name_collision_at_new_parent_raises(session: AsyncSession) -> None:
    a = await units.create_organizational_unit("Faculty A", None, None, session)
    b = await units.create_organizational_unit("Faculty B", None, None, session)
    assert a.id is not None and b.id is not None
    await units.create_organizational_unit("CS Dept", None, a.id, session)
    moving = await units.create_organizational_unit("CS Dept", None, b.id, session)
    assert moving.id is not None
    with pytest.raises(OrganizationalUnitAlreadyExists):
        await units.move_organizational_unit(moving.id, a.id, session)


async def test_delete_leaf_removes_it(session: AsyncSession) -> None:
    _, _, department = await make_tree(session)
    assert department.id is not None
    await units.delete_organizational_unit(department.id, session)
    with pytest.raises(OrganizationalUnitNotFound):
        await units.get_organizational_unit(department.id, session)


async def test_delete_with_children_raises(session: AsyncSession) -> None:
    university, _, _ = await make_tree(session)
    assert university.id is not None
    with pytest.raises(OrganizationalUnitInUse):
        await units.delete_organizational_unit(university.id, session)


async def test_delete_with_active_member_raises(session: AsyncSession) -> None:
    unit = await units.create_organizational_unit("University X", None, None, session)
    assert unit.id is not None
    session.add(OrganizationMembership(user_id=1, organizational_unit_id=unit.id))
    await session.flush()
    with pytest.raises(OrganizationalUnitInUse):
        await units.delete_organizational_unit(unit.id, session)


async def test_delete_removes_membership_history(session: AsyncSession) -> None:
    unit = await units.create_organizational_unit("University X", None, None, session)
    assert unit.id is not None
    membership = OrganizationMembership(user_id=1, organizational_unit_id=unit.id)
    session.add(membership)
    await session.flush()
    membership.soft_delete()
    await session.flush()
    await units.delete_organizational_unit(unit.id, session)
    rows = (
        await session.exec(
            select(OrganizationMembership).where(OrganizationMembership.organizational_unit_id == unit.id)
        )
    ).all()
    assert rows == []


async def test_delete_missing_raises(session: AsyncSession) -> None:
    with pytest.raises(OrganizationalUnitNotFound):
        await units.delete_organizational_unit(999, session)
