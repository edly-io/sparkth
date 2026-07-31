"""Organizational-unit sub-router (mounted at ``/units``): CRUD + re-parenting for the organization tree.

Structure only — membership is CLI-managed. All endpoints authorize at the GLOBAL scope; a
per-unit delegation scope waits on object-bearing cascade (EPIC #420 Phase 2).
Authored with LLM (Claude) assistance.
"""

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.organization.schemas import (
    OrganizationalUnitCreate,
    OrganizationalUnitResponse,
    OrganizationalUnitUpdate,
)
from sparkth.core.organization import units as unit_engine
from sparkth.core.organization.models import OrganizationalUnit
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import (
    ORGANIZATION_UNIT_CREATE,
    ORGANIZATION_UNIT_DELETE,
    ORGANIZATION_UNIT_READ,
    ORGANIZATION_UNIT_UPDATE,
)

router = APIRouter()


def _unit_to_response(unit: OrganizationalUnit) -> OrganizationalUnitResponse:
    """Assemble an OrganizationalUnitResponse, guarding the persisted-id invariant."""
    if unit.id is None:
        raise RuntimeError(f"Organizational unit has no id: {unit!r}")
    return OrganizationalUnitResponse(
        id=unit.id, name=unit.name, kind=unit.kind, parent_id=unit.parent_id, path=unit.path
    )


@router.get(
    "",
    response_model=list[OrganizationalUnitResponse],
    dependencies=[Depends(ORGANIZATION_UNIT_READ.require_in_global_scope())],
)
async def list_organizational_units(
    session: AsyncSession = Depends(get_async_session),
) -> list[OrganizationalUnitResponse]:
    """List all organizational units (flat; clients rebuild the tree from parent_id/path)."""
    return [_unit_to_response(unit) for unit in await unit_engine.list_organizational_units(session)]


@router.post(
    "",
    response_model=OrganizationalUnitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ORGANIZATION_UNIT_CREATE.require_in_global_scope())],
)
async def create_organizational_unit(
    payload: OrganizationalUnitCreate, session: AsyncSession = Depends(get_async_session)
) -> OrganizationalUnitResponse:
    """Create an organizational unit (omit parent_id for a new root). Returns the created unit."""
    return _unit_to_response(
        await unit_engine.create_organizational_unit(payload.name, payload.kind, payload.parent_id, session)
    )


@router.get(
    "/{unit_id}",
    response_model=OrganizationalUnitResponse,
    dependencies=[Depends(ORGANIZATION_UNIT_READ.require_in_global_scope())],
)
async def get_organizational_unit(
    unit_id: int, session: AsyncSession = Depends(get_async_session)
) -> OrganizationalUnitResponse:
    """Fetch an organizational unit by id."""
    return _unit_to_response(await unit_engine.get_organizational_unit(unit_id, session))


@router.patch(
    "/{unit_id}",
    response_model=OrganizationalUnitResponse,
    dependencies=[Depends(ORGANIZATION_UNIT_UPDATE.require_in_global_scope())],
)
async def update_organizational_unit(
    unit_id: int, payload: OrganizationalUnitUpdate, session: AsyncSession = Depends(get_async_session)
) -> OrganizationalUnitResponse:
    """Rename/re-kind a unit and/or move it (a provided parent_id — null = make root — re-parents).

    Applied atomically in one transaction: validation runs against the final state (a
    combined rename+move checks the new name against the destination's siblings), and
    nothing persists if any part fails.
    """
    return _unit_to_response(
        await unit_engine.patch_organizational_unit(
            unit_id,
            payload.name,
            payload.kind,
            "parent_id" in payload.model_fields_set,
            payload.parent_id,
            session,
        )
    )


@router.delete(
    "/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ORGANIZATION_UNIT_DELETE.require_in_global_scope())],
)
async def delete_organizational_unit(unit_id: int, session: AsyncSession = Depends(get_async_session)) -> None:
    """Delete an organizational unit (refused with 409 while it has children or active members)."""
    await unit_engine.delete_organizational_unit(unit_id, session)
