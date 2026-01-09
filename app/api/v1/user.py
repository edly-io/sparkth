from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.schemas import User as UserSchema

router = APIRouter()


@router.get("/me", response_model=UserSchema)
def get_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Fetch the current authenticated user from JWT token.

     Returns:
         Current authenticated user

     Raises:
         HTTPException: If no user is authenticated
    """

    if not current_user or not current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user authenticated.",
        )

    return current_user
