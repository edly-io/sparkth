"""Bearer-token authentication: the token-reading helpers and the current-user dependency.

The single canonical home for ``get_current_user``: every caller (routes, the permission
gate, plugins, and the test harness) imports it from here. It is deliberately not
re-exported from ``sparkth.api.v1.auth`` — one object keeps FastAPI dependency overrides working.

``get_current_user`` is a FastAPI dependency, so it is only available to code that runs
*inside* a route. Code that must identify the caller earlier — ``PluginAccessMiddleware``
runs before routing, so no dependency has resolved yet — composes the same two helpers this
module builds the dependency from, :func:`decode_token_username` and
:func:`get_user_by_username`, rather than decoding tokens or querying users of its own. One
implementation of "who is this request from" keeps the security gate from drifting away from
the dependency as tokens or user lookup change.
"""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core import security
from sparkth.core.models.user import User
from sparkth.lib.db import get_async_session
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

security_scheme = HTTPBearer()


def decode_token_username(token: str) -> str | None:
    """Return the username a bearer token identifies, or ``None`` if it identifies nobody.

    ``None`` covers every way a token can fail to name a user — malformed, signed with the
    wrong key, expired, or carrying no ``sub`` claim — because callers treat them alike:
    an unreadable token is an unauthenticated request. Callers decide what that means;
    this helper never raises.

    Args:
        token: The raw JWT from the ``Authorization`` header, without the ``Bearer`` prefix.
    """
    try:
        payload = security.decode_access_token(token)
    except jwt.InvalidTokenError as e:
        # Debug, not warning: expired tokens are routine (every session eventually reaches
        # this path), so logging louder would bury real failures in noise.
        logger.debug(f"Rejected an unreadable access token: {e}")
        return None

    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        return None
    return username


async def get_user_by_username(username: str, session: AsyncSession) -> User | None:
    """Return the user with this username, or ``None`` when no user has it."""
    result = await session.exec(select(User).where(User.username == username))
    return result.one_or_none()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Resolve the authenticated user, rejecting the request when the token names no one.

    Reuses the user ``PluginAccessMiddleware`` left on ``request.state`` when it has already
    resolved this request's caller, rather than decoding the same token and re-reading the
    same row. Only that gate writes the attribute, and only from this request's own token,
    so the answer is the one this dependency would have computed. Requests it never
    identified — core routes, which it does not gate — fall through to the full lookup.

    The reused instance is detached: the gate's session has closed by the time the route
    runs. That is safe because ``User`` maps only columns, which stay readable on a detached
    instance; a test in ``tests/core/plugins/test_middleware.py`` pins that, since adding a
    relationship to ``User`` is what would make this unsafe.
    """
    cached_user = getattr(request.state, "user", None)
    if isinstance(cached_user, User):
        return cached_user

    username = decode_token_username(credentials.credentials)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_username(username, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
