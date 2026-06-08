from fastapi import Depends, HTTPException, status

from app.api.v1.auth import get_current_user
from app.models.user import User


def require_user_id(current_user: User = Depends(get_current_user)) -> int:
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    return current_user.id
