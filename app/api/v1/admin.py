from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.dependencies import require_permission
from app.core.db import get_async_session
from app.models.rbac import RoleName
from app.models.user import User
from app.schemas import AdminUserList, AssignRoleRequest, UserWithRoles
from app.services.rbac import assign_role, get_user_roles

router = APIRouter(tags=["Admin"])


@router.get("/users", response_model=AdminUserList)
async def list_users(
    _admin: User = Depends(require_permission("users:list")),
    session: AsyncSession = Depends(get_async_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    """List all users with pagination. Requires users:list permission."""
    count_result = await session.exec(
        select(func.count()).select_from(User).where(User.is_deleted == False)  # noqa: E712
    )
    total = count_result.one()

    offset = (page - 1) * page_size
    result = await session.exec(
        select(User)
        .where(User.is_deleted == False)  # noqa: E712
        .order_by(User.id)  # type: ignore[arg-type]
        .offset(offset)
        .limit(page_size)
    )
    users = result.all()

    users_with_roles: list[dict[str, object]] = []
    for user in users:
        roles = await get_user_roles(session, user.id) if user.id else []
        users_with_roles.append(
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "email": user.email,
                "roles": [r.value for r in roles],
            }
        )

    return {
        "users": users_with_roles,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/users/{user_id}", response_model=UserWithRoles)
async def get_user_detail(
    user_id: int,
    _admin: User = Depends(require_permission("users:read")),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """Get user detail with roles. Requires users:read permission."""
    result = await session.exec(select(User).where(User.id == user_id, User.is_deleted == False))  # noqa: E712
    user = result.one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    roles = await get_user_roles(session, user_id)
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "roles": [r.value for r in roles],
    }


@router.patch("/users/{user_id}/roles", response_model=UserWithRoles)
async def assign_user_role(
    user_id: int,
    body: AssignRoleRequest,
    _admin: User = Depends(require_permission("users:assign_role")),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """Assign a role to a user. Requires users:assign_role permission."""
    try:
        role = RoleName(body.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid role: {body.role}. Valid roles: {[r.value for r in RoleName]}",
        )

    result = await session.exec(select(User).where(User.id == user_id, User.is_deleted == False))  # noqa: E712
    user = result.one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await assign_role(session, user_id, role)
    await session.flush()

    roles = await get_user_roles(session, user_id)
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "roles": [r.value for r in roles],
    }


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    _admin: User = Depends(require_permission("users:manage")),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    """Soft-delete a user. Requires users:manage permission."""
    result = await session.exec(select(User).where(User.id == user_id, User.is_deleted == False))  # noqa: E712
    user = result.one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.soft_delete()
    session.add(user)
    await session.flush()

    return {"detail": "User deactivated"}
