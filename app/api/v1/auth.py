from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.db import get_async_session
from app.models.user import User
from app.schemas import Token, UserCreate, UserLogin
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
    if not user or not security.verify_password(form_data.password, user.hashed_password):
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
