from fastapi import Depends, HTTPException, status

from sparkth.lib.auth import get_current_user
from sparkth.lib.models import User


def require_user_id(current_user: User = Depends(get_current_user)) -> int:
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    return current_user.id
