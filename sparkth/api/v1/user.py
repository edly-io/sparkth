from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import has_role
from sparkth.lib.permissions.scopes import GLOBAL
from sparkth.schemas import User as UserSchema

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def get_user(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> UserSchema:
    """Fetch the current authenticated user from the JWT token.

    ``is_admin`` is derived here from whether the user holds the global ``admin``
    role; it is not a stored column.

    Raises:
        HTTPException: If no user is authenticated.
    """
    if not current_user or not current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user authenticated.",
        )

    # "global" is the root scope; admin-ness is membership of the admin role there.
    is_admin = await has_role(current_user, "admin", GLOBAL, None, session)
    return UserSchema.model_validate(current_user).model_copy(update={"is_admin": is_admin})
