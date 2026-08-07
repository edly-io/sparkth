"""Organizational-unit CRUD and tree maintenance (create/rename/move/delete).

Module-level async functions that commit, mirroring the role/group CRUD engines. The
``path`` column is maintained exclusively here: ``create_organizational_unit`` derives it from the
parent, ``move_organizational_unit`` rewrites the moved subtree in one UPDATE. Nothing here touches
the permission engine — the tree is inert data. Authored with LLM (Claude) assistance.
"""

from sqlalchemy import delete, func, inspect, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.organization.exceptions import (
    OrganizationalUnitAlreadyExists,
    OrganizationalUnitInUse,
    OrganizationalUnitNotFound,
    OrganizationCycleError,
)
from sparkth.core.organization.models import OrganizationalUnit, OrganizationMembership


async def _ensure_sibling_name_free(
    name: str, parent_id: int | None, session: AsyncSession, exclude_id: int | None = None
) -> None:
    """Raise OrganizationalUnitAlreadyExists if a sibling under parent_id already carries name."""
    statement = select(OrganizationalUnit.id).where(
        OrganizationalUnit.name == name, OrganizationalUnit.parent_id == parent_id
    )
    if exclude_id is not None:
        statement = statement.where(OrganizationalUnit.id != exclude_id)
    if (await session.exec(statement.limit(1))).first() is not None:
        raise OrganizationalUnitAlreadyExists(name)


async def create_organizational_unit(
    name: str, kind: str | None, parent_id: int | None, session: AsyncSession
) -> OrganizationalUnit:
    """Create and return an organizational unit under parent_id (None = a new root).

    Raises OrganizationalUnitNotFound if the parent is missing, or OrganizationalUnitAlreadyExists if a sibling
    already carries the name. The unit's path is derived from the parent's.
    """
    parent = await get_organizational_unit(parent_id, session) if parent_id is not None else None
    await _ensure_sibling_name_free(name, parent_id, session)
    unit = OrganizationalUnit(name=name, kind=kind, parent_id=parent_id, path="")
    session.add(unit)
    await session.flush()  # assigns the id the path needs
    unit.path = f"{parent.path if parent is not None else '/'}{unit.id}/"
    await session.commit()
    await session.refresh(unit)
    return unit


async def list_organizational_units(session: AsyncSession) -> list[OrganizationalUnit]:
    """Return every organizational unit, oldest first."""
    return list((await session.exec(select(OrganizationalUnit).order_by(col(OrganizationalUnit.id)))).all())


async def get_organizational_unit(unit_id: int, session: AsyncSession) -> OrganizationalUnit:
    """Return the organizational unit with unit_id, or raise OrganizationalUnitNotFound."""
    unit = await session.get(OrganizationalUnit, unit_id)
    if unit is None:
        raise OrganizationalUnitNotFound(str(unit_id))
    return unit


