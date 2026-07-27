"""Org-unit CRUD and tree maintenance (create/rename/move/delete).

Module-level async functions that commit, mirroring the role/group CRUD engines. The
``path`` column is maintained exclusively here: ``create_org_unit`` derives it from the
parent, ``move_org_unit`` rewrites the moved subtree in one UPDATE. Nothing here touches
the permission engine — the tree is inert data. Authored with LLM (Claude) assistance.
"""

from sqlalchemy import func, inspect, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.org.exceptions import (
    OrgCycleError,
    OrgUnitAlreadyExists,
    OrgUnitInUse,
    OrgUnitNotFound,
)
from sparkth.core.org.models import OrgMembership, OrgUnit


async def _ensure_sibling_name_free(
    name: str, parent_id: int | None, session: AsyncSession, exclude_id: int | None = None
) -> None:
    """Raise OrgUnitAlreadyExists if a sibling under parent_id already carries name."""
    statement = select(OrgUnit.id).where(OrgUnit.name == name, OrgUnit.parent_id == parent_id)
    if exclude_id is not None:
        statement = statement.where(OrgUnit.id != exclude_id)
    if (await session.exec(statement.limit(1))).first() is not None:
        raise OrgUnitAlreadyExists(name)


async def create_org_unit(name: str, kind: str | None, parent_id: int | None, session: AsyncSession) -> OrgUnit:
    """Create and return an org unit under parent_id (None = a new root).

    Raises OrgUnitNotFound if the parent is missing, or OrgUnitAlreadyExists if a sibling
    already carries the name. The unit's path is derived from the parent's.
    """
    parent = await get_org_unit(parent_id, session) if parent_id is not None else None
    await _ensure_sibling_name_free(name, parent_id, session)
    unit = OrgUnit(name=name, kind=kind, parent_id=parent_id, path="")
    session.add(unit)
    await session.flush()  # assigns the id the path needs
    unit.path = f"{parent.path if parent is not None else '/'}{unit.id}/"
    await session.commit()
    await session.refresh(unit)
    return unit


async def list_org_units(session: AsyncSession) -> list[OrgUnit]:
    """Return every org unit, oldest first."""
    return list((await session.exec(select(OrgUnit).order_by(col(OrgUnit.id)))).all())


async def get_org_unit(unit_id: int, session: AsyncSession) -> OrgUnit:
    """Return the org unit with unit_id, or raise OrgUnitNotFound."""
    unit = await session.get(OrgUnit, unit_id)
    if unit is None:
        raise OrgUnitNotFound(str(unit_id))
    return unit


async def update_org_unit(unit_id: int, name: str | None, kind: str | None, session: AsyncSession) -> OrgUnit:
    """Rename and/or re-kind a unit and return it (None = field unchanged).

    Raises OrgUnitNotFound if the unit is missing, or OrgUnitAlreadyExists if the new name
    collides with a sibling. Re-parenting is move_org_unit, not this.
    """
    unit = await get_org_unit(unit_id, session)
    if name is not None and name != unit.name:
        await _ensure_sibling_name_free(name, unit.parent_id, session, unit_id)
        unit.name = name
    if kind is not None:
        unit.kind = kind
    unit.update_timestamp()
    session.add(unit)
    await session.commit()
    await session.refresh(unit)
    return unit


async def move_org_unit(unit_id: int, new_parent_id: int | None, session: AsyncSession) -> OrgUnit:
    """Re-parent a unit (None = make it a root) and return it.

    Raises OrgUnitNotFound (unit or new parent missing), OrgCycleError (new parent is the
    unit itself or one of its descendants), or OrgUnitAlreadyExists (name taken among the
    new siblings). Rewrites the moved subtree's paths in a single UPDATE.
    """
    unit = await get_org_unit(unit_id, session)
    new_parent = await get_org_unit(new_parent_id, session) if new_parent_id is not None else None
    if new_parent is not None and new_parent.path.startswith(unit.path):
        raise OrgCycleError(unit_id, new_parent.id if new_parent.id is not None else -1)
    await _ensure_sibling_name_free(unit.name, new_parent_id, session, unit_id)
    old_prefix = unit.path
    new_prefix = f"{new_parent.path if new_parent is not None else '/'}{unit.id}/"
    unit.parent_id = new_parent_id
    unit.update_timestamp()
    session.add(unit)
    await session.flush()
    # One UPDATE rewrites the unit and every descendant: swap the old prefix for the new.
    # Portable: || concat and substr exist on both SQLite and PostgreSQL; the path alphabet
    # is ids and slashes, so the LIKE prefix needs no wildcard escaping.
    await session.execute(
        update(OrgUnit)
        .where(col(OrgUnit.path).startswith(old_prefix))
        .values(path=new_prefix + func.substr(OrgUnit.path, len(old_prefix) + 1))
    )
    # The UPDATE's SET clause is SQL-side (func.substr), so SQLAlchemy's automatic
    # synchronize_session="fetch" fallback (triggered because that clause isn't
    # Python-evaluable) only partially expires the `path` attribute on matched in-session
    # objects — e.g. a descendant loaded earlier in this session — rather than the whole
    # instance. A bare session.get() only re-queries when the *whole* instance is expired,
    # so a partially-expired object would be handed back unchanged, and the first plain
    # `.path` access on it would attempt an illegal sync lazy-load under AsyncSession.
    # Refresh exactly those affected objects now, inside this function, rather than
    # leaving them expired for whichever caller touches them next — identified via
    # expired_attributes so this never itself reads a possibly-expired column, and never
    # disturbing unrelated objects (like the new parent) that the rewrite didn't touch.
    # Session-wide by design: fetch-sync already limited expiry to UPDATE-touched rows, so filtering more is redundant.
    for loaded in session.identity_map.values():
        if not isinstance(loaded, OrgUnit):
            continue
        state = inspect(loaded)
        if state is not None and state.expired_attributes:
            await session.refresh(loaded)
    await session.commit()
    await session.refresh(unit)
    return unit


async def delete_org_unit(unit_id: int, session: AsyncSession) -> None:
    """Delete a unit together with its membership history.

    Raises OrgUnitNotFound if the unit is missing, or OrgUnitInUse while it still has
    children or active members — predictable, and avoids choosing a cascade policy before
    real usage exists (mirrors the delete_role posture). Historical (soft-deleted)
    membership rows are removed along with the unit.
    """
    unit = await get_org_unit(unit_id, session)
    child = (await session.exec(select(OrgUnit.id).where(OrgUnit.parent_id == unit_id).limit(1))).first()
    if child is not None:
        raise OrgUnitInUse(unit_id)
    active_member = (
        await session.exec(
            select(OrgMembership.id)
            .where(OrgMembership.org_unit_id == unit_id, OrgMembership.is_deleted == False)
            .limit(1)
        )
    ).first()
    if active_member is not None:
        raise OrgUnitInUse(unit_id)
    for membership in (await session.exec(select(OrgMembership).where(OrgMembership.org_unit_id == unit_id))).all():
        await session.delete(membership)
    await session.delete(unit)
    await session.commit()
