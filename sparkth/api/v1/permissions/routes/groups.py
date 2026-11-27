"""Group sub-router (mounted at ``/groups``): CRUD for user groups, their members and their roles.

Granting a role to a group is CLI-managed; the roles a group holds can be listed. The endpoints that
address one group by ``{group_id}`` (get/update/delete, the member routes and the roles list) authorize
at the ``group`` scope, so a grant can be delegated to a single group; a global grant still satisfies
them via the scope cascade. Listing members or roles needs ``group.read``. Adding members
(``POST .../members`` with ``user_ids``, 1 to 100) needs ``group.member.add`` and removing them
(``DELETE .../members?user_ids=...``, 1 to 100) needs ``group.member.remove``; each request changes every
listed user or none. Listing groups returns the groups the caller holds ``group.read`` at (every group for
a global grant); creating a group stays global.
Authored with LLM (Claude) assistance.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.permissions.constants import MAX_GROUP_MEMBER_CHANGES
from sparkth.api.v1.permissions.schemas import (
    GroupCreate,
    GroupMemberResponse,
    GroupMembersAdd,
    GroupResponse,
    GroupRoleAssignmentResponse,
    GroupUpdate,
)
from sparkth.core.models.user import User
from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.models import Group, GroupMembership, GroupRoleAssignment
from sparkth.core.permissions.roles import list_roles
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import (
    GROUP_CREATE,
    GROUP_DELETE,
    GROUP_MEMBER_ADD,
    GROUP_MEMBER_REMOVE,
    GROUP_READ,
    GROUP_UPDATE,
    object_id_str_to_int,
)
from sparkth.lib.permissions.scopes import GROUP
from sparkth.services.users.service import get_user

router = APIRouter()


def _group_to_response(group: Group) -> GroupResponse:
    """Assemble a GroupResponse, guarding the persisted-id invariant.

    A persisted/refreshed group always has an id; a real guard (not a bare ``assert``, which
    ``python -O`` strips) is what keeps the invariant enforced in optimized builds.
    """
    if group.id is None:
        raise RuntimeError(f"Group has no id: {group!r}")
    return GroupResponse(id=group.id, name=group.name, description=group.description)


def _build_group_member_response(membership: GroupMembership, user: User) -> GroupMemberResponse:
    """Assemble the response for a member from their membership and user rows, leaving the email out."""
    return GroupMemberResponse(
        user_id=membership.user_id, name=user.name, username=user.username, added_at=membership.created_at
    )


def _build_group_role_response(
    assignment: GroupRoleAssignment, group: Group, role_name: str
) -> GroupRoleAssignmentResponse:
    """Assemble the response for a group's role assignment, guarding the persisted-id invariant."""
    if assignment.id is None:
        raise RuntimeError(f"Group role assignment has no id: {assignment!r}")
    return GroupRoleAssignmentResponse(
        id=assignment.id,
        group_id=assignment.group_id,
        group_name=group.name,
        role_id=assignment.role_id,
        role_name=role_name,
        scope=assignment.scope,
        scope_object_id=assignment.scope_object_id,
        assigned_at=assignment.created_at,
    )


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    accessible_ids: set[str] | None = Depends(GROUP_READ.require_for_any_object(GROUP)),
    session: AsyncSession = Depends(get_async_session),
) -> list[GroupResponse]:
    """List the groups the caller may read. Returns a list of GroupResponse (id, name, description)."""
    groups = await group_engine.list_groups(object_id_str_to_int(accessible_ids), session)
    return [_group_to_response(group) for group in groups]


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
    dependencies=[Depends(GROUP_READ.require(GROUP, "group_id"))],
)
async def get_group(group_id: int, session: AsyncSession = Depends(get_async_session)) -> GroupResponse:
    """Fetch a group by id. Returns its GroupResponse (id, name, description)."""
    return _group_to_response(await group_engine.get_group(group_id, session))


