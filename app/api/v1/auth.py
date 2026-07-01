import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.google_auth import (
    exchange_auth_code,
    generate_google_login_url,
    get_google_user_info,
)
from app.lib.analytics import UnknownEventTypeError, ingest_event

# Re-exported from its new home in app.lib.auth (same object) so existing importers and the
# test harness's dependency_overrides keep working unchanged.
from app.lib.auth import get_current_user as get_current_user
from app.lib.db import analytics_session_scope, get_async_session
from app.lib.log import get_logger
from app.lib.permissions import Permission, can
from app.lib.permissions.scopes import PermissionScope
from app.models.base import utc_now
from app.models.user import User
from app.schemas import (
    GoogleAuthUrl,
    ResendVerificationRequest,
    Token,
    UserCreate,
    UserLogin,
    VerifyEmailRequest,
)
from app.schemas import User as UserSchema
from app.services.email_verification import (
    EmailVerificationService,
    TokenExpiredError,
    TokenInvalidError,
    send_verification_email,
)
from app.services.whitelist import WhitelistService

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter()


@router.post("/register", response_model=UserSchema)
async def register_user(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> User:
    if not settings.REGISTRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Registration is currently disabled")

    normalized_email = user.email.strip().lower()
    if not await WhitelistService.is_email_allowed(session, normalized_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email address is not authorized to register. Contact an administrator.",
        )
    result = await session.exec(select(User).where(User.username == user.username))
    db_user = result.one_or_none()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    result = await session.exec(select(User).where(User.email == normalized_email))
    db_user_email = result.one_or_none()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = security.get_password_hash(user.password)
    db_user = User(
        name=user.name,
        username=user.username,
        email=normalized_email,
        hashed_password=hashed_password,
    )
    session.add(db_user)
    await session.flush()

    if db_user.id is None:
        raise RuntimeError("user.id unexpectedly None after flush")
    raw_token = await EmailVerificationService.create_token(session, user_id=db_user.id)
    await session.commit()
    await session.refresh(db_user)

    background_tasks.add_task(
        send_verification_email,
        to=db_user.email,
        name=db_user.name,
        raw_token=raw_token,
    )
    return db_user


async def _emit_login_event(username: str, user_id: str | None) -> None:
    """Emit a user.logged_in analytics event as a background task.

    Runs after the login response has been sent. Must not raise — any exception
    that escapes a background task propagates through Starlette's middleware in
    ASGI test transports and would break tests even though production handles it
    transparently. Known analytics failures are logged at WARNING; anything
    unexpected is logged at ERROR. Either way the login outcome is unaffected.
    """
    try:
        async with analytics_session_scope() as analytics_session:
            await ingest_event(
                analytics_session,
                "user.logged_in",
                1,
                {"username": username},
                actor_id=user_id,
            )
    except (UnknownEventTypeError, ValidationError, SQLAlchemyError) as exc:
        logger.warning("Failed to emit user.logged_in analytics event: %s", exc)
    except Exception as exc:
        # Broad catch required: any unhandled exception in a background task
        # propagates through the Starlette ASGI middleware stack. Log at ERROR
        # so unexpected failures are visible, but never let them surface to callers.
        logger.error("Unexpected error emitting user.logged_in analytics event: %s", exc, exc_info=True)


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: UserLogin,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str | datetime]:
    result = await session.exec(select(User).where(User.username == form_data.username))
    user = result.one_or_none()

    # Check if user exists and has a password set (Google-only users won't have one)
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "email_not_verified", "email": user.email},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expires_at = utc_now() + access_token_expires

    access_token = security.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

    background_tasks.add_task(
        _emit_login_event,
        username=user.username,
        user_id=str(user.id) if user.id is not None else None,
    )

    return {"access_token": access_token, "token_type": "bearer", "expires_at": expires_at}


