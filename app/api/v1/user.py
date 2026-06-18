from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.lib.db import get_async_session
from app.lib.permissions import ROLE_ADMIN, PermissionService
from app.models.user import User
from app.schemas import User as UserSchema

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def get_user(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserSchema:
    """Return current authenticated user with is_admin derived from admin role."""
    if not current_user or not current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user authenticated.")

    result = UserSchema.model_validate(current_user)
    result.is_admin = await PermissionService(session).has_role(current_user.id, ROLE_ADMIN)
    return result
