from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.models.user import User
from app.schemas import GoogleAuthUrl, Token, UserCreate, UserLogin
from app.schemas import User as UserSchema

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
    except Exception:
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
async def register_user(user: UserCreate, session: AsyncSession = Depends(get_async_session)) -> User:
    if not settings.REGISTRATION_ENABLED:
        raise HTTPException(status_code=403, detail="Registration is currently disabled")
    result = await session.exec(select(User).where(User.username == user.username))
    db_user = result.one_or_none()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    result = await session.exec(select(User).where(User.email == user.email))
    db_user_email = result.one_or_none()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = security.get_password_hash(user.password)
    db_user = User(
        name=user.name,
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
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

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    utc_now = datetime.now(timezone.utc)
    expires_at = utc_now + access_token_expires

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
        email = google_user["email"]
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
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
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
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

        # Generate JWT token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        utc_now = datetime.now(timezone.utc)
        expires_at = utc_now + access_token_expires

        jwt_token = security.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

        # Redirect to frontend callback page with token
        redirect_url = f"/login/callback?token={jwt_token}&expires_at={expires_at.isoformat()}"
        return RedirectResponse(url=redirect_url, status_code=302)

    except ValueError as e:
        # Redirect to login page with error
        return RedirectResponse(url=f"/login?error={str(e)}", status_code=302)
