"""Role sub-router (mounted at ``/roles``): role CRUD and managing a role's permission grants.

Roles are created and edited here by end users with the ``role.*`` permissions. The endpoints that
address one role by ``{role_id}`` (get/update/delete and its permission grants) authorize at the
``role`` scope (``require(ROLE, "role_id")``), so a grant can be delegated to a single role; a
global grant still satisfies them via the scope cascade. Listing all roles and creating a role stay
global. Permissions and scopes themselves are NOT manageable through this API — they are declared in
code (platform defaults or plugin hooks); this API only assigns the already-registered permissions
to roles.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.api.v1.permissions.schemas import RoleCreate, RolePermissionAdd, RoleResponse, RoleUpdate
from sparkth.core.permissions import roles as role_engine
from sparkth.core.permissions.models import Role
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import ROLE_CREATE, ROLE_DELETE, ROLE_READ, ROLE_UPDATE
from sparkth.lib.permissions.exceptions import PermissionNotFound, RoleAlreadyExists, RoleInUse, RoleNotFound
from sparkth.lib.permissions.scopes import ROLE

router = APIRouter()


def _role_id(role: Role) -> int:
    """Return the role's primary key, raising if it is unset.

    A persisted/refreshed role always has an id; a real guard (not a bare ``assert``, which
    ``python -O`` strips) is what keeps the invariant enforced in optimized builds.
    """
    if role.id is None:
        raise RuntimeError(f"Role has no id: {role!r}")
    return role.id


def _build_role_response(role: Role, permissions: list[str]) -> RoleResponse:
    """Assemble a RoleResponse from a role and its already-fetched permission grants."""
    return RoleResponse(id=_role_id(role), name=role.name, description=role.description, permissions=permissions)


async def _role_to_response(role: Role, session: AsyncSession) -> RoleResponse:
    """Build a RoleResponse for one persisted role, fetching its permission grants."""
    permissions = await role_engine.get_role_permissions(_role_id(role), session)
    return _build_role_response(role, permissions)


@router.get(
    "",
    response_model=list[RoleResponse],
    dependencies=[Depends(ROLE_READ.require_in_global_scope())],
)
async def list_roles(session: AsyncSession = Depends(get_async_session)) -> list[RoleResponse]:
    """List all roles. Returns a list of RoleResponse (id, name, description, permissions).

    Grants are fetched for every role in a single batched query.
    """
    all_roles = await role_engine.list_roles(session)
    permissions_by_role = await role_engine.get_permissions_for_roles([_role_id(role) for role in all_roles], session)
    return [_build_role_response(role, permissions_by_role.get(_role_id(role), [])) for role in all_roles]


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ROLE_CREATE.require_in_global_scope())],
)
async def create_role(payload: RoleCreate, session: AsyncSession = Depends(get_async_session)) -> RoleResponse:
    """Create a role. Returns the created RoleResponse (id, name, description, permissions)."""
    try:
        role = await role_engine.create_role(payload.name, payload.description, session)
    except RoleAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(ROLE_READ.require(ROLE, "role_id"))],
)
async def get_role(role_id: int, session: AsyncSession = Depends(get_async_session)) -> RoleResponse:
    """Fetch a role by id. Returns its RoleResponse (id, name, description, permissions)."""
    try:
        role = await role_engine.get_role(role_id, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.patch(
    "/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(ROLE_UPDATE.require(ROLE, "role_id"))],
)
async def update_role(
    role_id: int, payload: RoleUpdate, session: AsyncSession = Depends(get_async_session)
) -> RoleResponse:
    """Update a role's name and/or description. Returns the updated RoleResponse."""
    try:
        role = await role_engine.update_role(role_id, payload.name, payload.description, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except RoleAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ROLE_DELETE.require(ROLE, "role_id"))],
)
async def delete_role(role_id: int, session: AsyncSession = Depends(get_async_session)) -> None:
    """Delete a role (refused with 409 while it still has active assignments). Returns 204 No Content."""
    try:
        await role_engine.delete_role(role_id, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except RoleInUse as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post(
    "/{role_id}/permissions",
    response_model=RoleResponse,
    dependencies=[Depends(ROLE_UPDATE.require(ROLE, "role_id"))],
)
async def create_role_permission(
    role_id: int, payload: RolePermissionAdd, session: AsyncSession = Depends(get_async_session)
) -> RoleResponse:
    """Grant a registered permission to the role (idempotent). Returns the updated RoleResponse."""
    try:
        role = await role_engine.add_role_permission(role_id, payload.permission, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except PermissionNotFound as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.delete(
    "/{role_id}/permissions/{permission}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ROLE_UPDATE.require(ROLE, "role_id"))],
)
async def delete_role_permission(
    role_id: int, permission: str, session: AsyncSession = Depends(get_async_session)
) -> None:
    """Revoke a permission from the role (idempotent). Returns 204 No Content."""
    try:
        await role_engine.remove_role_permission(role_id, permission, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