@router.get("/google/authorize", response_model=GoogleAuthUrl)
async def google_authorize() -> dict[str, str]:
    """Get Google OAuth authorization URL."""
    try:
        url = generate_google_login_url()
        return {"url": url}
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    session: AsyncSession = Depends(get_async_session),
) -> RedirectResponse:
    """
    Handle Google OAuth callback.

    This endpoint:
    1. Exchanges the authorization code for tokens
    2. Fetches user info from Google
    3. Creates or links the user account
    4. Redirects to frontend with JWT token
    """
    try:
        # Exchange code for tokens
        token_data = await exchange_auth_code(code)
        access_token = token_data["access_token"]

        # Get user info from Google
        google_user = await get_google_user_info(access_token)
        google_id = google_user["id"]
        email = google_user["email"].strip().lower()
        name = google_user.get("name", email.split("@")[0])

        # Try to find existing user by google_id
        result = await session.exec(select(User).where(User.google_id == google_id))
        user = result.one_or_none()

        if not user:
            # Try to find by email and link Google account
            result = await session.exec(select(User).where(User.email == email))
            user = result.one_or_none()

            if user:
                # Link Google ID to existing account
                user.google_id = google_id
                if not user.email_verified:
                    user.email_verified = True
                    user.email_verified_at = utc_now()
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
                # Check whitelist before creating new user
                if not await WhitelistService.is_email_allowed(session, email):
                    return RedirectResponse(url="/login?error=email_not_whitelisted", status_code=302)

                # Create new user with username from email prefix
                base_username = email.split("@")[0][:20]
                username = base_username

                # Check if username exists, add random suffix if needed
                result = await session.exec(select(User).where(User.username == username))
                if result.one_or_none():
                    import secrets

                    suffix = secrets.token_hex(3)  # 6 char hex string
                    username = f"{base_username[:13]}{suffix}"

                user = User(
                    name=name[:30],  # Limit name to field max length
                    username=username[:20],  # Limit username to field max length
                    email=email,
                    google_id=google_id,
                    hashed_password=None,
                    email_verified=True,
                    email_verified_at=utc_now(),
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

        # Generate JWT token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_at = utc_now() + access_token_expires

        jwt_token = security.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

        # Redirect to frontend callback page with token
        redirect_url = f"/login/callback?token={jwt_token}&expires_at={expires_at.isoformat()}"
        return RedirectResponse(url=redirect_url, status_code=302)

    except ValueError as e:
        # Redirect to login page with error
        return RedirectResponse(url=f"/login?error={quote(str(e))}", status_code=302)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    # Unauthenticated endpoint: deliberately returns no body so we don't leak
    # account state (verified flag, id, name) to anyone holding a token.
    try:
        await EmailVerificationService.verify_token(session, raw_token=body.token)
    except TokenExpiredError:
        raise HTTPException(status_code=400, detail="expired_token")
    except TokenInvalidError:
        raise HTTPException(status_code=400, detail="invalid_token")
    await session.commit()


@asynccontextmanager
async def _get_resend_redis() -> AsyncIterator[Any]:
    """Yield a Redis client for the resend cooldown; close on exit.

    The endpoint is rate-limited to roughly one request per email per
    cooldown window, so per-request client + pool setup is acceptable
    and avoids any shared mutable state. Not routed through `CacheService` —
    that wraps a different API (string get/set with default ttl).

    Tests override this with a fake context manager.
    """
    redis = aioredis.from_url(  # type: ignore[no-untyped-call]
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield redis
    finally:
        await redis.aclose()


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification_email(
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    email_lower = body.email.strip().lower()
    key = f"email_verify_resend:{hashlib.sha256(email_lower.encode()).hexdigest()}"
    async with _get_resend_redis() as redis:
        accepted = await redis.set(
            key,
            "1",
            ex=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS,
            nx=True,
        )
    if not accepted:
        raise HTTPException(status_code=429, detail="rate_limited")

    result = await EmailVerificationService.request_resend(session, email=email_lower)
    if result is None:
        return {}

    raw_token, user_name = result
    await session.commit()

    background_tasks.add_task(
        send_verification_email,
        to=email_lower,
        name=user_name,
        raw_token=raw_token,
    )
    return {}


class RequirePermission:
    """FastAPI dependency authorizing the current user for a permission.

    Instances are callable dependencies; the instance carries the ``Permission`` and
    ``PermissionScope`` it enforces.
    """

    def __init__(
        self, permission: Permission, permission_scope: PermissionScope, scope_param: str | None = None
    ) -> None:
        """Bind the permission and scope this dependency enforces.

        Captured at construction so one instance is a reusable dependency across requests.
        ``scope_param`` names the path parameter whose value becomes the scope object id; it
        is resolved per request (not here), because the path value does not exist yet when the
        dependency object is built.
        """
        self.permission = permission
        self.permission_scope = permission_scope
        self.scope_param = scope_param

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
    ) -> User:
        """Authorize the current user for the bound permission, or raise 403.

        Resolves the scope object id from the request's path params at call time, asks the
        permission engine whether the user may act, and returns the user so the route
        receives the authenticated principal. Raises 403 when the permission is absent, and
        500 when ``scope_param`` names a path parameter the route does not provide (a wiring
        error that would otherwise silently deny every user).
        """
        if self.scope_param is not None and self.scope_param not in request.path_params:
            logger.error(
                "RequirePermission misconfigured: scope_param %r is not among the route's path params %s",
                self.scope_param,
                list(request.path_params),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission scope is misconfigured",
            )
        scope_object_id = request.path_params.get(self.scope_param) if self.scope_param else None
        if not await can(current_user, self.permission, self.permission_scope, scope_object_id, session):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_user
