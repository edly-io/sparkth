import hashlib
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import jwt
import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.db import get_async_session
from app.core.google_auth import (
    exchange_auth_code,
    generate_google_login_url,
    get_google_user_info,
)
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

router = APIRouter()
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

    assert db_user.id is not None
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


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: UserLogin, session: AsyncSession = Depends(get_async_session)
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


@router.post("/verify-email", response_model=UserSchema)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_async_session),
) -> User:
    try:
        user = await EmailVerificationService.verify_token(session, raw_token=body.token)
    except TokenExpiredError:
        raise HTTPException(status_code=400, detail="expired_token")
    except TokenInvalidError:
        raise HTTPException(status_code=400, detail="invalid_token")
    await session.commit()
    await session.refresh(user)
    return user


async def _get_resend_redis() -> Any:
    """Indirection so tests can override the rate-limit backend.

    Returns a fresh Redis client. The caller is responsible for closing it
    via `aclose()` (see the resend endpoint's try/finally). The endpoint
    is rate-limited to roughly one request per email per cooldown window,
    so per-request pool setup is fine and avoids the shared-mutable-state
    cost of a long-lived singleton. Not routed through `CacheService` —
    that wraps a different API (string get/set with default ttl).
    """
    return aioredis.from_url(  # type: ignore[no-untyped-call]
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification_email(
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, str]:
    email_lower = body.email.lower()
    key = f"email_verify_resend:{hashlib.sha256(email_lower.encode()).hexdigest()}"
    redis = await _get_resend_redis()
    try:
        accepted = await redis.set(
            key,
            "1",
            ex=settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS,
            nx=True,
        )
    finally:
        await redis.aclose()
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


async def require_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return current_user
