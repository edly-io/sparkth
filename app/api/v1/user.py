from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.models.user import User
from app.schemas import UserWithRoles
from app.services.rbac import get_user_roles

router = APIRouter()


@router.get("/me", response_model=UserWithRoles)
async def get_user(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, object]:
    """
    Fetch the current authenticated user from JWT token.

     Returns:
         Current authenticated user with roles

     Raises:
         HTTPException: If no user is authenticated
    """

    if not current_user or not current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user authenticated.",
        )

    roles = await get_user_roles(session, current_user.id)
    return {
        "id": current_user.id,
        "name": current_user.name,
        "username": current_user.username,
        "email": current_user.email,
        "roles": [r.value for r in roles],
    }
