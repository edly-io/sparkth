"""Group sub-router (mounted at ``/groups``): CRUD for user groups (issue #519).

Structural definition only — membership and group-role grants are CLI-managed, mirroring
how user-role assignment is CLI-only. All endpoints authorize at the GLOBAL scope; a
per-group delegation scope is deferred until object-bearing scope cascade exists
(EPIC #420 Phase 2). Authored with LLM (Claude) assistance.
"""

from fastapi import APIRouter, Depends, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.permissions.schemas import GroupCreate, GroupResponse, GroupUpdate
from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.models import Group
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import GROUP_CREATE, GROUP_DELETE, GROUP_READ, GROUP_UPDATE

router = APIRouter()


def _group_to_response(group: Group) -> GroupResponse:
    """Assemble a GroupResponse, guarding the persisted-id invariant.

    A persisted/refreshed group always has an id; a real guard (not a bare ``assert``, which
    ``python -O`` strips) is what keeps the invariant enforced in optimized builds.
    """
    if group.id is None:
        raise RuntimeError(f"Group has no id: {group!r}")
    return GroupResponse(id=group.id, name=group.name, description=group.description)


@router.get(
    "",
    response_model=list[GroupResponse],
    dependencies=[Depends(GROUP_READ.require_in_global_scope())],
)
async def list_groups(session: AsyncSession = Depends(get_async_session)) -> list[GroupResponse]:
    """List all groups. Returns a list of GroupResponse (id, name, description)."""
    return [_group_to_response(group) for group in await group_engine.list_groups(session)]


@router.post(
    "",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(GROUP_CREATE.require_in_global_scope())],
)
async def create_group(payload: GroupCreate, session: AsyncSession = Depends(get_async_session)) -> GroupResponse:
    """Create a group. Returns the created GroupResponse (id, name, description)."""
    return _group_to_response(await group_engine.create_group(payload.name, payload.description, session))


@router.get(
    "/{group_id}",
    response_model=GroupResponse,
    dependencies=[Depends(GROUP_READ.require_in_global_scope())],
)
async def get_group(group_id: int, session: AsyncSession = Depends(get_async_session)) -> GroupResponse:
    """Fetch a group by id. Returns its GroupResponse (id, name, description)."""
    return _group_to_response(await group_engine.get_group(group_id, session))


@router.patch(
    "/{group_id}",
    response_model=GroupResponse,
    dependencies=[Depends(GROUP_UPDATE.require_in_global_scope())],
)
async def update_group(
    group_id: int, payload: GroupUpdate, session: AsyncSession = Depends(get_async_session)
) -> GroupResponse:
    """Update a group's name and/or description. Returns the updated GroupResponse."""
    return _group_to_response(await group_engine.update_group(group_id, payload.name, payload.description, session))


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(GROUP_DELETE.require_in_global_scope())],
)
async def delete_group(group_id: int, session: AsyncSession = Depends(get_async_session)) -> None:
    """Delete a group (refused with 409 while it has active role assignments). Returns 204 No Content."""
    await group_engine.delete_group(group_id, session)