@router.patch(
    "/{group_id}",
    response_model=GroupResponse,
    dependencies=[Depends(GROUP_UPDATE.require(GROUP, "group_id"))],
)
async def update_group(
    group_id: int, payload: GroupUpdate, session: AsyncSession = Depends(get_async_session)
) -> GroupResponse:
    """Update a group's name and/or description. Returns the updated GroupResponse."""
    return _group_to_response(await group_engine.update_group(group_id, payload.name, payload.description, session))


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(GROUP_DELETE.require(GROUP, "group_id"))],
)
async def delete_group(group_id: int, session: AsyncSession = Depends(get_async_session)) -> None:
    """Delete a group with its memberships, role assignments and scoped grants. Returns 204 No Content."""
    await group_engine.delete_group(group_id, session)


@router.get(
    "/{group_id}/members",
    response_model=list[GroupMemberResponse],
    dependencies=[Depends(GROUP_READ.require(GROUP, "group_id"))],
)
async def list_group_members(
    group_id: int, session: AsyncSession = Depends(get_async_session)
) -> list[GroupMemberResponse]:
    """List a group's active members, oldest first. Returns each member's id, name, username and join time."""
    members = await group_engine.get_group_members(group_id, session)
    return [_build_group_member_response(membership, user) for membership, user in members]


@router.post(
    "/{group_id}/members",
    response_model=list[GroupMemberResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(GROUP_MEMBER_ADD.require(GROUP, "group_id"))],
)
async def add_group_members(
    group_id: int, payload: GroupMembersAdd, session: AsyncSession = Depends(get_async_session)
) -> list[GroupMemberResponse]:
    """Add up to 100 users to a group in one request, all or nothing.

    Every user must exist and not be deleted, else the request answers 404 and changes nothing. A user who is
    already a member is returned unchanged, and an id repeated in the request counts once. Returns one
    GroupMemberResponse per distinct user, in request order.
    """
    user_ids = list(dict.fromkeys(payload.user_ids))
    # ponytail: one lookup per user, capped at 100 per request; one batched query if that ceiling rises.
    users = [await get_user(user_id, session) for user_id in user_ids]
    memberships = [await group_engine.add_group_member(user_id, group_id, session) for user_id in user_ids]
    response = [_build_group_member_response(membership, user) for membership, user in zip(memberships, users)]
    await session.commit()
    return response


@router.delete(
    "/{group_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(GROUP_MEMBER_REMOVE.require(GROUP, "group_id"))],
)
async def remove_group_members(
    group_id: int,
    user_ids: list[int] = Query(..., min_length=1, max_length=MAX_GROUP_MEMBER_CHANGES),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Take up to 100 users, given as repeated ``user_ids`` query parameters, out of a group.

    A user who is not a member is skipped. Returns 204 No Content, or 404 for an unknown group.
    """
    await group_engine.get_group(group_id, session)
    # ponytail: one removal query per user, capped at 100 per request; one batched update if that ceiling rises.
    for user_id in dict.fromkeys(user_ids):
        await group_engine.remove_group_member(user_id, group_id, session)
    await session.commit()


@router.get(
    "/{group_id}/roles",
    response_model=list[GroupRoleAssignmentResponse],
    dependencies=[Depends(GROUP_READ.require(GROUP, "group_id"))],
)
async def list_group_roles(
    group_id: int, session: AsyncSession = Depends(get_async_session)
) -> list[GroupRoleAssignmentResponse]:
    """List the roles a group holds, oldest first. Returns each assignment's role, scope and grant time."""
    group = await group_engine.get_group(group_id, session)
    assignments = await group_engine.get_group_roles(group_id, session)
    roles = await list_roles({assignment.role_id for assignment in assignments}, session)
    role_names = {role.id: role.name for role in roles}
    return [_build_group_role_response(assignment, group, role_names[assignment.role_id]) for assignment in assignments]
