"""Tests for the org-unit CRUD engine (sparkth.core.organization.units).
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


async def test_patch_rename_and_move_validates_against_destination(session: AsyncSession) -> None:
    # The current parent already holds the target name; the destination does not — the
    # combined rename+move must validate against the destination's siblings and succeed.
    root_a = await units.create_organizational_unit("A", None, None, session)
    root_b = await units.create_organizational_unit("B", None, None, session)
    assert root_a.id is not None and root_b.id is not None
    await units.create_organizational_unit("X", None, root_a.id, session)
    unit = await units.create_organizational_unit("Y", None, root_a.id, session)
    assert unit.id is not None

    patched = await units.patch_organizational_unit(unit.id, "X", None, True, root_b.id, session)

    assert patched.name == "X"
    assert patched.parent_id == root_b.id
    assert patched.path == f"{root_b.path}{unit.id}/"


async def test_patch_rename_away_from_destination_collision(session: AsyncSession) -> None:
    # The destination holds a sibling with the unit's CURRENT name, but the patch renames
    # away from it in the same call — validating the final state, this must succeed.
    root_a = await units.create_organizational_unit("A", None, None, session)
    root_b = await units.create_organizational_unit("B", None, None, session)
    assert root_a.id is not None and root_b.id is not None
    await units.create_organizational_unit("Y", None, root_b.id, session)
    unit = await units.create_organizational_unit("Y", None, root_a.id, session)
    assert unit.id is not None

    patched = await units.patch_organizational_unit(unit.id, "Z", None, True, root_b.id, session)

    assert patched.name == "Z"
    assert patched.parent_id == root_b.id


async def test_patch_is_atomic_when_move_fails(session: AsyncSession) -> None:
    # A failing move (cycle) must leave the rename unapplied — nothing half-commits.
    university, faculty, _ = await make_tree(session)
    assert university.id is not None and faculty.id is not None
    with pytest.raises(OrganizationCycleError):
        await units.patch_organizational_unit(university.id, "Renamed U", None, True, faculty.id, session)
    fresh = await units.get_organizational_unit(university.id, session)
    assert fresh.name == "University X"


async def test_patch_is_atomic_when_name_collides_at_destination(session: AsyncSession) -> None:
    # A failing sibling-name check must leave the kind change unapplied too.
    root_a = await units.create_organizational_unit("A", None, None, session)
    root_b = await units.create_organizational_unit("B", None, None, session)
    assert root_a.id is not None and root_b.id is not None
    await units.create_organizational_unit("X", None, root_b.id, session)
    unit = await units.create_organizational_unit("Y", None, root_a.id, session)
    assert unit.id is not None

    with pytest.raises(OrganizationalUnitAlreadyExists):
        await units.patch_organizational_unit(unit.id, "X", "department", True, root_b.id, session)

    fresh = await units.get_organizational_unit(unit.id, session)
    assert fresh.name == "Y"
    assert fresh.kind is None
    assert fresh.parent_id == root_a.id


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


def test_facade_exposes_public_surface() -> None:
    from sparkth.core.organization import memberships as core_memberships
    from sparkth.core.organization import units as core_units
    from sparkth.core.organization.exceptions import OrganizationalUnitNotFound as CoreOrganizationalUnitNotFound
    from sparkth.lib import organization as facade

    assert facade.create_organizational_unit is core_units.create_organizational_unit
    assert facade.move_organizational_unit is core_units.move_organizational_unit
    assert facade.add_organization_member is core_memberships.add_organization_member
    assert facade.OrganizationalUnitNotFound is CoreOrganizationalUnitNotFound
