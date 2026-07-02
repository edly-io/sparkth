"""Role-management API: role CRUD and managing a role's permission grants.

Roles are created and edited here by end users with the ``role.*`` permissions.
Permissions and scopes themselves are NOT manageable through this API — they are
declared in code (platform defaults or plugin hooks); this API only assigns the
already-registered permissions to roles.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.permissions.schemas import RoleCreate, RolePermissionAdd, RoleResponse, RoleUpdate
from app.core.permissions.exceptions import PermissionNotFound, RoleAlreadyExists, RoleInUse, RoleNotFound
from app.core.permissions.models import Role
from app.core.permissions.roles import (
    add_role_permission,
    available_permissions,
    create_role,
    delete_role,
    get_role,
    get_role_permissions,
    list_roles,
    remove_role_permission,
    update_role,
)
from app.lib.db import get_async_session
from app.lib.permissions import ROLE_CREATE, ROLE_DELETE, ROLE_READ, ROLE_UPDATE

router = APIRouter()


async def _role_to_response(role: Role, session: AsyncSession) -> RoleResponse:
    """Build a RoleResponse for a persisted role, attaching its permission grants."""
    assert role.id is not None
    permissions = await get_role_permissions(role.id, session)
    return RoleResponse(id=role.id, name=role.name, description=role.description, permissions=permissions)


@router.get(
    "/available",
    response_model=list[str],
    dependencies=[Depends(ROLE_READ.require_in_global_scope())],
)
async def list_available_permissions() -> list[str]:
    """List the permissions assignable to a role. Returns a list of permission strings."""
    return available_permissions()


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    dependencies=[Depends(ROLE_READ.require_in_global_scope())],
)
async def list_all_roles(session: AsyncSession = Depends(get_async_session)) -> list[RoleResponse]:
    """List all roles. Returns a list of RoleResponse (id, name, description, permissions)."""
    return [await _role_to_response(role, session) for role in await list_roles(session)]


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ROLE_CREATE.require_in_global_scope())],
)
async def create_new_role(payload: RoleCreate, session: AsyncSession = Depends(get_async_session)) -> RoleResponse:
    """Create a role. Returns the created RoleResponse (id, name, description, permissions)."""
    try:
        role = await create_role(payload.name, payload.description, session)
    except RoleAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(ROLE_READ.require_in_global_scope())],
)
async def get_one_role(role_id: int, session: AsyncSession = Depends(get_async_session)) -> RoleResponse:
    """Fetch a role by id. Returns its RoleResponse (id, name, description, permissions)."""
    try:
        role = await get_role(role_id, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.patch(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(ROLE_UPDATE.require_in_global_scope())],
)
async def update_existing_role(
    role_id: int, payload: RoleUpdate, session: AsyncSession = Depends(get_async_session)
) -> RoleResponse:
    """Update a role's name and/or description. Returns the updated RoleResponse."""
    try:
        role = await update_role(role_id, payload.name, payload.description, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except RoleAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return await _role_to_response(role, session)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ROLE_DELETE.require_in_global_scope())],
)
async def delete_existing_role(role_id: int, session: AsyncSession = Depends(get_async_session)) -> None:
    """Delete a role (refused with 409 while it still has active assignments). Returns 204 No Content."""
    try:
        await delete_role(role_id, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except RoleInUse as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post(
    "/roles/{role_id}/permissions",
    response_model=RoleResponse,
    dependencies=[Depends(ROLE_UPDATE.require_in_global_scope())],
)
async def grant_role_permission(
    role_id: int, payload: RolePermissionAdd, session: AsyncSession = Depends(get_async_session)
) -> RoleResponse:
    """Grant a registered permission to the role (idempotent). Returns the updated RoleResponse."""
    try:
        await add_role_permission(role_id, payload.permission, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except PermissionNotFound as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    return await _role_to_response(await get_role(role_id, session), session)


@router.delete(
    "/roles/{role_id}/permissions/{permission}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ROLE_UPDATE.require_in_global_scope())],
)
async def revoke_role_permission(
    role_id: int, permission: str, session: AsyncSession = Depends(get_async_session)
) -> None:
    """Revoke a permission from the role (idempotent). Returns 204 No Content."""
    try:
        await remove_role_permission(role_id, permission, session)
    except RoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
