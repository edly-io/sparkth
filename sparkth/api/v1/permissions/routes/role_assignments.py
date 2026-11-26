"""Role-assignment routes (mounted under ``/roles``): list, give and take away a role for users and groups.

Every route addresses one role by ``{role_id}`` and authorizes at the ``role`` scope, so a grant can be
delegated to a single role; a global grant still satisfies it via the scope cascade. Listing needs
``role.read``, giving a role ``role.assign`` and taking it away ``role.revoke``. A role is given at a
scope the caller names, and a holder of ``role.assign`` at a role may give it at any scope. An assignment
is addressed by its own id, and only an active assignment of the role in the path is found. A user
assignment and a group assignment live in separate tables, so an id is found only on its own path.
Authored with LLM (Claude) assistance.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.permissions.routes.groups import build_group_role_response
from sparkth.api.v1.permissions.schemas import (
    GroupRoleAssignmentCreate,
    GroupRoleAssignmentResponse,
    UserRoleAssignmentCreate,
    UserRoleAssignmentResponse,
)
from sparkth.core.models.user import User
from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.grants import get_role_assignment, get_user_assignments_of_role
from sparkth.core.permissions.models import RoleAssignment
from sparkth.core.permissions.roles import get_role
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import (
    ROLE_ASSIGN,
    ROLE_READ,
    ROLE_REVOKE,
    assign_role,
    get_permission_scope,
    revoke_role,
)
from sparkth.lib.permissions.exceptions import PluginNotLoaded
from sparkth.lib.permissions.scopes import PLUGIN, ROLE, PermissionScope
from sparkth.lib.plugins import get_plugin_loader
from sparkth.services.users.service import get_user

router = APIRouter()


def _resolve_grant_scope(scope: str, scope_object_id: str | None) -> PermissionScope:
    """Return the registered scope kind named ``scope``.

    Raises when the kind is unknown, and when it is ``plugin`` and ``scope_object_id`` is not the name
    of a loaded plugin. Any other kind accepts the object id as given.
    """
    permission_scope = get_permission_scope(scope)
    if permission_scope is PLUGIN and scope_object_id is not None:
        loaded = [name for name, _ in get_plugin_loader().get_loaded_plugins()]
        if scope_object_id not in loaded:
            raise PluginNotLoaded(scope_object_id)
    return permission_scope


def _build_user_assignment_response(
    assignment: RoleAssignment, user: User, role_name: str
) -> UserRoleAssignmentResponse:
    """Assemble the response for a user's role assignment, guarding the persisted-id invariant."""
    if assignment.id is None:
        raise RuntimeError(f"Role assignment has no id: {assignment!r}")
    return UserRoleAssignmentResponse(
        id=assignment.id,
        user_id=assignment.user_id,
        name=user.name,
        username=user.username,
        role_id=assignment.role_id,
        role_name=role_name,
        scope=assignment.scope,
        scope_object_id=assignment.scope_object_id,
        assigned_at=assignment.created_at,
    )


@router.get(
    "/{role_id}/assignments/users",
    response_model=list[UserRoleAssignmentResponse],
    dependencies=[Depends(ROLE_READ.require(ROLE, "role_id"))],
)
async def list_user_role_assignments(
    role_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_session),
) -> list[UserRoleAssignmentResponse]:
    """List a page of the users holding a role, by assignment id. Returns each user's scope and grant time."""
    role = await get_role(role_id, session)
    rows = await get_user_assignments_of_role(role_id, limit, offset, session)
    return [_build_user_assignment_response(assignment, user, role.name) for assignment, user in rows]


@router.post(
    "/{role_id}/assignments/users",
    response_model=UserRoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ROLE_ASSIGN.require(ROLE, "role_id"))],
)
async def assign_user_role(
    role_id: int, payload: UserRoleAssignmentCreate, session: AsyncSession = Depends(get_async_session)
) -> UserRoleAssignmentResponse:
    """Give a role to a user at a scope; an assignment that already exists is returned unchanged."""
    role = await get_role(role_id, session)
    user = await get_user(payload.user_id, session)
    permission_scope = _resolve_grant_scope(payload.scope, payload.scope_object_id)
    assignment = await assign_role(payload.user_id, role.name, permission_scope, payload.scope_object_id, session)
    response = _build_user_assignment_response(assignment, user, role.name)
    await session.commit()
    return response


@router.delete(
    "/{role_id}/assignments/users/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ROLE_REVOKE.require(ROLE, "role_id"))],
)
async def revoke_user_role(
    role_id: int, assignment_id: int, session: AsyncSession = Depends(get_async_session)
) -> None:
    """Take a role away from a user by the id of the assignment. Returns 204 No Content."""
    role = await get_role(role_id, session)
    assignment = await get_role_assignment(assignment_id, role_id, session)
    # ponytail: a row whose scope kind is no longer registered, or whose stored pairing is no longer valid,
    # cannot be revoked here (422); upgrade to a revoke that works from the row's own strings.
    permission_scope = get_permission_scope(assignment.scope)
    await revoke_role(assignment.user_id, role.name, permission_scope, assignment.scope_object_id, session)
    await session.commit()


@router.get(
    "/{role_id}/assignments/groups",
    response_model=list[GroupRoleAssignmentResponse],
    dependencies=[Depends(ROLE_READ.require(ROLE, "role_id"))],
)
async def list_group_role_assignments(
    role_id: int, session: AsyncSession = Depends(get_async_session)
) -> list[GroupRoleAssignmentResponse]:
    """List the groups holding a role, by assignment id. Returns each group's scope and grant time."""
    role = await get_role(role_id, session)
    rows = await group_engine.get_group_assignments_of_role(role_id, session)
    return [build_group_role_response(assignment, group, role.name) for assignment, group in rows]


@router.post(
    "/{role_id}/assignments/groups",
    response_model=GroupRoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ROLE_ASSIGN.require(ROLE, "role_id"))],
)
async def assign_group_role(
    role_id: int, payload: GroupRoleAssignmentCreate, session: AsyncSession = Depends(get_async_session)
) -> GroupRoleAssignmentResponse:
    """Give a role to a group at a scope; an assignment that already exists is returned unchanged."""
    role = await get_role(role_id, session)
    group = await group_engine.get_group(payload.group_id, session)
    permission_scope = _resolve_grant_scope(payload.scope, payload.scope_object_id)
    assignment = await group_engine.assign_role_to_group(
        payload.group_id, role.name, permission_scope, payload.scope_object_id, session
    )
    response = build_group_role_response(assignment, group, role.name)
    await session.commit()
    return response


@router.delete(
    "/{role_id}/assignments/groups/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ROLE_REVOKE.require(ROLE, "role_id"))],
)
async def revoke_group_role(
    role_id: int, assignment_id: int, session: AsyncSession = Depends(get_async_session)
) -> None:
    """Take a role away from a group by the id of the assignment. Returns 204 No Content."""
    role = await get_role(role_id, session)
    assignment = await group_engine.get_group_role_assignment(assignment_id, role_id, session)
    # ponytail: same ceiling as the user revoke above (422 for an unregistered scope kind or an invalid
    # stored pairing); upgrade to a revoke that works from the row's own strings.
    permission_scope = get_permission_scope(assignment.scope)
    await group_engine.revoke_role_from_group(
        assignment.group_id, role.name, permission_scope, assignment.scope_object_id, session
    )
    await session.commit()