async def patch_organizational_unit(
    unit_id: int,
    name: str | None,
    kind: str | None,
    move: bool,
    new_parent_id: int | None,
    session: AsyncSession,
) -> OrganizationalUnit:
    """Rename/re-kind and/or re-parent a unit in one transaction and return it.

    ``move=False`` leaves the parent alone (``new_parent_id`` is ignored); ``move=True``
    re-parents to ``new_parent_id`` (None = make it a root). Validation runs against the
    final state — the name is checked against the destination's siblings — and nothing
    commits until every check has passed, so a combined rename+move can never half-apply.
    Raises OrganizationalUnitNotFound (unit or new parent missing), OrganizationCycleError
    (new parent is the unit itself or one of its descendants), or
    OrganizationalUnitAlreadyExists (final name taken among the final siblings).
    """
    unit = await get_organizational_unit(unit_id, session)
    moving = move and new_parent_id != unit.parent_id
    new_parent: OrganizationalUnit | None = None
    if moving and new_parent_id is not None:
        new_parent = await get_organizational_unit(new_parent_id, session)
        if new_parent.path.startswith(unit.path):
            raise OrganizationCycleError(unit_id, new_parent.id if new_parent.id is not None else -1)
    final_name = name if name is not None else unit.name
    final_parent_id = new_parent_id if moving else unit.parent_id
    if final_name != unit.name or moving:
        await _ensure_sibling_name_free(final_name, final_parent_id, session, unit_id)
    if name is not None:
        unit.name = name
    if kind is not None:
        unit.kind = kind
    unit.update_timestamp()
    session.add(unit)
    if moving:
        old_prefix = unit.path
        new_prefix = f"{new_parent.path if new_parent is not None else '/'}{unit.id}/"
        unit.parent_id = new_parent_id
        await session.flush()
        # One UPDATE rewrites the unit and every descendant: swap the old prefix for the
        # new. Portable: || concat and substr exist on both SQLite and PostgreSQL; the path
        # alphabet is ids and slashes, so the LIKE prefix needs no wildcard escaping.
        await session.execute(
            update(OrganizationalUnit)
            .where(col(OrganizationalUnit.path).startswith(old_prefix))
            .values(path=new_prefix + func.substr(OrganizationalUnit.path, len(old_prefix) + 1))
        )
        # The SQL-side SET clause makes fetch-sync expire `path` on UPDATE-touched
        # in-session units; under AsyncSession the next plain attribute access on them
        # would raise (MissingGreenlet) instead of lazy-loading. Refresh exactly those
        # units here so callers never inherit expired objects. (synchronize_session=False
        # + expire_all is not equivalent: it expires everything, pushing that same failure
        # onto every caller.)
        for loaded in session.identity_map.values():
            if not isinstance(loaded, OrganizationalUnit):
                continue
            state = inspect(loaded)
            if state is not None and state.expired_attributes:
                await session.refresh(loaded)
    await session.commit()
    await session.refresh(unit)
    return unit


async def update_organizational_unit(
    unit_id: int, name: str | None, kind: str | None, session: AsyncSession
) -> OrganizationalUnit:
    """Rename and/or re-kind a unit and return it (None = field unchanged).

    Raises OrganizationalUnitNotFound if the unit is missing, or OrganizationalUnitAlreadyExists if the new name
    collides with a sibling. Re-parenting is move_organizational_unit or patch_organizational_unit, not this.
    """
    return await patch_organizational_unit(unit_id, name, kind, False, None, session)


async def move_organizational_unit(
    unit_id: int, new_parent_id: int | None, session: AsyncSession
) -> OrganizationalUnit:
    """Re-parent a unit (None = make it a root) and return it.

    Raises OrganizationalUnitNotFound (unit or new parent missing), OrganizationCycleError (new parent is the
    unit itself or one of its descendants), or OrganizationalUnitAlreadyExists (name taken among the
    new siblings). Rewrites the moved subtree's paths in a single UPDATE.
    """
    return await patch_organizational_unit(unit_id, None, None, True, new_parent_id, session)


async def delete_organizational_unit(unit_id: int, session: AsyncSession) -> None:
    """Delete a unit together with its membership history.

    Raises OrganizationalUnitNotFound if the unit is missing, or OrganizationalUnitInUse while it still has
    children or active members — predictable, and avoids choosing a cascade policy before
    real usage exists (mirrors the delete_role posture). Historical (soft-deleted)
    membership rows are removed along with the unit.
    """
    unit = await get_organizational_unit(unit_id, session)
    child = (
        await session.exec(select(OrganizationalUnit.id).where(OrganizationalUnit.parent_id == unit_id).limit(1))
    ).first()
    if child is not None:
        raise OrganizationalUnitInUse(unit_id)
    active_member = (
        await session.exec(
            select(OrganizationMembership.id)
            .where(OrganizationMembership.organizational_unit_id == unit_id, OrganizationMembership.is_deleted == False)
            .limit(1)
        )
    ).first()
    if active_member is not None:
        raise OrganizationalUnitInUse(unit_id)
    # Historical membership rows go in one bulk statement (same pattern as delete_group).
    await session.execute(
        delete(OrganizationMembership).where(col(OrganizationMembership.organizational_unit_id) == unit_id)
    )
    await session.delete(unit)
    await session.commit()
