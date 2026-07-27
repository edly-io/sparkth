"""User ↔ organizational-unit membership management.

Module-level async functions that flush (callers own the transaction boundary), mirroring
the group-membership engine. Membership is HR truth: it grants nothing, and sitting in a
unit does not imply sitting in its ancestors or descendants.
Authored with LLM (Claude) assistance.
"""

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.organization.models import OrganizationMembership
from sparkth.core.organization.units import get_organizational_unit


async def _find_active_membership(
    user_id: int, organizational_unit_id: int, session: AsyncSession
) -> OrganizationMembership | None:
    """Return the user's active membership row in the unit, or None."""
    statement = (
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organizational_unit_id == organizational_unit_id,
            OrganizationMembership.is_deleted == False,
        )
        .limit(1)
    )
    return (await session.exec(statement)).first()


async def add_organization_member(
    user_id: int, organizational_unit_id: int, session: AsyncSession
) -> OrganizationMembership:
    """Return the user's active membership in the unit, creating it if absent.

    Idempotent and race-safe under the same savepoint pattern as the role/group engines.
    Raises OrganizationalUnitNotFound.
    """
    await get_organizational_unit(organizational_unit_id, session)
    existing = await _find_active_membership(user_id, organizational_unit_id, session)
    if existing is not None:
        return existing
    try:
        # Insert inside a savepoint so a unique-index violation rolls back cleanly without
        # poisoning the surrounding transaction.
        async with session.begin_nested():
            membership = OrganizationMembership(user_id=user_id, organizational_unit_id=organizational_unit_id)
            session.add(membership)
            await session.flush()
        return membership
    except IntegrityError:
        # A concurrent add inserted the same (user, unit) after our check; return that
        # winner to stay idempotent, re-raise if it's somehow still not visible.
        winner = await _find_active_membership(user_id, organizational_unit_id, session)
        if winner is None:
            raise
        return winner


async def remove_organization_member(user_id: int, organizational_unit_id: int, session: AsyncSession) -> None:
    """Soft-delete the user's active memberships in the unit (a no-op when there are none)."""
    statement = select(OrganizationMembership).where(
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.organizational_unit_id == organizational_unit_id,
        OrganizationMembership.is_deleted == False,
    )
    for membership in (await session.exec(statement)).all():
        membership.soft_delete()
    await session.flush()


async def get_organization_members(organizational_unit_id: int, session: AsyncSession) -> list[int]:
    """Return the user ids of the unit's active members. Raises OrganizationalUnitNotFound."""
    await get_organizational_unit(organizational_unit_id, session)
    result = await session.exec(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organizational_unit_id == organizational_unit_id,
            OrganizationMembership.is_deleted == False,
        )
    )
    return list(result.all())
