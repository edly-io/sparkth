"""FastAPI dependencies for Google Drive route handlers.

Functions here are injected via ``Depends()`` by route handlers.
"""

from fastapi import Depends, HTTPException, status

from app.lib.auth import get_current_user
from app.lib.log import get_logger
from app.models.user import User

__all__ = [
    "require_user_id",
]

logger = get_logger(__name__)


def require_user_id(current_user: User = Depends(get_current_user)) -> int:
    """FastAPI dependency — extract and validate the current user's ID."""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    return current_user.id
