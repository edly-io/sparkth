"""
Utility functions and dependencies for API endpoints.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select

from app.core import security
from app.core.db import get_session
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    :param credentials: HTTP Bearer token credentials
    :param session: Database session
    :return: Current user object
    :raises HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token using security module
    token = credentials.credentials
    username = security.verify_token(token)
    
    if username is None:
        raise credentials_exception
    
    # Get user from database
    user = session.exec(
        select(User).where(User.username == username)
    ).first()
    
    if user is None:
        raise credentials_exception
    
    return user
