"""Authentication dependency for resolving the current user from a bearer token.

The single canonical home for ``get_current_user``: every caller (routes, the permission
gate, plugins, and the test harness) imports it from here. It is deliberately not
re-exported from ``sparkth.api.v1.auth`` — one object keeps FastAPI dependency overrides working.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core import security
from sparkth.lib.db import get_async_session
from sparkth.models.user import User

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    token = credentials.credentials

    try:
        payload = security.decode_access_token(token)
        username = payload.get("sub")
        if not isinstance(username, str) or username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.exec(select(User).where(User.username == username))
    user = result.one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
